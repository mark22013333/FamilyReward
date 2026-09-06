@echo off
chcp 65001 >nul 2>&1
setlocal

REM ===========================================================
REM  Family Reward - Restore database
REM
REM  IMPORTANT: keep this file pure ASCII with CRLF line endings.
REM  See scripts\msg.py for the reason.
REM
REM  restore_db.py refuses to run while the service is up, and
REM  always backs up the current database as pre-restore-* first.
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

"%PYTHON%" scripts\restore_db.py
set "EXITCODE=%ERRORLEVEL%"

echo.
pause
endlocal
exit /b %EXITCODE%
