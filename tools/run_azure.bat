@echo off
set "PATH=%~dp0;%PATH%"
setlocal enabledelayedexpansion
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

rem Fallback for freshly installed winget ffmpeg (where PATH is not refreshed)
for /d %%d in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*") do (
    for /d %%f in ("%%d\ffmpeg-*") do (
        set "PATH=%%f\bin;!PATH!"
    )
)

rem Find .env in current or parent directory
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

rem Get pipeline.py absolute path
set PIPELINE_SCRIPT=%~dp0pipeline.py

rem No arguments -> let the user pick a mode (any argument skips the menu)
set MODE_ARGS=
if "%~1"=="" (
    echo.
    echo 選擇輸出模式 / Choose output mode:
    echo   [1] 傳統版:硬切換頁,乾淨影片 + 外掛 SRT 字幕 ^(預設^)
    echo   [2] 動態版:頁間轉場動畫 + 逐字卡拉OK字幕燒錄
    choice /c 12 /n /d 1 /t 30 /m "請按 1 或 2(30 秒未按自動選 1): "
    if errorlevel 2 (
        set MODE_ARGS=
    ) else if errorlevel 1 (
        set MODE_ARGS=--plain
    )
)

python "!PIPELINE_SCRIPT!" --engine azure !MODE_ARGS! %*
if errorlevel 1 (
    echo.
    echo [ERROR] pipeline failed. See messages above.
    pause
    exit /b 1
)
