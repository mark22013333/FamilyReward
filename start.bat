@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM ===========================================================
REM  Family Reward - Start
REM
REM  IMPORTANT: This file must stay pure ASCII and use CRLF.
REM  On a Big5 (CP950) machine cmd.exe reads the file using the
REM  system code page, so UTF-8 Chinese bytes in this file would
REM  be mis-decoded and break parsing. All Chinese text shown to
REM  the user is printed by Python (msg.py) instead.
REM ===========================================================

cd /d "%~dp0"

set "MSG=scripts\msg.py"

echo.
echo ============================================================
echo.
echo      Family Reward
echo.
echo ============================================================
echo.

if not exist "data"   mkdir "data"
if not exist "logs"   mkdir "logs"
if not exist "backup" mkdir "backup"
if not exist "run"    mkdir "run"

if not exist "config\config.yaml" (
    echo [ERROR] config\config.yaml not found.
    echo         Please make sure the project was extracted completely.
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [SETUP] Created .env from .env.example
        echo.
        echo         Please open .env and fill in:
        echo             FLASK_SECRET_KEY
        echo             ADMIN_INITIAL_PASSWORD
        echo.
        echo         Then run start.bat again.
        echo.
        pause
        exit /b 1
    ) else (
        echo [ERROR] Neither .env nor .env.example was found.
        echo.
        pause
        exit /b 1
    )
)

REM --- Locate Python: runtime -^> .venv -^> py -^> python ---
set "PYTHON="

if exist "runtime\python.exe" (
    set "PYTHON=runtime\python.exe"
    goto :python_found
)

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
    goto :python_found
)

echo First run: creating the Python virtual environment.
echo This only happens once and may take a few minutes.
echo.

set "BOOTSTRAP="
py -3 --version >nul 2>&1
if not errorlevel 1 set "BOOTSTRAP=py -3"

if not defined BOOTSTRAP (
    python --version >nul 2>&1
    if not errorlevel 1 set "BOOTSTRAP=python"
)

if not defined BOOTSTRAP (
    echo.
    echo [ERROR] Python was not found.
    echo.
    echo         Please install Python 3.10 or newer:
    echo             https://www.python.org/downloads/
    echo.
    echo         During installation, be sure to check:
    echo             Add Python to PATH
    echo.
    pause
    exit /b 1
)

%BOOTSTRAP% -m venv .venv
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to create the virtual environment.
    echo.
    pause
    exit /b 1
)

set "PYTHON=.venv\Scripts\python.exe"

echo Installing required packages...
echo.
"%PYTHON%" -m pip install --upgrade pip --quiet
"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Package installation failed.
    echo         Please check your network connection and try again.
    echo.
    pause
    exit /b 1
)

copy /y "requirements.txt" "run\requirements.installed" >nul

:python_found

REM --- Reinstall packages when requirements.txt changed ---
if exist "run\requirements.installed" (
    fc /b "requirements.txt" "run\requirements.installed" >nul 2>&1
    if errorlevel 1 (
        echo Package list changed, updating...
        echo.
        "%PYTHON%" -m pip install -r requirements.txt --quiet
        if errorlevel 1 (
            echo.
            echo [ERROR] Package update failed.
            echo.
            pause
            exit /b 1
        )
        copy /y "requirements.txt" "run\requirements.installed" >nul
    )
) else (
    "%PYTHON%" -m pip install -r requirements.txt --quiet
    copy /y "requirements.txt" "run\requirements.installed" >nul
)

REM --- launcher.py handles migration, Waitress and Cloudflare ---
"%PYTHON%" launcher.py start
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    "%PYTHON%" "%MSG%" start_failed 2>nul
    if errorlevel 1 (
        echo Startup failed. See logs\family-reward.log for details.
    )
    echo.
    pause
    exit /b %EXITCODE%
)

endlocal
