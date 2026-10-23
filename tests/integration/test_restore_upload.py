"""後台上傳備份並還原的測試。"""

from __future__ import annotations

import io
import sqlite3
import zipfile
from pathlib import Path

import pytest

from family_reward.models import AuditLog, Child
from family_reward.services import backup_service, email_service, restore_service
from tests.conftest import ADMIN_PASSWORD

INITIAL_REVISION = "2adacd12a4a8"


def _stamp(path: Path, revision: str) -> None:
    """真正的備份一定有 alembic_version（launcher 啟動時會跑 migration）。

    測試的資料庫是 create_all() 建的，所以要補上。
    """
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS alembic_version "
            "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
        )
        connection.execute("DELETE FROM alembic_version")
        connection.execute("INSERT INTO alembic_version VALUES (?)", (revision,))
        connection.commit()
    finally:
        connection.close()


@pytest.fixture()
def make_backup(app, settings):  # noqa: ANN001, ANN201
    def _make(revision: str | None = None) -> Path:
        with app.app_context():
            path = backup_service.create_backup(
                settings.database.path, settings.backup.directory
            )
        _stamp(path, revision or restore_service._head_revision())
        return path

    return _make


def _upload(client, data: bytes, filename: str, **overrides):  # noqa: ANN001, ANN003, ANN202
    form = {
        "backup_file": (io.BytesIO(data), filename),
        "current_password": ADMIN_PASSWORD,
        "confirm": "y",
    }
    form.update(overrides)
    return client.post(
        "/admin/restore",
        data=form,
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def _child_names(app) -> list[str]:  # noqa: ANN001
    with app.app_context():
        return sorted(child.name for child in Child.query.all())


def _add_child(db, name: str) -> None:  # noqa: ANN001
    extra = Child(name=name, avatar="🐯", theme="OCEAN", active=True)
    extra.set_pin("5678")
    db.session.add(extra)
    db.session.commit()


# --------------------------------------------------------------------------
# 成功還原
# --------------------------------------------------------------------------


def test_restore_replaces_current_data(client, app, db, child, login_admin, make_backup):
    backup = make_backup()
    _add_child(db, "小華")
    assert _child_names(app) == ["小明", "小華"]

    login_admin()
    body = _upload(client, backup.read_bytes(), backup.name).get_data(as_text=True)

    assert "還原完成" in body
    assert _child_names(app) == ["小明"]


def test_restore_keeps_safety_backup_of_current_data(
    client, app, db, child, login_admin, make_backup, settings
):
    backup = make_backup()
    _add_child(db, "小華")

    login_admin()
    _upload(client, backup.read_bytes(), backup.name)

    safety = [
        info.path for info in backup_service.list_backups(settings.backup.directory)
        if info.path.name.startswith("pre-restore-")
    ]
    assert len(safety) == 1
    connection = sqlite3.connect(str(safety[0]))
    try:
        names = sorted(row[0] for row in connection.execute("SELECT name FROM child"))
    finally:
        connection.close()
    # 還原前的資料（含小華）要能救回來
    assert names == ["小明", "小華"]


def test_restore_logs_out_and_backup_credentials_work(
    client, app, child, login_admin, make_backup
):
    backup = make_backup()
    login_admin()
    body = _upload(client, backup.read_bytes(), backup.name).get_data(as_text=True)

    assert "重新登入" in body
    assert client.get("/admin/settings").status_code == 302

    login_admin()
    assert client.get("/admin/settings").status_code == 200


def test_restore_is_audited_in_restored_database(client, app, child, login_admin, make_backup):
    backup = make_backup()
    login_admin()
    _upload(client, backup.read_bytes(), backup.name)

    with app.app_context():
        log = AuditLog.query.filter_by(action="RESTORE_DATABASE").one()
        assert backup.name in log.description
        assert "pre-restore-" in log.description


def test_restore_accepts_emailed_zip(client, app, db, child, login_admin, make_backup):
    backup = make_backup()
    zip_name, zip_bytes = email_service.build_attachment(backup)
    _add_child(db, "小華")

    login_admin()
    body = _upload(client, zip_bytes, zip_name).get_data(as_text=True)

    assert "還原完成" in body
    assert _child_names(app) == ["小明"]


def test_restore_migrates_older_backup(client, app, child, login_admin, settings, tmp_path):
    """舊版本的備份要先升級才還原，升級後新版本的資料表要存在。"""
    old = tmp_path / "old-version.db"
    restore_service._migrate_file(old, settings, INITIAL_REVISION)

    # 把目前測試資料搬進舊版本的資料庫（只搬兩邊都有的欄位）
    connection = sqlite3.connect(str(old))
    try:
        connection.execute("ATTACH DATABASE ? AS live", (str(settings.database.path),))
        for table in ("admin_user", "child"):
            columns = [row[1] for row in connection.execute(f"PRAGMA main.table_info({table})")]
            column_list = ", ".join(columns)
            connection.execute(
                f"INSERT INTO main.{table} ({column_list}) SELECT {column_list} FROM live.{table}"
            )
        connection.commit()
        connection.execute("DETACH DATABASE live")
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    finally:
        connection.close()
    assert "app_setting" not in tables

    login_admin()
    body = _upload(client, old.read_bytes(), old.name).get_data(as_text=True)

    assert "還原完成" in body
    connection = sqlite3.connect(str(settings.database.path))
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    finally:
        connection.close()
    assert "app_setting" in tables
    assert revision == restore_service._head_revision()
    assert _child_names(app) == ["小明"]


def test_staging_is_cleaned_up(client, child, login_admin, make_backup, settings):
    backup = make_backup()
    login_admin()
    _upload(client, backup.read_bytes(), backup.name)

    staging = settings.backup.directory / restore_service.STAGING_DIR_NAME
    assert list(staging.iterdir()) == []


# --------------------------------------------------------------------------
# 拒絕還原：目前資料都不能被動到
# --------------------------------------------------------------------------


def _assert_untouched(app, settings):  # noqa: ANN001, ANN202
    assert _child_names(app) == ["小明", "小華"]
    assert not any(
        info.path.name.startswith("pre-restore-")
        for info in backup_service.list_backups(settings.backup.directory)
    )


@pytest.fixture()
def two_children(db, child):  # noqa: ANN001, ANN201
    _add_child(db, "小華")


def test_wrong_password_does_not_restore(
    client, app, settings, two_children, login_admin, make_backup
):
    backup = make_backup()
    login_admin()
    body = _upload(
        client, backup.read_bytes(), backup.name, current_password="wrong-password"
    ).get_data(as_text=True)

    assert "密碼不正確" in body
    _assert_untouched(app, settings)


def test_missing_confirmation_does_not_restore(
    client, app, settings, two_children, login_admin, make_backup
):
    backup = make_backup()
    login_admin()
    form_without_confirm = {
        "backup_file": (io.BytesIO(backup.read_bytes()), backup.name),
        "current_password": ADMIN_PASSWORD,
    }
    body = client.post(
        "/admin/restore",
        data=form_without_confirm,
        content_type="multipart/form-data",
        follow_redirects=True,
    ).get_data(as_text=True)

    assert "請勾選確認" in body
    _assert_untouched(app, settings)


def test_non_database_file_rejected(client, app, settings, two_children, login_admin):
    login_admin()
    body = _upload(client, b"just some text", "notes.db").get_data(as_text=True)

    assert "不是資料庫備份檔" in body
    _assert_untouched(app, settings)


def test_other_sqlite_database_rejected(
    client, app, settings, two_children, login_admin, tmp_path
):
    other = tmp_path / "other.db"
    connection = sqlite3.connect(str(other))
    connection.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()

    login_admin()
    body = _upload(client, other.read_bytes(), other.name).get_data(as_text=True)

    assert "不是「家庭任務集點樂園」的備份" in body
    _assert_untouched(app, settings)


def test_backup_from_newer_version_rejected(
    client, app, settings, two_children, login_admin, make_backup
):
    backup = make_backup(revision="ffffffffffff")
    login_admin()
    body = _upload(client, backup.read_bytes(), backup.name).get_data(as_text=True)

    assert "比目前更新的版本" in body
    _assert_untouched(app, settings)


def test_zip_without_single_db_rejected(client, app, settings, two_children, login_admin):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("README.txt", "hello")
    login_admin()
    body = _upload(client, buffer.getvalue(), "backup.zip").get_data(as_text=True)

    assert "剛好有一個 .db" in body
    _assert_untouched(app, settings)


def test_wrong_extension_rejected(client, app, settings, two_children, login_admin):
    login_admin()
    body = _upload(client, b"SQLite format 3\x00", "backup.txt").get_data(as_text=True)

    assert "只能上傳 .db 或 .zip" in body
    _assert_untouched(app, settings)


# --------------------------------------------------------------------------
# 畫面與權限
# --------------------------------------------------------------------------


def test_settings_page_shows_restore_form(client, login_admin):
    login_admin()
    body = client.get("/admin/settings").get_data(as_text=True)
    assert "從備份還原" in body
    assert 'enctype="multipart/form-data"' in body


def test_restore_requires_admin(client):
    response = client.post(
        "/admin/restore",
        data={"backup_file": (io.BytesIO(b"x"), "a.db")},
        content_type="multipart/form-data",
    )
    assert response.status_code in (302, 400)


def test_backups_in_same_second_do_not_overwrite(app, settings, monkeypatch):
    """連續還原時 pre-restore 備份會在同一秒產生，不能互相覆蓋。"""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    frozen = datetime(2026, 10, 23, 23, 3, 12, tzinfo=ZoneInfo("Asia/Taipei"))
    monkeypatch.setattr(backup_service, "now_local", lambda tz_name: frozen)

    with app.app_context():
        first = backup_service.create_backup(
            settings.database.path, settings.backup.directory, prefix="pre-restore-"
        )
        second = backup_service.create_backup(
            settings.database.path, settings.backup.directory, prefix="pre-restore-"
        )

    assert first != second
    assert first.exists() and second.exists()
    assert second.name == "pre-restore-family-reward-20261023-230312-1.db"
    assert len(backup_service.list_backups(settings.backup.directory)) == 2
