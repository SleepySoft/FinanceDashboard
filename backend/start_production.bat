@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [FinanceDashboard Backend - Production]
echo.

if not exist "..\frontend\dist\" (
    echo 未检测到 frontend\dist，请先运行 frontend\build.bat 构建前端。
    pause
    exit /b 1
)

if not exist "venv\Scripts\activate.bat" (
    echo 未检测到虚拟环境，请先运行 start.bat 完成初始化。
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo 启动生产服务（http://localhost:80）...
echo 注意：80 端口需要管理员权限，若启动失败请以管理员身份运行本脚本。
uvicorn main:app --host 0.0.0.0 --port 80
pause
