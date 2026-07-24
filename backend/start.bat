@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [FinanceDashboard Backend]
echo.

if not exist "venv\Scripts\activate.bat" (
    echo Python virtual environment not found. Creating ...
    python -m venv venv
    if errorlevel 1 (
        echo Failed to create virtual environment. Make sure Python 3.10+ is installed and in PATH.
        pause
        exit /b 1
    )
    echo Virtual environment created. Installing dependencies ...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install dependencies. Check your network or requirements.txt.
        pause
        exit /b 1
    )
) else (
    call venv\Scripts\activate.bat
)

echo.
echo Starting Uvicorn dev server (http://localhost:8000) ...
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
