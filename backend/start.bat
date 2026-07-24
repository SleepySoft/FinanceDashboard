@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [FinanceDashboard Backend]
echo.

if not exist "venv\Scripts\activate.bat" (
    echo 未检测到 Python 虚拟环境，正在创建 ...
    python -m venv venv
    if errorlevel 1 (
        echo 创建虚拟环境失败，请确认已安装 Python 3.10+ 且加入了 PATH。
        pause
        exit /b 1
    )
    echo 虚拟环境创建完成，正在安装依赖 ...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    if errorlevel 1 (
        echo 依赖安装失败，请检查网络或 requirements.txt。
        pause
        exit /b 1
    )
) else (
    call venv\Scripts\activate.bat
)

echo.
echo 启动 Uvicorn 开发服务器（http://localhost:8000）...
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
