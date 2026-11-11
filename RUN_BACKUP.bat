@echo off
title Sri Basaveshwara ERP - Database Backup
color 0B

echo ========================================================
echo   Sri Basaveshwara & Co. (AgriBOS ERP)
echo   Running Database Backup...
echo ========================================================

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\backup_db.ps1"

echo ========================================================
echo Backup process complete. Check the backups folder.
echo ========================================================

if "%1"=="--silent" goto end
if "%1"=="-s" goto end
pause
:end
