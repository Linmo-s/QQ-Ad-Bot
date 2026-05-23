@echo off
chcp 65001 >nul
echo ========================================
echo   QQ-Ad-Bot 环境初始化
echo ========================================

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.12+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 创建虚拟环境
if not exist ".venv" (
    echo [1/4] 创建虚拟环境...
    python -m venv .venv
) else (
    echo [1/4] 虚拟环境已存在，跳过
)

:: 安装 Python 依赖（使用清华镜像源，国内网络无需 VPN）
echo [2/4] 安装 Python 依赖...
.venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

:: 初始化配置
if not exist "massages_image_massage\data\config.json" (
    echo [3/4] 初始化配置文件...
    if not exist "massages_image_massage\data" mkdir "massages_image_massage\data"
    copy "massages_image_massage\data\config.example.json" "massages_image_massage\data\config.json" >nul 2>&1
    echo       已从模板创建 config.json，请通过 Web 面板配置
) else (
    echo [3/4] 配置文件已存在，跳过
)

:: 安装 NapCat 依赖（使用淘宝镜像源，国内网络无需 VPN）
if exist "NapCat.Shell\package.json" (
    if not exist "NapCat.Shell\node_modules" (
        echo [4/4] 安装 NapCat Node.js 依赖...
        where npm >nul 2>&1
        if not errorlevel 1 (
            cd NapCat.Shell && npm install --registry=https://registry.npmmirror.com && cd ..
        ) else (
            echo       未找到 npm，跳过 NapCat 依赖安装
            echo       如果 NapCat.Shell\node_modules 已包含，可忽略此提示
        )
    ) else (
        echo [4/4] NapCat 依赖已存在，跳过
    )
) else (
    echo [4/4] 未找到 NapCat.Shell，跳过
)

echo.
echo ========================================
echo   初始化完成！运行 start.bat 启动机器人
echo ========================================
pause
