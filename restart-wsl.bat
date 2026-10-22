@echo off
chcp 65001 >nul 2>&1
setlocal

REM ===========================================================
REM  Family Reward - Restart the service running in WSL
REM
REM  IMPORTANT: keep this file pure ASCII with CRLF line endings.
REM  See scripts\msg.py for the reason. (Messages here stay in
REM  English because this Windows folder has no Python to run
REM  msg.py; the app itself runs inside WSL.)
REM
REM  Restarts the systemd service and checks that it came back.
REM  Run it after changing config\config.yaml or .env in WSL.
REM
REM  Usage:
REM    restart-wsl.bat              (default distro SplitSwan)
REM    restart-wsl.bat Ubuntu       (another WSL distro)
REM    restart-wsl.bat SplitSwan /nopause
REM ===========================================================

set "DISTRO=SplitSwan"
if not "%~1"=="" if /i not "%~1"=="/nopause" set "DISTRO=%~1"

set "NOPAUSE="
if /i "%~1"=="/nopause" set "NOPAUSE=1"
if /i "%~2"=="/nopause" set "NOPAUSE=1"

set "SERVICE=familyreward-web"

REM wsl.exe prints UTF-16 by default, which shows up garbled here.
set "WSL_UTF8=1"

REM wsl.exe returns negative exit codes (e.g. distro not found),
REM which "if errorlevel 1" does not catch, so compare with NEQ 0.

where wsl >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] wsl.exe not found. Is WSL installed?
    echo.
    set "EXITCODE=1"
    goto :end
)

echo.
echo Restarting %SERVICE% in WSL distro "%DISTRO%" ...

wsl -d %DISTRO% -u root -- systemctl restart %SERVICE%
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Restart command failed. Check the distro name:
    echo         wsl -l -v
    echo.
    set "EXITCODE=1"
    goto :end
)

REM Give Waitress a moment to bind the port before checking.
REM (ping instead of timeout: timeout fails without a console.)
ping -n 6 127.0.0.1 >nul

wsl -d %DISTRO% -- systemctl is-active --quiet %SERVICE%
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] %SERVICE% did not come back up. Recent log:
    echo.
    wsl -d %DISTRO% -- journalctl -u %SERVICE% -n 30 --no-pager
    echo.
    set "EXITCODE=1"
    goto :end
)

echo.
echo [OK] %SERVICE% is running.
echo.
echo     Local:  http://127.0.0.1:19880  (inside WSL)
echo     Public: https://familyreward.longhopick.com
echo.
set "EXITCODE=0"

:end
if not defined NOPAUSE pause
endlocal & exit /b %EXITCODE%
