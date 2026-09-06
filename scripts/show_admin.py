"""查詢目前的管理員帳號。

用途：忘記後台帳號時可以查出來。
刻意「只顯示帳號」，不顯示也無法還原密碼（密碼是 Hash，本來就取不回來）。

用法：
    .venv\\Scripts\\python.exe scripts\\show_admin.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from family_reward.config import ConfigError, load_settings  # noqa: E402


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"設定檔有問題：{exc}")
        return 1

    if not settings.database.path.exists():
        print(f"找不到資料庫：{settings.database.path}")
        print("請先執行一次 start.bat。")
        return 1

    # 這裡刻意直接用 sqlite3 讀取，不啟動整個 Flask app，
    # 這樣即使服務正在執行也能安全查詢。
    import sqlite3

    connection = sqlite3.connect(str(settings.database.path))
    try:
        rows = list(
            connection.execute(
                "SELECT username, active, must_change_password, last_login_at "
                "FROM admin_user ORDER BY id"
            )
        )
    except sqlite3.Error as exc:
        print(f"讀取資料庫失敗：{exc}")
        return 1
    finally:
        connection.close()

    if not rows:
        print("資料庫裡還沒有任何管理員帳號。")
        print("執行 start.bat 時會依 config.yaml 的 admin.initial_username 自動建立。")
        return 1

    print()
    print("目前的管理員帳號：")
    print()
    for username, active, must_change, last_login in rows:
        status = "使用中" if active else "已停用"
        note = "（仍使用初始密碼，請盡快修改）" if must_change else ""
        print(f"    {username}    [{status}]  {note}")
        if last_login:
            print(f"        最後登入：{last_login}")
    print()

    # 「登不進去」有很大機率是連錯 port，所以一併顯示正確網址。
    host = settings.server.host
    port = settings.server.port
    print("後台登入網址：")
    print()
    print(f"    http://{host}:{port}/login/admin")
    print()

    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.5)
        running = sock.connect_ex((host, port)) == 0

    if running:
        print("    ✓ 服務正在執行中")
    else:
        print("    ✗ 服務沒有在執行 —— 請先執行 start.bat")
    print()

    if settings.cloudflare.hostname:
        print(f"對外網址：https://{settings.cloudflare.hostname}/login/admin")
        print()

    print("忘記密碼請執行：")
    print()
    print("    .venv\\Scripts\\python.exe scripts\\reset_admin_password.py")
    print()
    print("※ .env 的 ADMIN_INITIAL_PASSWORD 只在「第一次建立帳號」時生效，")
    print("  改了它不會套用到既有帳號。")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
