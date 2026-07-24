@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [FinanceDashboard Frontend]
echo.

if not exist "node_modules\" (
    echo 未检测到 node_modules，正在安装 npm 依赖 ...
    npm install
    if errorlevel 1 (
        echo npm 依赖安装失败，请确认已安装 Node.js 18+ 且加入了 PATH。
        pause
        exit /b 1
    )
)

echo.
echo 启动 Vite 开发服务器（http://localhost:80）...
echo 注意：80 端口需要管理员权限，若启动失败请以管理员身份运行本脚本。
npm run dev
pause
