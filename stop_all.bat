@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [FinanceDashboard] Stopping backend and frontend ...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_all.ps1"

echo.
echo Done.
if /i not "%~1"=="nopause" pause
