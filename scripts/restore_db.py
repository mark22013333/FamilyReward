"""還原資料庫（由 restore.bat 執行）。

安全流程：

1. 確認系統已經停止（檢查 PID 與 Port）
2. 列出可用的備份讓使用者挑選
3. 把「目前」的資料庫先備份成 pre-restore-*（後悔時還救得回來）
4. 才覆蓋資料庫

不會直接覆蓋正在使用中的資料庫。
"""

from __future__ import annotations

import shutil
import socket
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from family_reward.config import ConfigError, Settings, load_settings  # noqa: E402
from family_reward.services import backup_service  # noqa: E402

RUN_DIR = PROJECT_ROOT / "run"


def is_running(settings: Settings) -> bool:
    """檢查服務是否還在執行。"""
    pid_file = RUN_DIR / "web.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            pid = 0
        if pid > 0:
            import subprocess

            try:
                output = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                ).stdout
                if str(pid) in output:
                    return True
            except (OSError, subprocess.SubprocessError):
                pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((settings.server.host, settings.server.port)) == 0


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"設定檔有問題：{exc}")
        return 1

    print()
    print("=" * 60)
    print()
    print("     家庭任務集點樂園 - 還原資料庫")
    print()
    print("=" * 60)
    print()

    if is_running(settings):
        print("⚠️  系統目前正在執行中，不能在這個狀態還原資料庫。")
        print()
        print("請先執行 stop.bat，再重新執行 restore.bat。")
        print()
        return 1

    backups = backup_service.list_backups(settings.backup.directory)
    if not backups:
        print(f"在 {settings.backup.directory} 找不到任何備份檔。")
        print()
        return 1

    print("可以還原的備份：")
    print()
    for index, backup in enumerate(backups, start=1):
        print(f"  [{index}]  {backup.display_time}   {backup.size_mb} MB   {backup.path.name}")
    print()
    print("  [0]  取消")
    print()

    try:
        raw = input("請輸入要還原的編號：").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。")
        return 1

    if raw in ("", "0"):
        print("\n已取消，沒有做任何變更。\n")
        return 0

    try:
        choice = int(raw)
        selected = backups[choice - 1]
    except (ValueError, IndexError):
        print("\n編號不正確，已取消。\n")
        return 1

    print()
    print(f"即將用以下備份覆蓋目前的資料庫：\n\n    {selected.path.name}\n")
    try:
        confirm = input("確定要還原嗎？(輸入 yes 繼續)：").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。")
        return 1

    if confirm != "yes":
        print("\n已取消，沒有做任何變更。\n")
        return 0

    # 先把現在的資料庫備份起來，還原後後悔還救得回來。
    if settings.database.path.exists():
        try:
            safety = backup_service.create_backup(
                settings.database.path,
                settings.backup.directory,
                tz_name=settings.app.timezone,
                prefix="pre-restore-",
            )
            print(f"\n已經把目前的資料庫備份為：{safety.name}")
        except (OSError, RuntimeError) as exc:
            print(f"\n無法備份目前的資料庫：{exc}")
            print("為了安全起見，還原已中止。\n")
            return 1

    try:
        # WAL / SHM 是舊資料庫的殘留，一併清掉避免混到新資料。
        for suffix in ("-wal", "-shm"):
            leftover = Path(str(settings.database.path) + suffix)
            leftover.unlink(missing_ok=True)

        shutil.copy2(selected.path, settings.database.path)
    except OSError as exc:
        print(f"\n還原失敗：{exc}\n")
        return 1

    print()
    print("還原完成！")
    print()
    print("請執行 start.bat 重新啟動系統。")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
