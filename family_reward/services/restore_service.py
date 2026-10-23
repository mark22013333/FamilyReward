"""從後台上傳備份並還原資料庫。

和 restore.bat 不同，這裡是在「系統執行中」還原，所以每一步都要能失敗而不傷到現有資料：

    1. 上傳檔先存到暫存區（.db，或寄信功能寄出的 .zip）
    2. 驗證：SQLite 格式、integrity_check、必要資料表、Alembic 版本
    3. 備份比目前程式舊 → 在「暫存複本」上跑 migration（子行程）
    4. 把目前的資料庫備份成 pre-restore-*（後悔還救得回來）
    5. 用 SQLite Backup API 把暫存複本寫進正在使用的資料庫
    6. 重新初始化（管理員、成就定義、預設設定）

1 ~ 3 任何一步失敗，正在使用的資料庫完全不會被動到。

Migration 用子行程跑，原因：Alembic 的 env.py 會呼叫 logging.fileConfig()，
在 Web 行程裡執行會把整個應用程式的 log 設定換掉（檔案 log 會消失）。
"""

from __future__ import annotations

import logging
import os
import sqlite3
import subprocess
import sys
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path

from flask import Flask

from ..config import PROJECT_ROOT, Settings
from ..database import BUSY_TIMEOUT_MS, enable_wal
from ..exceptions import AppError
from ..extensions import db
from ..utils.timezone import now_local
from . import backup_service

logger = logging.getLogger(__name__)

#: 家庭系統的資料庫通常不到 1 MB，50 MB 已經非常寬鬆。
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

SQLITE_HEADER = b"SQLite format 3\x00"
REQUIRED_TABLES = frozenset({"alembic_version", "admin_user", "child"})
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
STAGING_DIR_NAME = ".restore-staging"

#: 同一時間只允許一個還原（Waitress 有多條執行緒）
_restore_lock = threading.Lock()


class RestoreError(AppError):
    """還原失敗。message 可以直接顯示給家長看。"""

    default_message = "還原沒有成功，目前的資料沒有被變更。"


@dataclass(frozen=True)
class RestoreResult:
    source_name: str
    safety_backup_name: str | None
    migrated_from: str | None
    child_count: int


# --------------------------------------------------------------------------
# 驗證
# --------------------------------------------------------------------------


def _head_revision() -> str:
    from alembic.script import ScriptDirectory

    head = ScriptDirectory(str(MIGRATIONS_DIR)).get_current_head()
    if head is None:  # pragma: no cover - 專案一定有 migration
        raise RestoreError("找不到資料庫版本資訊，無法還原。")
    return head


def _known_revisions() -> set[str]:
    from alembic.script import ScriptDirectory

    return {script.revision for script in ScriptDirectory(str(MIGRATIONS_DIR)).walk_revisions()}


def _extract_zip(zip_path: Path, target: Path) -> str:
    """從寄信功能產生的 ZIP 取出 .db，回傳裡面的檔名。"""
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = [
                info for info in archive.infolist()
                if not info.is_dir() and info.filename.lower().endswith(".db")
            ]
            if len(members) != 1:
                raise RestoreError("ZIP 裡面要剛好有一個 .db 備份檔。")
            member = members[0]
            # 先看宣告的大小，再邊讀邊數，避免壓縮炸彈
            if member.file_size > MAX_UPLOAD_BYTES:
                raise RestoreError("備份檔太大了，不像是這個系統的備份。")
            written = 0
            with archive.open(member) as source, target.open("wb") as destination:
                while chunk := source.read(1024 * 1024):
                    written += len(chunk)
                    if written > MAX_UPLOAD_BYTES:
                        raise RestoreError("備份檔太大了，不像是這個系統的備份。")
                    destination.write(chunk)
            return Path(member.filename).name
    except zipfile.BadZipFile as exc:
        raise RestoreError("ZIP 檔案損壞，無法讀取。") from exc


def _read_revision(path: Path) -> str:
    """驗證檔案是這個系統的備份，回傳它的 Alembic 版本。"""
    with path.open("rb") as handle:
        if handle.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
            raise RestoreError("這不是資料庫備份檔（.db），請確認選對檔案。")

    try:
        # 唯讀開啟，驗證過程不會改到上傳的檔案
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise RestoreError("備份檔已經損壞，無法還原。")

            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            if not REQUIRED_TABLES <= tables:
                raise RestoreError("這個資料庫不是「家庭任務集點樂園」的備份。")

            row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        finally:
            connection.close()
    except sqlite3.DatabaseError as exc:
        raise RestoreError("備份檔已經損壞，無法還原。") from exc

    if not row:
        raise RestoreError("這個備份沒有版本資訊，無法還原。")
    revision = str(row[0])
    if revision not in _known_revisions():
        raise RestoreError(
            "這個備份來自比目前更新的版本。請先更新程式（git pull）再還原。"
        )
    return revision


