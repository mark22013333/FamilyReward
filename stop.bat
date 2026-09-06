@echo off
chcp 65001 >nul 2>&1
setlocal

REM ===========================================================
REM  家庭任務集點樂園 - 停止
REM  只會關閉本系統自己記錄的 PID，
REM  絕不使用 taskkill /F /IM python.exe，
REM  以免誤殺使用者其他的 Python 程式。
REM ===========================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo.
echo      家庭任務集點樂園 - 停止服務
echo.
echo ============================================================
echo.

set "PYTHON="
if exist "runtime\python.exe"      set "PYTHON=runtime\python.exe"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

if "%PYTHON%"=="" (
    echo [錯誤] 找不到 Python 環境。
    echo.
    echo 服務可能從來沒有啟動過。
    echo.
    pause
    exit /b 1
)

"%PYTHON%" launcher.py stop

echo.
pause
endlocal
