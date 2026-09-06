"""應用程式啟動器。

由 start.bat 執行，負責所有比較複雜的流程，讓 BAT 保持很薄：

    讀設定 → 檢查 Port → Migration → 初始化 → 啟動 Waitress
    → 啟動 Cloudflare Tunnel → 寫 PID → 等待 → 優雅關閉

任一步驟失敗都會顯示清楚的中文訊息，並回傳非 0 的 exit code。
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from family_reward.config import ConfigError, Settings, load_settings  # noqa: E402
from family_reward.utils.logging_setup import setup_logging  # noqa: E402

logger = logging.getLogger("family_reward.launcher")

RUN_DIR = PROJECT_ROOT / "run"
WEB_PID_FILE = RUN_DIR / "web.pid"
CLOUDFLARED_PID_FILE = RUN_DIR / "cloudflared.pid"
#: Windows 沒有 SIGTERM，stop.bat 用這個旗標檔請求優雅關閉。
SHUTDOWN_FLAG_FILE = RUN_DIR / "shutdown.request"

SEPARATOR = "=" * 60


class LauncherError(Exception):
    """啟動流程失敗，訊息可以直接顯示給使用者。"""


# --------------------------------------------------------------------------
# 基本工具
# --------------------------------------------------------------------------


def ensure_directories(settings: Settings) -> None:
    """建立必要的目錄。"""
    for path in (
        settings.database.path.parent,
        settings.logging.path.parent,
        settings.backup.directory,
        RUN_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def read_pid(path: Path) -> int | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
        return int(value) if value else None
    except (OSError, ValueError):
        return None


def write_pid(path: Path, pid: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid), encoding="utf-8")


def process_alive(pid: int) -> bool:
    """檢查行程是否還活著（Windows 使用 tasklist）。"""
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            output = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout
            return str(pid) in output
        except (OSError, subprocess.SubprocessError):
            return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def request_shutdown() -> None:
    """建立停止旗標，讓正在執行的 launcher 自己優雅收尾。"""
    SHUTDOWN_FLAG_FILE.parent.mkdir(parents=True, exist_ok=True)
    SHUTDOWN_FLAG_FILE.write_text("stop", encoding="utf-8")


def clear_shutdown_request() -> None:
    SHUTDOWN_FLAG_FILE.unlink(missing_ok=True)


def _watch_shutdown_flag(server, interval: float = 0.5) -> None:  # noqa: ANN001
    """背景監看停止旗標；一出現就關閉 server，讓 run() 正常回傳。"""
    while True:
        if SHUTDOWN_FLAG_FILE.exists():
            logger.info("Shutdown requested via flag file")
            clear_shutdown_request()
            server.close()
            return
        time.sleep(interval)


# --------------------------------------------------------------------------
# 啟動前檢查
# --------------------------------------------------------------------------


def check_already_running(settings: Settings) -> None:
    """避免使用者連按兩次 start.bat 啟動兩份。"""
    pid = read_pid(WEB_PID_FILE)
    if pid and process_alive(pid):
        raise LauncherError(
            f"{settings.app.name}已經在執行中 ⭐\n\n"
            f"  http://{settings.server.host}:{settings.server.port}\n\n"
            "如果要重新啟動，請先執行 stop.bat。"
        )

    if is_port_in_use(settings.server.host, settings.server.port):
        raise LauncherError(
            f"Port {settings.server.port} 已被其他程式使用。\n\n"
            "請修改 config\\config.yaml 的 server.port，或先關閉佔用的程式。"
        )


def run_migrations(settings: Settings) -> None:
    """執行 Alembic migration。失敗就不啟動 Web Server。"""
    logger.info("Running database migrations...")
    env = os.environ.copy()
    env["FLASK_APP"] = "app.py"
    env["APP_ENV"] = settings.app.env

    result = subprocess.run(
        [sys.executable, "-m", "flask", "db", "upgrade"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )

    if result.returncode != 0:
        logger.error("Migration failed:\n%s\n%s", result.stdout, result.stderr)
        raise LauncherError(
            "資料庫更新失敗。\n\n"
            "請查看：logs\\family-reward.log\n\n"
            "常見原因：data 目錄沒有寫入權限，或資料庫檔案損毀。"
        )

    logger.info("Database migrations completed")


# --------------------------------------------------------------------------
# Cloudflare Tunnel
# --------------------------------------------------------------------------


def start_cloudflared(settings: Settings) -> subprocess.Popen | None:
    """啟動 Cloudflare Tunnel。

    失敗時只警告，不影響本機服務（需求書第 163 節）。
    """
    if not settings.cloudflare.enabled:
        return None

    executable = settings.cloudflare.executable
    config = settings.cloudflare.config

    if not executable.exists():
        logger.warning("找不到 cloudflared 執行檔：%s", executable)
        print(f"\n⚠️  找不到 cloudflared：{executable}")
        print("   本機服務仍然可以正常使用。\n")
        return None

    if not config.exists():
        logger.warning("找不到 Cloudflare 設定檔：%s", config)
        print(f"\n⚠️  找不到 Cloudflare 設定檔：{config}")
        print("   本機服務仍然可以正常使用。\n")
        return None

    try:
        process = subprocess.Popen(
            [str(executable), "tunnel", "--config", str(config), "run"],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        logger.warning("Cloudflare Tunnel 啟動失敗：%s", exc)
        print("\n⚠️  網站已在本機啟動，但 Cloudflare Tunnel 啟動失敗。")
        print("   請查看 Log。\n")
        return None

    # 給它一點時間，如果立刻掛掉就代表設定有問題。
    time.sleep(2)
    if process.poll() is not None:
        logger.warning("Cloudflare Tunnel 啟動後立刻結束（exit=%s）", process.returncode)
        print("\n⚠️  網站已在本機啟動，但 Cloudflare Tunnel 啟動失敗。")
        print(f"   本機：http://{settings.server.host}:{settings.server.port}")
        print("   請查看 Log。\n")
        return None

    write_pid(CLOUDFLARED_PID_FILE, process.pid)
    logger.info("Cloudflare Tunnel started (pid=%s)", process.pid)
    return process


def stop_cloudflared(process: subprocess.Popen | None) -> None:
    """優雅結束 cloudflared，逾時才強制關閉。"""
    if process is None or process.poll() is not None:
        CLOUDFLARED_PID_FILE.unlink(missing_ok=True)
        return

    logger.info("Stopping Cloudflare Tunnel...")
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        logger.warning("Cloudflare Tunnel 未在時間內結束，強制關閉。")
        process.kill()
    CLOUDFLARED_PID_FILE.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# 畫面輸出
# --------------------------------------------------------------------------


def print_banner(settings: Settings, cloudflare_running: bool) -> None:
    hostname = settings.cloudflare.hostname
    print()
    print(SEPARATOR)
    print()
    print(f"     {settings.app.name} ⭐")
    print()
    print(SEPARATOR)
    print()
    print("本機網址：")
    print()
    print(f"    http://{settings.server.host}:{settings.server.port}")
    print()
    print("SQLite：")
    print()
    print(f"    {settings.database.path}")
    print()
    print("Log：")
    print()
    print(f"    {settings.logging.path}")
    print()
    if settings.cloudflare.enabled:
        print("Cloudflare：")
        print()
        if cloudflare_running:
            print("    已啟動")
            if hostname:
                print()
                print("公開網址：")
                print()
                print(f"    https://{hostname}")
        else:
            print("    ⚠️ 啟動失敗（本機服務仍可正常使用）")
        print()
    print(SEPARATOR)
    print()
    print("要停止服務，請執行 stop.bat，或在這個視窗按 Ctrl+C。")
    print()


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------


def serve(settings: Settings) -> int:
    """啟動 Waitress 並等待結束訊號。"""
    from waitress import create_server

    from family_reward import create_app
    from family_reward.seed import initialize

    app = create_app(settings=settings, setup_log=False)
    initialize(app)

    server = create_server(
        app,
        host=settings.server.host,
        port=settings.server.port,
        threads=settings.server.threads,
        # ident 會寫進 HTTP 的 Server header，只能是 latin-1，
        # 因此這裡固定用英文，不可以帶入中文的 app.name。
        # 順便不揭露 Waitress 版本。
        ident="FamilyReward",
    )

    # 清掉上一次殘留的旗標，避免剛啟動就被關掉。
    clear_shutdown_request()

    cloudflare = start_cloudflared(settings)
    write_pid(WEB_PID_FILE, os.getpid())

    threading.Thread(
        target=_watch_shutdown_flag, args=(server,), daemon=True
    ).start()

    logger.info(
        "Application startup: serving on http://%s:%s (threads=%s)",
        settings.server.host,
        settings.server.port,
        settings.server.threads,
    )
    print_banner(settings, cloudflare is not None)

    def handle_signal(signum, frame):  # noqa: ANN001, ANN202
        """收到停止訊號時讓 waitress 從 run() 回傳，走正常的收尾流程。"""
        logger.info("Received signal %s, shutting down...", signum)
        # 不能直接在 signal handler 裡呼叫 close()（會卡住 select loop），
        # 改用另一條 thread 觸發。
        threading.Thread(target=server.close, daemon=True).start()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    if os.name == "nt":
        # Windows 上 taskkill（不加 /F）送的是 CTRL_BREAK/WM_CLOSE，
        # 這裡一併攔截，讓 stop.bat 也能優雅關閉。
        with contextlib.suppress(AttributeError, ValueError, OSError):
            signal.signal(signal.SIGBREAK, handle_signal)  # type: ignore[attr-defined]

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")
    except OSError as exc:
        logger.exception("Web server error: %s", exc)
        return 1
    finally:
        logger.info("Application shutdown: stopping services...")
        stop_cloudflared(cloudflare)
        WEB_PID_FILE.unlink(missing_ok=True)
        clear_shutdown_request()
        logger.info("Application shutdown complete")
        print("\n服務已經停止。掰掰！👋\n")

    return 0


def stop() -> int:
    """停止正在執行的服務（只關掉自己記錄的 PID）。"""
    stopped = False

    web_pid = read_pid(WEB_PID_FILE)

    # --- 先請 launcher 自己優雅收尾 ---
    # 它會一併關閉 Waitress 與 cloudflared，所以不必分別去砍。
    if web_pid and process_alive(web_pid):
        print(f"正在停止 Web Server（PID {web_pid}）...")
        try:
            if os.name == "nt":
                # Windows 沒有 SIGTERM。對背景執行（沒有主控台）的行程，
                # `taskkill` 不加 /F 送的是 WM_CLOSE，Python 收不到，
                # 因此改用旗標檔請求關閉。
                request_shutdown()
            else:
                os.kill(web_pid, signal.SIGTERM)

            # 最多等 15 秒讓它把 SQLite 與 cloudflared 收乾淨。
            for _ in range(30):
                if not process_alive(web_pid):
                    break
                time.sleep(0.5)

            if process_alive(web_pid):
                print("  沒有在時間內結束，改為強制關閉。")
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(web_pid)],
                        capture_output=True,
                        timeout=10,
                    )
                else:
                    os.kill(web_pid, signal.SIGKILL)
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"  停止 Web Server 時發生問題：{exc}")

        WEB_PID_FILE.unlink(missing_ok=True)
        stopped = True
    elif web_pid:
        print("Web Server 沒有在執行（清除舊的 PID 檔）。")
        WEB_PID_FILE.unlink(missing_ok=True)

    # --- 萬一 cloudflared 被留下來（例如 launcher 被強制關閉）就補收尾 ---
    cf_pid = read_pid(CLOUDFLARED_PID_FILE)
    if cf_pid and process_alive(cf_pid):
        print(f"正在停止 Cloudflare Tunnel（PID {cf_pid}）...")
        try:
            subprocess.run(
                ["taskkill", "/F", "/PID", str(cf_pid)]
                if os.name == "nt"
                else ["kill", "-9", str(cf_pid)],
                capture_output=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"  停止 Cloudflare Tunnel 時發生問題：{exc}")
        stopped = True
    CLOUDFLARED_PID_FILE.unlink(missing_ok=True)

    # 一定要清掉旗標，否則下一次 start.bat 剛啟動就會被自己關掉。
    clear_shutdown_request()

    if stopped:
        print("\n服務已經停止。\n")
    else:
        print("\n目前沒有正在執行的服務。\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="家庭任務集點樂園啟動器")
    parser.add_argument(
        "command",
        nargs="?",
        default="start",
        choices=["start", "stop", "migrate"],
        help="start=啟動服務、stop=停止服務、migrate=只執行資料庫更新",
    )
    args = parser.parse_args()

    try:
        settings = load_settings()
    except ConfigError as exc:
        print()
        print("設定檔有問題，無法啟動：")
        print()
        print(f"  {exc}")
        print()
        print("請檢查 config\\config.yaml 與 .env。")
        print()
        return 1

    ensure_directories(settings)
    setup_logging(
        settings.logging.path,
        level=settings.logging.level,
        max_bytes=settings.logging.max_bytes,
        backup_count=settings.logging.backup_count,
    )

    if args.command == "stop":
        return stop()

    try:
        if args.command == "migrate":
            run_migrations(settings)
            print("資料庫更新完成。")
            return 0

        check_already_running(settings)
        run_migrations(settings)
        return serve(settings)

    except LauncherError as exc:
        print()
        print(str(exc))
        print()
        logger.error("Startup aborted: %s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected startup error: %s", exc)
        print()
        print("啟動時發生未預期的錯誤。")
        print()
        print(f"請查看：{settings.logging.path}")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
