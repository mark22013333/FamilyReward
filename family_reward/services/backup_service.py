"""資料庫備份。

使用 SQLite 官方的 Backup API（sqlite3.Connection.backup），
而不是直接複製檔案 —— 直接複製正在寫入的 DB 可能拿到損壞的備份。
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..utils.timezone import now_local

logger = logging.getLogger(__name__)

BACKUP_PREFIX = "family-reward-"
BACKUP_SUFFIX = ".db"


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    created_at: datetime
    size_bytes: int

    @property
    def size_mb(self) -> float:
        return round(self.size_bytes / 1024 / 1024, 2)

    @property
    def display_time(self) -> str:
        return self.created_at.strftime("%Y/%m/%d %H:%M")


def create_backup(
    db_path: Path, backup_dir: Path, *, tz_name: str = "Asia/Taipei", prefix: str = ""
) -> Path:
    """安全備份資料庫，回傳備份檔路徑。

    Args:
        prefix: 額外前綴，例如 restore 前的 "pre-restore-"。
    """
    if not db_path.exists():
        raise FileNotFoundError(f"找不到資料庫檔案：{db_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now_local(tz_name).strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"{prefix}{BACKUP_PREFIX}{timestamp}{BACKUP_SUFFIX}"

    source = sqlite3.connect(str(db_path), timeout=5.0)
    try:
        destination = sqlite3.connect(str(target))
        try:
            # SQLite Backup API：即使來源正在被寫入也能取得一致的快照。
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()

    logger.info("Database backup created: %s", target.name)
    return target


def list_backups(backup_dir: Path) -> list[BackupInfo]:
    """列出所有備份檔（新到舊）。"""
    if not backup_dir.exists():
        return []

    backups: list[BackupInfo] = []
    for path in backup_dir.glob(f"*{BACKUP_PREFIX}*{BACKUP_SUFFIX}"):
        if not path.is_file():
            continue
        stat = path.stat()
        backups.append(
            BackupInfo(
                path=path,
                created_at=datetime.fromtimestamp(stat.st_mtime),
                size_bytes=stat.st_size,
            )
        )
    return sorted(backups, key=lambda info: info.created_at, reverse=True)


def get_latest_backup(backup_dir: Path) -> BackupInfo | None:
    backups = list_backups(backup_dir)
    return backups[0] if backups else None


def days_since_last_backup(backup_dir: Path) -> int | None:
    """距離上次備份幾天；從來沒備份過回傳 None。"""
    latest = get_latest_backup(backup_dir)
    if latest is None:
        return None
    return (datetime.now() - latest.created_at).days
