@echo off
chcp 65001
title 打包方案 (DLL硬塞版)...

:: --- 配置环境路径 (智能加载) ---
set "ENV_PATH=C:\Your\Anaconda\Path\envs\xx"
set "PYTHON_EXE=python"

:: 1. 尝试加载本地私有配置
if exist "path_config.bat" (
    call path_config.bat
)

:: 2. 覆盖默认值 (如果存在私有配置)
if defined MY_ENV_ROOT (
    set "ENV_PATH=%MY_ENV_ROOT%"
)
if defined MY_PYTHON_EXE (
    set "PYTHON_EXE=%MY_PYTHON_EXE%"
)

:: 核心：找到那几个调皮的 DLL (通常在 Library\bin)
set "DLL_SRC=%ENV_PATH%\Library\bin"

echo ==================================================
echo      正在生成独立 EXE (DLL硬塞版)
echo      策略: 使用 --add-binary 强制植入 DLL
echo ==================================================
echo.

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec

echo [1/2] 正在打包...

:: --add-binary "源;目标": 强制把文件塞进去
:: 塞入 tcl86t.dll 和 tk86t.dll 到根目录 (.)
:: 塞入 sqlite3.dll 和 zlib.dll 以防万一
"%PYTHON_EXE%" -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "图片极限压缩工具" ^
    --add-binary "%DLL_SRC%\tcl86t.dll;." ^
    --add-binary "%DLL_SRC%\tk86t.dll;." ^
    --add-binary "%DLL_SRC%\sqlite3.dll;." ^
    --add-binary "%DLL_SRC%\zlib.dll;." ^
    --hidden-import "tkinter" ^
    --collect-all "tkinterdnd2" ^
    gui.py

if %errorlevel% neq 0 (
    echo [错误] 打包失败！
    pause
    exit
)

echo.
echo ==================================================
echo      🎉 打包成功！
echo.
echo      请测试 [dist] 文件夹下的 EXE 文件。
echo      如果这次还不行，我就把电脑吃了。
echo ==================================================
pause
explorer dist
