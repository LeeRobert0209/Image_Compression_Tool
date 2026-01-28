@echo off
chcp 65001
title 图片极限压缩工具启动器

:: --- 配置 Python 环境路径 (智能加载) ---
set "PYTHON_EXE=python"
set "PYTHONW_EXE=pythonw"

:: 1. 尝试加载本地私有配置
if exist "path_config.bat" (
    :: 先调用配置脚本
    call path_config.bat
)

:: 2. 如果配置脚本运行后，自定义变量有值，则使用自定义变量
if defined MY_PYTHON_EXE (
    set "PYTHON_EXE=%MY_PYTHON_EXE%"
    set "PYTHONW_EXE=%MY_PYTHONW_EXE%"
)

echo ==================================================
echo      正在初始化图片压缩工具...
echo      Design by Antigravity
echo      使用环境: %PYTHON_EXE%
echo ==================================================
echo.

:: 1. 检查 Python 是否存在
if not exist "%PYTHON_EXE%" (
    :: 如果是默认的 "python" 命令，其实 exist 检查可能会误报，但没关系
    :: 我们加一个特判: 如果是绝对路径且不存在，才报错
    echo [检查] 正在验证环境...
    "%PYTHON_EXE%" --version >nul 2>&1
    if %errorlevel% neq 0 (
         echo [错误] 无法运行 Python: %PYTHON_EXE%
         echo.
         echo [提示] 如果未安装 Python，请访问 python.org 下载
         echo (或者检查 path_config.bat 中的路径是否正确)
         pause
         exit
    )
)

:: 2. 检查依赖并自动安装
echo [检查依赖库] ...
"%PYTHON_EXE%" -c "import PIL, tkinterdnd2, fitz" >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 首次运行，正在安装必要组件...
    "%PYTHON_EXE%" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if %errorlevel% neq 0 (
        echo [错误] 依赖安装失败，请检查网络或 pip 配置。
        pause
        exit
    )
    echo [成功] 依赖安装完成。
) else (
    echo [检查通过] 环境完整。
)

:: 3. 启动工具 (使用 pythonw 隐藏黑窗口)
echo [正在启动] ...
if exist "%PYTHONW_EXE%" (
    start "" "%PYTHONW_EXE%" gui.py
) else (
    echo [警告] 未找到 pythonw.exe，将使用普通模式启动...
    "%PYTHON_EXE%" gui.py
)

exit
