@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [FinanceDashboard] 一键启动
echo.

:: 启动后端（在新窗口）
start "FinanceDashboard Backend" cmd /k "cd /d backend && start.bat"

:: 等待后端初始化
timeout /t 4 /nobreak >nul

:: 启动前端（在新窗口）
start "FinanceDashboard Frontend" cmd /k "cd /d frontend && start.bat"

echo.
echo 已在新窗口中启动：
echo   - 后端：http://localhost:8000
echo   - 前端：http://localhost:80  （80 端口可能需要管理员权限）
echo.
echo 按任意键关闭本窗口（服务窗口不会随之关闭）。
pause >nul
