@echo off
title Sri Basaveshwara ERP - Install Automated Backup Scheduler
color 0A

echo =======================================================================
echo   Sri Basaveshwara & Co. (AgriBOS ERP)
echo   Automated Nightly Database Backup Scheduler Installer
echo =======================================================================
echo.

set "TASK_NAME=AgriBOS_Daily_Database_Backup"
set "SCRIPT_PATH=%~dp0scripts\backup_db.ps1"

echo Registering Windows Task Scheduler Job: "%TASK_NAME%"...
echo Target Script: "%SCRIPT_PATH%"
echo Frequency: Daily at 00:00 (Midnight)
echo.

schtasks /Create /SC DAILY /TN "%TASK_NAME%" /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"%SCRIPT_PATH%\"" /ST 00:00 /F

if %ERRORLEVEL% EQU 0 (
    echo.
    echo =======================================================================
    echo [SUCCESS] Daily automated backup task registered successfully!
    echo The database will automatically backup every night at 00:00 (Midnight).
    echo Backups are compressed and stored in the "backups" folder with 30-day retention.
    echo =======================================================================
) else (
    echo.
    echo [NOTE] If registration required elevated permissions, please right-click this
    echo file and choose "Run as administrator".
)

echo.
pause
