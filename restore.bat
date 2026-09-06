@echo off
chcp 65001 >nul 2>&1
setlocal

REM ===========================================================
REM  家庭任務集點樂園 - 還原資料庫
REM  還原前必須先停止系統（restore_db.py 會檢查）。
REM  還原前會自動把目前的資料庫備份為 pre-restore-*。
REM ===========================================================

cd /d "%~dp0"

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

"%PYTHON%" scripts\restore_db.py
set "EXITCODE=%ERRORLEVEL%"

echo.
pause
endlocal
exit /b %EXITCODE%
