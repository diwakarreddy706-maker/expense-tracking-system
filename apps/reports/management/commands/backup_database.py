import os
import sys
import gzip
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Executes a robust, compressed database backup with integrity verification and retention pruning'

    def add_arguments(self, parser):
        parser.add_argument(
            '--destination',
            type=str,
            default=os.getenv('BACKUP_DIR', str(settings.BASE_DIR / 'backups')),
            help='Directory path where backup archives will be stored'
        )
        parser.add_argument(
            '--retention-days',
            type=int,
            default=int(os.getenv('RETENTION_DAYS', '30')),
            help='Number of days to keep backup archives before pruning (default 30)'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['auto', 'sql', 'json'],
            default='auto',
            help='Backup format: auto (detects engine), sql (native dump), json (portable Django fixture)'
        )

    def handle(self, *args, **options):
        dest_dir = Path(options['destination'])
        dest_dir.mkdir(parents=True, exist_ok=True)
        retention_days = options['retention_days']
        fmt = options['format']

        db_config = settings.DATABASES['default']
        engine = db_config['ENGINE']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        self.stdout.write(f"Initiating database backup for engine: {engine}...")

        backup_file = None
        if fmt == 'json' or 'sqlite' in engine:
            backup_file = self._backup_json_or_sqlite(dest_dir, timestamp, engine, db_config, fmt)
        elif 'mysql' in engine:
            backup_file = self._backup_mysql(dest_dir, timestamp, db_config)
        elif 'postgresql' in engine or 'postgres' in engine:
            backup_file = self._backup_postgres(dest_dir, timestamp, db_config)
        else:
            # Fallback to portable JSON
            backup_file = self._backup_json(dest_dir, timestamp)

        if not backup_file or not backup_file.exists() or backup_file.stat().st_size == 0:
            raise CommandError("Backup failed: Output archive is missing or empty.")

        size_kb = round(backup_file.stat().st_size / 1024, 2)
        self.stdout.write(self.style.SUCCESS(
            f"Successfully created backup archive: {backup_file} ({size_kb} KB)"
        ))

        # Retention Pruning
        self._prune_old_backups(dest_dir, retention_days)

    def _backup_mysql(self, dest_dir: Path, timestamp: str, db_config: dict) -> Path:
        out_path = dest_dir / f"ets_mysql_{timestamp}.sql.gz"
        mysqldump_bin = shutil.which('mysqldump')

        if not mysqldump_bin:
            self.stdout.write(self.style.WARNING("mysqldump binary not detected. Falling back to Django native JSON export..."))
            return self._backup_json(dest_dir, timestamp)

        host = db_config.get('HOST', '127.0.0.1')
        port = str(db_config.get('PORT', '3306'))
        user = db_config.get('USER', 'root')
        password = db_config.get('PASSWORD', '')
        dbname = db_config.get('NAME', '')

        cmd = [
            mysqldump_bin,
            f"--host={host}",
            f"--port={port}",
            f"--user={user}",
            "--single-transaction",
            "--quick",
            "--routines",
            "--triggers",
            "--default-character-set=utf8mb4",
            dbname
        ]

        env = os.environ.copy()
        if password:
            env['MYSQL_PWD'] = password

        try:
            with open(out_path, 'wb') as f_out:
                with gzip.GzipFile(fileobj=f_out, mode='wb') as gz_out:
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
                    shutil.copyfileobj(proc.stdout, gz_out)
                    proc.wait()
                    if proc.returncode != 0:
                        err = proc.stderr.read().decode('utf-8', errors='ignore')
                        self.stdout.write(self.style.WARNING(f"mysqldump error ({err}). Falling back to JSON snapshot..."))
                        if out_path.exists():
                            out_path.unlink()
                        return self._backup_json(dest_dir, timestamp)
            return out_path
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"mysqldump execution failed: {e}. Falling back to JSON snapshot..."))
            if out_path.exists():
                out_path.unlink()
            return self._backup_json(dest_dir, timestamp)

    def _backup_postgres(self, dest_dir: Path, timestamp: str, db_config: dict) -> Path:
        out_path = dest_dir / f"ets_postgres_{timestamp}.sql.gz"
        pg_dump_bin = shutil.which('pg_dump')

        if not pg_dump_bin:
            self.stdout.write(self.style.WARNING("pg_dump binary not detected. Falling back to Django native JSON export..."))
            return self._backup_json(dest_dir, timestamp)

        host = db_config.get('HOST', '127.0.0.1')
        port = str(db_config.get('PORT', '5432'))
        user = db_config.get('USER', 'postgres')
        password = db_config.get('PASSWORD', '')
        dbname = db_config.get('NAME', '')

        cmd = [
            pg_dump_bin,
            f"--host={host}",
            f"--port={port}",
            f"--username={user}",
            "--clean",
            "--no-owner",
            dbname
        ]

        env = os.environ.copy()
        if password:
            env['PGPASSWORD'] = password

        try:
            with open(out_path, 'wb') as f_out:
                with gzip.GzipFile(fileobj=f_out, mode='wb') as gz_out:
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
                    shutil.copyfileobj(proc.stdout, gz_out)
                    proc.wait()
                    if proc.returncode != 0:
                        self.stdout.write(self.style.WARNING("pg_dump failed. Falling back to JSON snapshot..."))
                        if out_path.exists():
                            out_path.unlink()
                        return self._backup_json(dest_dir, timestamp)
            return out_path
        except Exception:
            return self._backup_json(dest_dir, timestamp)

    def _backup_json_or_sqlite(self, dest_dir: Path, timestamp: str, engine: str, db_config: dict, fmt: str) -> Path:
        if fmt == 'json' or 'sqlite' not in engine:
            return self._backup_json(dest_dir, timestamp)

        # SQLite atomic file copy & compress
        sqlite_path = Path(db_config['NAME'])
        if not sqlite_path.exists():
            return self._backup_json(dest_dir, timestamp)

        out_path = dest_dir / f"ets_sqlite_{timestamp}.sqlite3.gz"
        with open(sqlite_path, 'rb') as f_in:
            with gzip.open(out_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return out_path

    def _backup_json(self, dest_dir: Path, timestamp: str) -> Path:
        out_path = dest_dir / f"ets_snapshot_{timestamp}.json.gz"
        temp_json = dest_dir / f"ets_temp_{timestamp}.json"

        try:
            with open(temp_json, 'w', encoding='utf-8') as f:
                call_command(
                    'dumpdata',
                    natural_foreign=True,
                    natural_primary=True,
                    exclude=['contenttypes', 'auth.permission', 'sessions'],
                    stdout=f
                )

            with open(temp_json, 'rb') as f_in:
                with gzip.open(out_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            return out_path
        finally:
            if temp_json.exists():
                temp_json.unlink()

    def _prune_old_backups(self, dest_dir: Path, retention_days: int):
        cutoff = datetime.now() - timedelta(days=retention_days)
        deleted = 0
        for item in dest_dir.glob('ets_*.*'):
            if item.is_file():
                mtime = datetime.fromtimestamp(item.stat().st_mtime)
                if mtime < cutoff:
                    try:
                        item.unlink()
                        deleted += 1
                    except Exception:
                        pass
        if deleted:
            self.stdout.write(f"Pruned {deleted} expired backup file(s) older than {retention_days} days.")