def _migrate_file(path: Path, settings: Settings, revision: str = "head") -> None:
    """在子行程裡把指定的資料庫檔案升級到 revision。"""
    staging = path.parent
    config_path = staging / "migrate-config.yaml"
    config_path.write_text(
        "app:\n"
        f"  timezone: \"{settings.app.timezone}\"\n"
        "database:\n"
        f"  path: \"{path.as_posix()}\"\n"
        "logging:\n"
        f"  path: \"{(staging / 'migrate.log').as_posix()}\"\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["FLASK_APP"] = "app.py"
    env["FAMILY_REWARD_CONFIG"] = str(config_path)
    # 只是要跑 migration，不需要正式環境的 SECRET_KEY 檢查
    env["APP_ENV"] = "testing"

    result = subprocess.run(
        [sys.executable, "-m", "flask", "db", "upgrade", revision],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    if result.returncode != 0:
        logger.error("Restore migration failed:\n%s\n%s", result.stdout, result.stderr)
        raise RestoreError("備份的資料庫版本升級失敗，目前的資料沒有被變更。")


# --------------------------------------------------------------------------
# 還原
# --------------------------------------------------------------------------


def _staging_dir(settings: Settings) -> Path:
    staging = settings.backup.directory / STAGING_DIR_NAME
    staging.mkdir(parents=True, exist_ok=True)
    return staging


def _clear_staging(staging: Path) -> None:
    for item in staging.iterdir():
        if item.is_file():
            item.unlink(missing_ok=True)


def _copy_into_live_database(source: Path, live: Path) -> None:
    """用 SQLite Backup API 把 source 寫進正在使用的資料庫。

    不直接覆蓋檔案：其他執行緒可能正開著連線，覆蓋檔案會讓它們讀到半新半舊的資料。
    Backup API 會取得寫入鎖，整個資料庫一次換成新內容。
    """
    db.session.remove()
    db.engine.dispose()

    source_connection = sqlite3.connect(str(source))
    try:
        live_connection = sqlite3.connect(str(live), timeout=BUSY_TIMEOUT_MS / 1000)
        try:
            source_connection.backup(live_connection)
        finally:
            live_connection.close()
    finally:
        source_connection.close()

    enable_wal(live)
    # 讓之後的請求都拿新的連線，不重用還原前的連線
    db.engine.dispose()


def restore_upload(
    app: Flask, upload_path: Path, original_name: str, *, actor_name: str
) -> RestoreResult:
    """還原家長上傳的備份。upload_path 是已經存到暫存區的上傳檔。"""
    settings: Settings = app.settings  # type: ignore[attr-defined]
    staging = upload_path.parent
    candidate = staging / "candidate.sqlite"

    if original_name.lower().endswith(".zip"):
        source_name = _extract_zip(upload_path, candidate)
    else:
        upload_path.replace(candidate)
        source_name = Path(original_name).name

    revision = _read_revision(candidate)
    head = _head_revision()
    migrated_from = None
    if revision != head:
        _migrate_file(candidate, settings)
        migrated_from = revision
        if _read_revision(candidate) != head:  # pragma: no cover - 防呆
            raise RestoreError("備份的資料庫版本升級失敗，目前的資料沒有被變更。")

    live = settings.database.path
    safety_name = None
    if live.exists():
        try:
            safety = backup_service.create_backup(
                live,
                settings.backup.directory,
                tz_name=settings.app.timezone,
                prefix="pre-restore-",
            )
        except (OSError, RuntimeError, sqlite3.Error) as exc:
            logger.exception("Pre-restore backup failed: %s", exc)
            raise RestoreError("無法先備份目前的資料庫，為了安全起見已取消還原。") from exc
        safety_name = safety.name

    _copy_into_live_database(candidate, live)
    logger.info(
        "Database restored from upload %s (migrated_from=%s, safety=%s)",
        source_name,
        migrated_from,
        safety_name,
    )

    from .. import seed
    from ..models import ActorType, AuditAction, Child
    from . import audit_service

    seed.initialize(app)

    restored_at = now_local(settings.app.timezone).strftime("%Y/%m/%d %H:%M")
    audit_service.record(
        AuditAction.RESTORE_DATABASE,
        actor_type=ActorType.ADMIN,
        # 還原後的資料庫裡，管理員 id 不一定還對得上，只記名稱
        actor_name=actor_name,
        entity_type="DATABASE",
        description=(
            f"{restored_at} 從上傳的備份還原：{source_name}"
            + (f"（還原前的資料已備份為 {safety_name}）" if safety_name else "")
        ),
    )
    db.session.commit()

    child_count = db.session.query(Child).count()
    return RestoreResult(
        source_name=source_name,
        safety_backup_name=safety_name,
        migrated_from=migrated_from,
        child_count=child_count,
    )


def restore_from_file_storage(app: Flask, file_storage, *, actor_name: str) -> RestoreResult:  # noqa: ANN001
    """Route 用：把 werkzeug 的上傳檔存到暫存區後還原。"""
    original_name = (file_storage.filename or "").strip()
    if not original_name.lower().endswith((".db", ".zip")):
        raise RestoreError("請選擇 .db 備份檔，或寄信功能寄出的 .zip。")

    if not _restore_lock.acquire(blocking=False):
        raise RestoreError("已經有一個還原正在進行，請稍後再試。")
    try:
        settings: Settings = app.settings  # type: ignore[attr-defined]
        staging = _staging_dir(settings)
        _clear_staging(staging)
        upload_path = staging / "upload.bin"
        file_storage.save(str(upload_path))
        if upload_path.stat().st_size > MAX_UPLOAD_BYTES:
            raise RestoreError("備份檔太大了，不像是這個系統的備份。")
        return restore_upload(app, upload_path, original_name, actor_name=actor_name)
    finally:
        try:
            _clear_staging(_staging_dir(app.settings))  # type: ignore[attr-defined]
        finally:
            _restore_lock.release()
