@echo off
title Sri Basaveshwara Harvesting & Co - ERP System
color 0A

echo ========================================================
echo    Sri Basaveshwara Harvesting & Co. - AgriBOS ERP
echo ========================================================
echo [1/3] Checking environment...

cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in %~dp0venv!
    echo Please ensure the project virtual environment is installed.
    pause
    exit /b 1
)

echo [2/3] Launching AgriBOS ERP in browser...
start /min cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8000/"

echo [3/3] System is running. Keep this window open while using the software.
echo Close this window or press Ctrl+C to shut down the server.
echo ========================================================

.\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
pause
