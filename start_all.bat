@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [FinanceDashboard] Starting backend and frontend ...
echo.

:: Start backend in a new window
start "FinanceDashboard Backend" cmd /k "cd /d backend && start.bat"

:: Wait for backend to initialize
ping -n 5 127.0.0.1 >nul

:: Start frontend in a new window
start "FinanceDashboard Frontend" cmd /k "cd /d frontend && start.bat"

echo.
echo Services started in new windows:
echo   - Backend: http://localhost:8000
echo   - Frontend: http://localhost:80  (port 80 may require admin rights)
echo.
echo Press any key to close this window (service windows will remain running).
pause >nul
