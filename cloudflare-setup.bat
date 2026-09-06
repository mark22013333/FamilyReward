@echo off
chcp 65001 >nul 2>&1
setlocal

REM ===========================================================
REM  Family Reward - Cloudflare Tunnel setup helper
REM
REM  IMPORTANT: keep this file pure ASCII with CRLF line endings.
REM  See scripts\msg.py for the reason.
REM
REM  This only inspects and explains. It never changes anything
REM  on your Cloudflare account, because publishing a hostname
REM  is an outward-facing change you should confirm yourself.
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

"%PYTHON%" scripts\cloudflare_setup.py
set "EXITCODE=%ERRORLEVEL%"

echo.
pause
endlocal
exit /b %EXITCODE%
