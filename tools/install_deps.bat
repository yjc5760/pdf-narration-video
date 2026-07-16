@echo off
setlocal
echo ============================================
echo  PDF-to-video pipeline - dependency setup
echo ============================================
echo.

rem --- 1. Python ---
where python >nul 2>nul
if errorlevel 1 (
    echo [MISSING] python not found. Install it first:
    echo           winget install Python.Python.3.12
    echo           Then open a NEW window and run this file again.
    pause
    exit /b 1
)
python --version

rem --- 2. pip packages ---
echo.
echo [INSTALL] azure-cognitiveservices-speech + requests ...
python -m pip install --upgrade azure-cognitiveservices-speech requests
if errorlevel 1 (
    echo [ERROR] pip install failed. See messages above.
    pause
    exit /b 1
)

rem --- 3. ffmpeg / ffprobe (exe already bundled in this folder) ---
echo.
where ffmpeg >nul 2>nul
if not errorlevel 1 goto ffmpeg_ok
if exist "%~dp0ffmpeg.exe" goto ffmpeg_ok
echo [MISSING] ffmpeg. Trying winget...
winget install --accept-source-agreements --accept-package-agreements ffmpeg
echo           Open a NEW window afterwards so PATH takes effect.
goto ffmpeg_done
:ffmpeg_ok
echo [OK] ffmpeg / ffprobe available
:ffmpeg_done

rem --- 4. pdftoppm (poppler, converts PDF pages to images) ---
echo.
where pdftoppm >nul 2>nul
if not errorlevel 1 (
    echo [OK] pdftoppm available
    goto poppler_done
)
echo [MISSING] pdftoppm. Trying winget poppler...
winget install --accept-source-agreements --accept-package-agreements oschwartz10612.Poppler
if errorlevel 1 (
    echo.
    echo [HINT] If winget cannot find it, download manually:
    echo   https://github.com/oschwartz10612/poppler-windows/releases
    echo   Unzip, then add Library\bin to PATH, or copy the files
    echo   from bin into this folder.
)
echo           Open a NEW window afterwards so PATH takes effect.
:poppler_done

rem --- 5. .env check ---
echo.
if exist "%~dp0.env" (
    echo [OK] .env exists
) else (
    echo [TODO] No .env yet. Create one with:
    echo   AZURE_SPEECH_KEY="your-key"
    echo   AZURE_SPEECH_REGION="your-region"
)

echo.
echo ============================================
echo  Done. Run run_azure.bat to build the video.
echo ============================================
pause
