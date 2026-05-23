@echo off
chcp 65001 >nul

if not exist ".venv" (
    echo [错误] 虚拟环境不存在，请先运行 setup.bat
    pause
    exit /b 1
)

echo 正在启动 QQ-Ad-Bot...
.venv\Scripts\python bot.py
pause
