@echo off
setlocal enabledelayedexpansion
if not exist ".env" (
    echo [ERROR] .env not found. Create it with AZURE_SPEECH_KEY / AZURE_SPEECH_REGION
    pause
    exit /b 1
)
rem Read .env, skipping blank lines and lines starting with #
for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" set "%%A=%%~B"
)
python pipeline.py --engine azure %*
if errorlevel 1 (
    echo.
    echo [ERROR] pipeline failed. See messages above.
    pause
    exit /b 1
)
