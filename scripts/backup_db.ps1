<#
.SYNOPSIS
    Expense Tracking System - Automated MySQL Database Backup Script for Windows
.DESCRIPTION
    Performs transactional mysqldump, compression, integrity validation, and 30-day retention pruning.
#>

param (
    [string]$BackupDir = "C:\backups\expense_tracking",
    [int]$RetentionDays = 30,
    [string]$DbName = $env:DB_NAME,
    [string]$DbUser = $env:DB_USER,
    [string]$DbPassword = $env:DB_PASSWORD,
    [string]$DbHost = $(if ($env:DB_HOST) { $env:DB_HOST } else { "127.0.0.1" }),
    [string]$DbPort = $(if ($env:DB_PORT) { $env:DB_PORT } else { "3306" })
)

$ErrorActionPreference = "Stop"

if (-not $DbName) { $DbName = "expense_tracking_db" }
if (-not $DbUser) { $DbUser = "expense_user" }

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

# Check mysqldump existence
$MysqldumpCmd = Get-Command "mysqldump" -ErrorAction SilentlyContinue
if (-not $MysqldumpCmd) {
    Write-Log "ERROR: 'mysqldump' not found in PATH. Please verify MySQL client tools are installed."
    exit 1
}

try {
    # Set password in environment securely for child process
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

    & mysqldump @DumpArgs

    if (-not (Test-Path $DumpFile) -or (Get-Item $DumpFile).Length -eq 0) {
        throw "Dump file is missing or empty."
    }

    Write-Log "Compressing dump file into zip archive..."
    Compress-Archive -Path $DumpFile -DestinationPath $ZipFile -Force
    Remove-Item -Path $DumpFile -Force

    $FileSizeMB = [math]::Round(((Get-Item $ZipFile).Length / 1MB), 2)
    Write-Log "SUCCESS: Backup completed successfully: $ZipFile (Size: $FileSizeMB MB)"

    # Prune old backups
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
