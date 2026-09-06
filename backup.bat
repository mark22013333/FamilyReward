@echo off
chcp 65001 >nul 2>&1
setlocal

REM ===========================================================
REM  Family Reward - Backup database
REM
REM  IMPORTANT: keep this file pure ASCII with CRLF line endings.
REM  See scripts\msg.py for the reason.
REM
REM  Uses the SQLite Backup API, so it is safe to run even while
REM  the application is running.
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
"%PYTHON%" "scripts\msg.py" backup_header
echo.

"%PYTHON%" scripts\backup_db.py
set "EXITCODE=%ERRORLEVEL%"

echo.
pause
endlocal
exit /b %EXITCODE%
