param (
    [string]$BackupDir = "",
    [int]$RetentionDays = 30,
    [string]$DbName = "",
    [string]$DbUser = "",
    [string]$DbPassword = "",
    [string]$DbHost = "",
    [string]$DbPort = ""
)

$ErrorActionPreference = "Stop"

# Resolve Project Root and load .env configuration
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$EnvFile = Join-Path $ProjectRoot ".env"

if (Test-Path $EnvFile) {
    foreach ($entry in (Get-Content $EnvFile)) {
        $trimmed = $entry.Trim()
        if ($trimmed -and -not $trimmed.StartsWith("#") -and $trimmed.Contains("=")) {
            $kv = $trimmed.Split("=", 2)
            $k = $kv[0].Trim()
            $v = $kv[1].Trim()
            if (-not [System.Environment]::GetEnvironmentVariable($k)) {
                [System.Environment]::SetEnvironmentVariable($k, $v)
            }
        }
    }
}

if (-not $BackupDir) { $BackupDir = Join-Path $ProjectRoot "backups" }
if (-not $DbName) { $DbName = if ($env:DB_NAME) { $env:DB_NAME } else { "expense_tracking_db" } }
if (-not $DbUser) { $DbUser = if ($env:DB_USER) { $env:DB_USER } else { "root" } }
if (-not $DbPassword) { $DbPassword = $env:DB_PASSWORD }
if (-not $DbHost) { $DbHost = if ($env:DB_HOST) { $env:DB_HOST } else { "127.0.0.1" } }
if (-not $DbPort) { $DbPort = if ($env:DB_PORT) { $env:DB_PORT } else { "3306" } }

if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$DumpFile = Join-Path $BackupDir "ets_backup_$Timestamp.sql"
$ZipFile = Join-Path $BackupDir "ets_backup_$Timestamp.sql.zip"
$LogFile = Join-Path $BackupDir "backup.log"

function Write-Log {
    param([string]$Message)
    $LogEntry = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $LogEntry
    Add-Content -Path $LogFile -Value $LogEntry
}

Write-Log "Starting automated backup for database '$DbName' on ${DbHost}:${DbPort}..."

# Check mysqldump existence in PATH or common Windows installation paths
$MysqldumpPath = $null
$MysqldumpCmd = Get-Command "mysqldump" -ErrorAction SilentlyContinue
if ($MysqldumpCmd) {
    $MysqldumpPath = $MysqldumpCmd.Source
} else {
    $CommonPaths = @(
        "C:\Program Files\MySQL\MySQL Server *\bin\mysqldump.exe",
        "C:\Program Files\MySQL\MySQL Workbench *\mysqldump.exe",
        "C:\Program Files (x86)\MySQL\*\bin\mysqldump.exe",
        "C:\xampp\mysql\bin\mysqldump.exe",
        "C:\laragon\bin\mysql\*\bin\mysqldump.exe"
    )
    foreach ($pattern in $CommonPaths) {
        $found = Resolve-Path $pattern -ErrorAction SilentlyContinue
        if ($found) {
            $MysqldumpPath = $found[-1].Path
            break
        }
    }
}

if (-not $MysqldumpPath -or -not (Test-Path $MysqldumpPath)) {
    Write-Log "ERROR: 'mysqldump' not found in PATH or standard MySQL directories. Please verify MySQL client tools are installed."
    exit 1
}

Write-Log "Using mysqldump binary: $MysqldumpPath"

try {
    if ($DbPassword) {
        $env:MYSQL_PWD = $DbPassword
    }

    $DumpArgs = @(
        "--host=$DbHost",
        "--port=$DbPort",
        "--user=$DbUser",
        "--single-transaction",
        "--quick",
        "--routines",
        "--triggers",
        "--default-character-set=utf8mb4",
        "--result-file=$DumpFile",
        $DbName
    )

    & $MysqldumpPath @DumpArgs

    if (-not (Test-Path $DumpFile) -or (Get-Item $DumpFile).Length -eq 0) {
        throw "Dump file is missing or empty."
    }

    Write-Log "Compressing dump file into zip archive..."
    Compress-Archive -Path $DumpFile -DestinationPath $ZipFile -Force
    Remove-Item -Path $DumpFile -Force

    $FileSizeMB = [math]::Round(((Get-Item $ZipFile).Length / 1MB), 2)
    Write-Log "SUCCESS: Backup completed successfully: $ZipFile (Size: $FileSizeMB MB)"

    Write-Log "Pruning backup archives older than $RetentionDays days..."
    $CutoffDate = (Get-Date).AddDays(-$RetentionDays)
    $OldBackups = Get-ChildItem -Path $BackupDir -Filter "ets_backup_*.zip" | Where-Object { $_.LastWriteTime -lt $CutoffDate }
    $DeletedCount = 0
    foreach ($Old in $OldBackups) {
        Remove-Item -Path $Old.FullName -Force
        $DeletedCount++
    }
    Write-Log "Pruning complete. Removed $DeletedCount old backup archive(s)."
}
catch {
    Write-Log "ERROR: Backup failed with exception: $_"
    exit 1
}
finally {
    if ($DbPassword) {
        $env:MYSQL_PWD = $null
    }
}

Write-Log "Backup job finished cleanly."
exit 0
