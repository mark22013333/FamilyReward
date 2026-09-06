"""備份資料庫（由 backup.bat 執行）。

使用 SQLite 官方的 Backup API，即使系統正在使用中也能取得一致的快照。
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from family_reward.config import ConfigError, load_settings  # noqa: E402
from family_reward.services import backup_service  # noqa: E402


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"設定檔有問題：{exc}")
        return 1

    if not settings.database.path.exists():
        print(f"找不到資料庫檔案：{settings.database.path}")
        print("請先啟動過系統一次（執行 start.bat）。")
        return 1

    try:
        target = backup_service.create_backup(
            settings.database.path,
            settings.backup.directory,
            tz_name=settings.app.timezone,
        )
    except (OSError, RuntimeError) as exc:
        print(f"備份失敗：{exc}")
        return 1

    size_mb = round(target.stat().st_size / 1024 / 1024, 2)
    print()
    print("備份完成！")
    print()
    print(f"    檔案：{target.name}")
    print(f"    位置：{target.parent}")
    print(f"    大小：{size_mb} MB")
    print()

    backups = backup_service.list_backups(settings.backup.directory)
    print(f"目前共有 {len(backups)} 個備份檔。")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
