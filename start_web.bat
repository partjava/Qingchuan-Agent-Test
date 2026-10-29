@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=D:\anaconda\anaconda\envs\pytorch\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=D:\anaconda\anaconda\python.exe"
)
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

echo ========================================================
echo   晴川 校园办事智能体与 RAG 交互系统
echo   正在初始化系统并加载核心模型，请稍候...
echo   服务地址: http://127.0.0.1:8000
echo ========================================================

"%PYTHON_EXE%" main.py --web --port 8000
if %errorlevel% neq 0 (
    echo.
    echo System exited with error code %errorlevel%.
    pause
)
