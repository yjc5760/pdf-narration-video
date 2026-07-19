@echo off
chcp 65001 >nul
setlocal

:: 切換到專案根目錄
cd /d "%~dp0.."

:: 取得目前時間產生檔名
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set "TIMESTAMP=%datetime:~0,4%%datetime:~4,2%%datetime:~6,2%_%datetime:~8,2%%datetime:~10,2%%datetime:~12,2%"
set "BACKUP_FILE=tts_cache_backup_%TIMESTAMP%.zip"

echo 正在備份各專案 work/ 目錄下的 TTS 快取檔案...
echo 備份檔案將儲存為: %BACKUP_FILE%

:: 使用 PowerShell 將 page-*.json 與 page-*.mp3 打包
:: 注意:必須保留「專案/work/檔名」相對路徑,否則不同專案的 page-01.mp3 會互相覆蓋
powershell -NoProfile -Command "Add-Type -AssemblyName System.IO.Compression.FileSystem; $zip=[System.IO.Compression.ZipFile]::Open('%BACKUP_FILE%','Create'); Get-ChildItem -Path '.\*\work\*' -Include 'page-*.json','page-*.mp3' -ErrorAction SilentlyContinue | ForEach-Object { $rel=(Resolve-Path -Relative $_.FullName).TrimStart('.','\').Replace('\','/'); [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,$_.FullName,$rel) } | Out-Null; $zip.Dispose()"

if exist "%BACKUP_FILE%" (
    echo [成功] 備份完成！
) else (
    echo [警告] 找不到可以備份的檔案，或是備份失敗。
)

echo.
pause
endlocal
