@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM ===========================================================
REM  家庭任務集點樂園 - 啟動
REM  雙擊這個檔案就可以開始使用。
REM  複雜的流程都在 launcher.py，這個 BAT 保持很薄。
REM ===========================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo.
echo      家庭任務集點樂園 ⭐
echo.
echo ============================================================
echo.
echo 正在準備...
echo.

REM --- 建立必要目錄 ---
if not exist "data"   mkdir "data"
if not exist "logs"   mkdir "logs"
if not exist "backup" mkdir "backup"
if not exist "run"    mkdir "run"

REM --- 檢查設定檔 ---
if not exist "config\config.yaml" (
    echo [錯誤] 找不到設定檔：config\config.yaml
    echo.
    echo 請確認專案完整解壓縮。
    echo.
    pause
    exit /b 1
)

REM --- 檢查 .env ---
if not exist ".env" (
    echo [提醒] 找不到 .env，正在從 .env.example 建立...
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo.
        echo 已經建立 .env，請先開啟它並填入：
        echo.
        echo     FLASK_SECRET_KEY
        echo     ADMIN_INITIAL_PASSWORD
        echo.
        echo 填好之後再執行一次 start.bat。
        echo.
        pause
        exit /b 1
    ) else (
        echo [錯誤] 找不到 .env.example，無法建立 .env。
        echo.
        pause
        exit /b 1
    )
)

REM --- 找 Python ---
REM 順序：portable runtime -> .venv -> py -> python
set "PYTHON="

if exist "runtime\python.exe" (
    set "PYTHON=runtime\python.exe"
    echo 使用內建 Python runtime。
    goto :python_found
)

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
    goto :python_found
)

echo 第一次啟動，正在建立 Python 虛擬環境...
echo （這個步驟只有第一次需要，請稍等一下）
echo.

set "BOOTSTRAP="
py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "BOOTSTRAP=py -3"
) else (
    python --version >nul 2>&1
    if not errorlevel 1 (
        set "BOOTSTRAP=python"
    )
)

if "!BOOTSTRAP!"=="" (
    echo.
    echo [錯誤] 找不到 Python。
    echo.
    echo 請先安裝 Python 3.10 或更新版本：
    echo.
    echo     https://www.python.org/downloads/
    echo.
    echo 安裝時請務必勾選：
    echo.
    echo     Add Python to PATH
    echo.
    pause
    exit /b 1
)

!BOOTSTRAP! -m venv .venv
if errorlevel 1 (
    echo.
    echo [錯誤] 建立虛擬環境失敗。
    echo.
    pause
    exit /b 1
)

set "PYTHON=.venv\Scripts\python.exe"

echo 正在安裝需要的套件...
echo.
"%PYTHON%" -m pip install --upgrade pip --quiet
"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [錯誤] 套件安裝失敗。
    echo.
    echo 請確認網路連線正常後再試一次。
    echo.
    pause
    exit /b 1
)

REM 記錄目前 requirements 的內容，之後有變更才重裝。
copy /y "requirements.txt" "run\requirements.installed" >nul

:python_found

REM --- 如果 requirements.txt 有更新，重新安裝套件 ---
if exist "run\requirements.installed" (
    fc /b "requirements.txt" "run\requirements.installed" >nul 2>&1
    if errorlevel 1 (
        echo 偵測到套件清單有變更，正在更新...
        echo.
        "%PYTHON%" -m pip install -r requirements.txt --quiet
        if errorlevel 1 (
            echo.
            echo [錯誤] 套件更新失敗。
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

REM --- 交給 launcher.py：Migration + Waitress + Cloudflare ---
"%PYTHON%" launcher.py start
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo 啟動沒有成功。詳細資訊請查看：
    echo.
    echo     logs\family-reward.log
    echo.
    pause
    exit /b %EXITCODE%
)

endlocal
