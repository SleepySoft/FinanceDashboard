@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [FinanceDashboard Frontend]
echo.

if not exist "node_modules" (
    echo node_modules not found. Installing npm dependencies ...
    npm install
    if errorlevel 1 (
        echo Failed to install npm dependencies. Make sure Node.js 18+ is installed and in PATH.
        pause
        exit /b 1
    )
)

echo.
echo Starting Vite dev server (http://localhost:80) ...
echo Note: port 80 may require administrator rights. Run this script as administrator if it fails.
npm run dev
pause
