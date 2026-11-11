@echo off
title Sri Basaveshwara ERP - Production Readiness Check
color 0B

echo =======================================================================
echo   Sri Basaveshwara & Co. (AgriBOS ERP)
echo   Production Deployment Readiness & Security Audit
echo =======================================================================
echo.

cd /d "%~dp0"
call ".\venv\Scripts\python.exe" manage.py check --deploy --settings=expense_tracking_core.settings.production

echo.
echo =======================================================================
echo Audit completed. If 0 issues are shown, the system is ready for production.
echo =======================================================================
pause
