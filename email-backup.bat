@echo off
chcp 65001 >nul 2>&1
setlocal

REM ===========================================================
REM  Family Reward - Backup database and send it by email
REM
REM  IMPORTANT: keep this file pure ASCII with CRLF line endings.
REM  See scripts\msg.py for the reason.
REM
REM  Creates a fresh backup and emails it (SMTP settings in
REM  config\config.yaml, password in .env).
REM
REM  For Windows Task Scheduler, add the argument  /nopause
REM  so the window does not wait for a key press.
REM ===========================================================

cd /d "%~dp0"

set "NOPAUSE="
if /i "%~1"=="/nopause" set "NOPAUSE=1"

set "PYTHON="
if exist "runtime\python.exe"        set "PYTHON=runtime\python.exe"
if exist ".venv\Scripts\python.exe"  set "PYTHON=.venv\Scripts\python.exe"

if not defined PYTHON (
    echo.
    echo [ERROR] Python environment not found.
    echo         Please run start.bat once to complete the setup.
    echo.
    if not defined NOPAUSE pause
    exit /b 1
)

echo.
"%PYTHON%" "scripts\msg.py" email_backup_header
echo.

"%PYTHON%" scripts\email_backup.py
set "EXITCODE=%ERRORLEVEL%"

echo.
if not defined NOPAUSE pause
endlocal & exit /b %EXITCODE%
