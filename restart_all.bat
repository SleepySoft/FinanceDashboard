@echo off
chcp 65001 >nul
cd /d "%~dp0"

set FRONTEND_PORT=%1
if "%FRONTEND_PORT%"=="" set FRONTEND_PORT=80

echo [FinanceDashboard] Restarting services ...
echo.

call "%~dp0stop_all.bat" nopause

echo.
echo Starting services again ...
call "%~dp0start_all.bat" %FRONTEND_PORT%
