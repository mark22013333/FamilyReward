"""建立一份新備份並寄到信箱（由 email-backup.bat 或排程執行）。

適合放進 Windows 工作排程器，或 Linux 的 systemd timer / cron，
定期把備份寄到信箱做異地保存。

用法：
    .venv\\Scripts\\python.exe scripts\\email_backup.py
    .venv/bin/python scripts/email_backup.py

成功回傳 0；設定錯誤或寄送失敗回傳 1（排程工具會記錄為失敗）。
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from family_reward.config import ConfigError, load_settings  # noqa: E402
from family_reward.services import backup_service, email_service  # noqa: E402
from family_reward.utils.logging_setup import setup_logging  # noqa: E402


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"設定檔有問題：{exc}")
        return 1

    # 排程執行時沒有人看畫面，結果也要留在 log 裡
    setup_logging(
        settings.logging.path,
        settings.logging.level,
        settings.logging.max_bytes,
        settings.logging.backup_count,
        console=False,
    )

    if not email_service.is_configured(settings):
        print("還沒有設定寄信功能。")
        print("請在 config/config.yaml 設定 email 區段，並在 .env 填入 SMTP_PASSWORD。")
        return 1

    if not settings.database.path.exists():
        print(f"找不到資料庫檔案：{settings.database.path}")
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

    try:
        recipients = email_service.send_backup(settings, target)
    except email_service.EmailError as exc:
        print(f"備份已建立（{target.name}），但寄信失敗：{exc.message}")
        return 1

    print()
    print("備份並寄出完成！")
    print()
    print(f"    檔案：{target.name}")
    print(f"    收件人：{', '.join(email_service.masked_recipients(settings))}")
    print(f"    （共 {len(recipients)} 位）")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
