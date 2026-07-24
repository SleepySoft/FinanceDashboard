@echo off
chcp 65001 >nul
cd /d "%~dp0"

set PORT=%1
if "%PORT%"=="" set PORT=80

echo [FinanceDashboard Backend - Production]
echo.

if not exist "..\frontend\dist" (
    echo frontend\dist not found. Please run frontend\build.bat first.
    pause
    exit /b 1
)

if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found. Please run start.bat first to initialize.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo Starting production server (http://localhost:%PORT%) ...
if "%PORT%"=="80" (
    echo Note: port 80 may require administrator rights. Run this script as administrator if it fails.
)
uvicorn main:app --host 0.0.0.0 --port %PORT%
pause
