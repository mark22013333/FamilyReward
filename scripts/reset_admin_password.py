"""重設管理員密碼。

用途：忘記後台密碼、或是改了 .env 卻發現沒有生效時使用。

背景：`.env` 的 ADMIN_INITIAL_PASSWORD 只在「第一次建立帳號」時生效，
之後改它不會套用到既有帳號 —— 設定檔不應該有能力隨時覆寫密碼。
所以要重設密碼，就用這支腳本明確地做。

用法：
    .venv\\Scripts\\python.exe scripts\\reset_admin_password.py

會互動式詢問要重設哪個帳號、以及新密碼（輸入時不顯示）。
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from family_reward import create_app  # noqa: E402
from family_reward.config import ConfigError  # noqa: E402
from family_reward.extensions import db  # noqa: E402
from family_reward.models import ActorType, AdminUser, AuditAction  # noqa: E402
from family_reward.services import audit_service  # noqa: E402
from family_reward.services.admin_service import MIN_PASSWORD_LENGTH  # noqa: E402

LINE = "=" * 62


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    print()
    print(LINE)
    print("  重設管理員密碼")
    print(LINE)
    print()

    try:
        app = create_app()
    except (ConfigError, RuntimeError) as exc:
        print(f"無法啟動：{exc}")
        return 1

    with app.app_context():
        admins = list(db.session.execute(db.select(AdminUser)).scalars())

        if not admins:
            print("資料庫裡還沒有任何管理員帳號。")
            print("請先執行 start.bat，系統會自動建立。")
            print()
            return 1

        if len(admins) == 1:
            target = admins[0]
            print(f"要重設的帳號：{target.username}")
        else:
            print("目前的管理員帳號：")
            print()
            for index, admin in enumerate(admins, start=1):
                print(f"  [{index}] {admin.username}")
            print()
            try:
                raw = input("請輸入編號：").strip()
                target = admins[int(raw) - 1]
            except (EOFError, KeyboardInterrupt):
                print("\n已取消。")
                return 1
            except (ValueError, IndexError):
                print("\n編號不正確，已取消。")
                return 1

        print()
        try:
            new_password = getpass.getpass("請輸入新密碼（輸入時不會顯示）：")
            confirm = getpass.getpass("請再輸入一次：")
        except (EOFError, KeyboardInterrupt):
            print("\n已取消。")
            return 1

        if new_password != confirm:
            print("\n兩次輸入的密碼不一樣，已取消。")
            return 1

        if len(new_password) < MIN_PASSWORD_LENGTH:
            print(f"\n密碼至少要 {MIN_PASSWORD_LENGTH} 個字元，已取消。")
            return 1

        try:
            target.set_password(new_password, is_initial=False)
            audit_service.record(
                AuditAction.CHANGE_PASSWORD,
                actor_type=ActorType.SYSTEM,
                actor_id=target.id,
                actor_name=target.username,
                entity_type="ADMIN_USER",
                entity_id=target.id,
                description=f"以 reset_admin_password.py 重設「{target.username}」的密碼",
            )
            db.session.commit()
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            print(f"\n重設失敗：{exc}")
            return 1

        print()
        print(f"完成！帳號「{target.username}」的密碼已經重設。")
        print()
        print("現在可以用新密碼登入後台了。")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
