@echo off
title Sri Basaveshwara ERP - Remove Automated Backup Scheduler
color 0C

echo =======================================================================
echo   Sri Basaveshwara & Co. (AgriBOS ERP)
echo   Uninstall Nightly Database Backup Scheduler
echo =======================================================================
echo.

set "TASK_NAME=AgriBOS_Daily_Database_Backup"

echo Removing Windows Task Scheduler Job: "%TASK_NAME%"...
echo.

schtasks /Delete /TN "%TASK_NAME%" /F

if %ERRORLEVEL% EQU 0 (
    echo.
    echo =======================================================================
    echo [SUCCESS] Scheduled backup task removed successfully.
    echo =======================================================================
) else (
    echo.
    echo [NOTE] Task was not found or already removed.
)

echo.
pause
