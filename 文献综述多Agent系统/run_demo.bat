@echo off
chcp 65001 >/dev/null
echo ========================================
echo   文献综述自动梳理系统 - 启动脚本
echo ========================================
echo.

REM 检查 Python
python --version >/dev/null 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 检查依赖
echo [1/3] 检查依赖...
pip show requests >/dev/null 2>&1
if errorlevel 1 (
    echo [2/3] 安装依赖...
    pip install -r requirements.txt
) else (
    echo [2/3] 依赖已安装
)

REM 设置 API Key（请替换为你的 key）
REM set DEEPSEEK_API_KEY=sk-your-key-here

echo.
echo [3/3] 启动系统...
echo.
echo 使用方法：
echo   1. 先设置 API Key: set DEEPSEEK_API_KEY=sk-your-key-here
echo   2. 运行: python main.py --topic "你的研究主题"
echo.
echo 示例命令：
echo   python main.py --topic "深度学习在医学影像中的应用" --workers 4
echo.

pause
