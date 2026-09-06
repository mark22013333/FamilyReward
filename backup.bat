@echo off
chcp 65001 >nul 2>&1
setlocal

REM ===========================================================
REM  家庭任務集點樂園 - 備份資料庫
REM  使用 SQLite Backup API，系統執行中也可以安全備份。
REM ===========================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo.
echo      家庭任務集點樂園 - 備份資料庫
echo.
echo ============================================================
echo.

set "PYTHON="
if exist "runtime\python.exe"       set "PYTHON=runtime\python.exe"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

if "%PYTHON%"=="" (
    echo [錯誤] 找不到 Python 環境。
    echo.
    echo 請先執行一次 start.bat 完成安裝。
    echo.
    pause
    exit /b 1
)

"%PYTHON%" scripts\backup_db.py
set "EXITCODE=%ERRORLEVEL%"

echo.
pause
endlocal
exit /b %EXITCODE%
