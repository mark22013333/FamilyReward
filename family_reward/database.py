"""SQLite 連線設定。

每一條連線都必須設定 foreign_keys / busy_timeout，
WAL 與 synchronous 則在應用程式初始化時設定一次（屬於資料庫檔案層級的設定）。

這些設定可以避免家庭中幾個人同時操作時出現 "database is locked"。
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

BUSY_TIMEOUT_MS = 5000


def register_sqlite_pragmas() -> None:
    """註冊全域的 SQLite connect 事件，為每條連線套用 PRAGMA。"""
    if getattr(register_sqlite_pragmas, "_registered", False):
        return

    @event.listens_for(Engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        # 只處理 SQLite；其他資料庫（目前沒有）不受影響。
        if not isinstance(dbapi_connection, sqlite3.Connection):
            return
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            cursor.execute("PRAGMA synchronous = NORMAL")
        finally:
            cursor.close()

    register_sqlite_pragmas._registered = True  # type: ignore[attr-defined]


def enable_wal(db_path: Path) -> None:
    """把資料庫切換到 WAL 模式（一次性設定，會寫進資料庫檔案）。

    記憶體資料庫（測試用）不支援也不需要 WAL，直接略過。
    """
    if str(db_path) == ":memory:":
        return
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        connection = sqlite3.connect(str(db_path), timeout=BUSY_TIMEOUT_MS / 1000)
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.commit()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        logger.warning("無法設定 WAL 模式：%s", exc)


def verify_database_writable(db_path: Path) -> None:
    """啟動時確認資料庫可以開啟與寫入，錯誤訊息要清楚可讀。"""
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(db_path), timeout=BUSY_TIMEOUT_MS / 1000)
        connection.close()
    except (sqlite3.Error, OSError) as exc:
        raise RuntimeError(
            "無法開啟資料庫。\n\n"
            f"請確認 {db_path.parent} 目錄存在，而且目前使用者有寫入權限。\n\n"
            "詳細資訊請查看 logs\\family-reward.log"
        ) from exc


def current_pragmas(engine: Engine) -> dict[str, object]:
    """回傳目前連線的 PRAGMA 設定，供測試驗證。"""
    with engine.connect() as connection:
        return {
            "foreign_keys": connection.execute(text("PRAGMA foreign_keys")).scalar(),
            "busy_timeout": connection.execute(text("PRAGMA busy_timeout")).scalar(),
            "journal_mode": connection.execute(text("PRAGMA journal_mode")).scalar(),
        }
