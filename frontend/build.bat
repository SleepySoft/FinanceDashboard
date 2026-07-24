@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [FinanceDashboard Frontend] Building production bundle ...

if not exist "node_modules" (
    echo node_modules not found. Installing npm dependencies ...
    npm install
    if errorlevel 1 (
        echo Failed to install npm dependencies. Make sure Node.js 18+ is installed and in PATH.
        pause
        exit /b 1
    )
)

npm run build
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Build complete. Output directory: frontend\dist
echo For production, run backend\start_production.bat to serve API + static files.
pause
