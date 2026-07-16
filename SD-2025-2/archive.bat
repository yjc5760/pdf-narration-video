@echo off
rem Archive SD-2025-2 final video to repo root output\ (copy -> verify -> done; sources kept)
cd /d "%~dp0"

copy /y "output\final_video.mp4" "..\output\SD-2025-2.mp4" >nul
copy /y "output\final_video.srt" "..\output\SD-2025-2.srt" >nul

fc /b "output\final_video.mp4" "..\output\SD-2025-2.mp4" >nul
if errorlevel 1 (
    echo [ERROR] MP4 copy verification FAILED - do not trust the archived file.
    pause
    exit /b 1
)
fc /b "output\final_video.srt" "..\output\SD-2025-2.srt" >nul
if errorlevel 1 (
    echo [ERROR] SRT copy verification FAILED - do not trust the archived file.
    pause
    exit /b 1
)

if exist "..\output\sync_probe.txt" del /q "..\output\sync_probe.txt"

echo [OK] Archived and byte-verified:
echo   ..\output\SD-2025-2.mp4
echo   ..\output\SD-2025-2.srt
pause
