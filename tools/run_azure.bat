@echo off
set "PATH=%~dp0;%PATH%"
setlocal enabledelayedexpansion
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

:: 尋找 .env (先找當前目錄，再找上一層目錄)
set ENV_FILE=
if exist ".env" (
    set ENV_FILE=.env
) else if exist "..\.env" (
    set ENV_FILE=..\.env
)

if "!ENV_FILE!"=="" (
    echo [ERROR] .env not found in current or parent directory. Create it with AZURE_SPEECH_KEY / AZURE_SPEECH_REGION
    pause
    exit /b 1
)

rem Read .env, skipping blank lines and lines starting with #
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("!ENV_FILE!") do (
    if not "%%A"=="" set "%%A=%%~B"
)

:: 取得 pipeline.py 絕對路徑，確保不論在哪個資料夾執行都能找到
set PIPELINE_SCRIPT=%~dp0pipeline.py

python "!PIPELINE_SCRIPT!" --engine azure %*
if errorlevel 1 (
    echo.
    echo [ERROR] pipeline failed. See messages above.
    pause
    exit /b 1
)
