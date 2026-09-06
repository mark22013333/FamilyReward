@echo off
chcp 65001 >nul 2>&1
setlocal

REM ===========================================================
REM  Family Reward - Stop
REM
REM  IMPORTANT: keep this file pure ASCII with CRLF line endings.
REM  See scripts\msg.py for the reason.
REM
REM  Only the PID recorded by this system is stopped. We never
REM  run "taskkill /F /IM python.exe", which would kill other
REM  Python programs the user may be running.
REM ===========================================================

cd /d "%~dp0"

set "PYTHON="
if exist "runtime\python.exe"        set "PYTHON=runtime\python.exe"
if exist ".venv\Scripts\python.exe"  set "PYTHON=.venv\Scripts\python.exe"

if not defined PYTHON (
    echo.
    echo [ERROR] Python environment not found.
    echo         Please run start.bat once to complete the setup.
    echo.
    pause
    exit /b 1
)

echo.
"%PYTHON%" "scripts\msg.py" stop_header
echo.

"%PYTHON%" launcher.py stop
set "EXITCODE=%ERRORLEVEL%"

echo.
pause
endlocal
exit /b %EXITCODE%
