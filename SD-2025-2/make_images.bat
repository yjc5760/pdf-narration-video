@echo off
rem Step 0 for project SD-2025-2:
rem   1) copy .env from SS-2023-1 if missing (Azure key, content never displayed)
rem   2) convert the source PDF into images/slide-NN.jpg with pdftoppm
set "PATH=%~dp0..\tools;%PATH%"
cd /d "%~dp0"

if not exist ".env" (
    if exist "..\SS-2023-1\.env" (
        copy /y "..\SS-2023-1\.env" ".env" >nul
        echo [OK] .env copied from SS-2023-1
    ) else (
        echo [TODO] No .env found. Create one here with:
        echo   AZURE_SPEECH_KEY="your-key"
        echo   AZURE_SPEECH_REGION="your-region"
    )
)

where pdftoppm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] pdftoppm not found. Install poppler first:
    echo   winget install oschwartz10612.Poppler
    echo   Then open a NEW window and run this file again.
    pause
    exit /b 1
)

if not exist "images" mkdir images
pdftoppm -jpeg -r 150 "..\input\2-DOF_Modal_Analysis_Sketchnotes.pdf" images\slide
if errorlevel 1 (
    echo [ERROR] pdftoppm failed. See messages above.
    pause
    exit /b 1
)

echo [OK] images generated:
dir /b images
echo.
echo Next step: run_azure.bat        (build video)
echo        or: run_azure.bat --verify   (build + ASR pronunciation check)
pause
