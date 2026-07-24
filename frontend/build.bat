@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [FinanceDashboard Frontend] 正在构建生产包 ...

if not exist "node_modules\" (
    echo 未检测到 node_modules，正在安装 npm 依赖 ...
    npm install
    if errorlevel 1 (
        echo npm 依赖安装失败，请确认已安装 Node.js 18+ 且加入了 PATH。
        pause
        exit /b 1
    )
)

npm run build
if errorlevel 1 (
    echo 构建失败。
    pause
    exit /b 1
)

echo.
echo 构建完成，输出目录：frontend\dist
echo 生产环境请运行 backend\start_production.bat，由后端统一 serve API + 静态文件。
pause
