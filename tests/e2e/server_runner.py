"""E2E 測試專用的伺服器啟動腳本。

用真的 Waitress 啟動（和正式環境相同的方式），
但資料庫、log、port 都由 FAMILY_REWARD_CONFIG 指定的設定檔決定。
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from waitress import serve  # noqa: E402

from family_reward import create_app  # noqa: E402
from family_reward.config import load_settings  # noqa: E402
from family_reward.extensions import db  # noqa: E402
from family_reward.seed import initialize  # noqa: E402


def main() -> None:
    settings = load_settings()
    app = create_app(settings=settings, setup_log=False)

    with app.app_context():
        # E2E 用的暫存資料庫直接建表，不必跑 Alembic。
        db.create_all()

    initialize(app)

    serve(
        app,
        host=settings.server.host,
        port=settings.server.port,
        threads=settings.server.threads,
        ident="FamilyReward",
    )


if __name__ == "__main__":
    main()
