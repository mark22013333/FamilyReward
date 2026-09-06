"""設定驗證與資料庫層保護的測試。"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from family_reward.config import ConfigError, Settings, validate_settings
from family_reward.database import current_pragmas
from family_reward.models import (
    Child,
    PointTransaction,
    SourceType,
    TaskAssignment,
    TransactionType,
)
from family_reward.utils.timezone import today_local, weekday_code


# --------------------------------------------------------------------------
# 設定驗證（需求書第 152 節）
# --------------------------------------------------------------------------


def test_points_per_card_must_be_positive(settings: Settings):
    settings.reward.points_per_card = 0

    with pytest.raises(ConfigError, match="points_per_card"):
        validate_settings(settings)


def test_invalid_port_rejected(settings: Settings):
    settings.server.port = 99999

    with pytest.raises(ConfigError, match="port"):
        validate_settings(settings)


def test_invalid_timezone_rejected(settings: Settings):
    settings.app.timezone = "Mars/Olympus"

    with pytest.raises(ConfigError, match="timezone"):
        validate_settings(settings)


def test_production_requires_secret_key(settings: Settings):
    settings.app.env = "production"
    settings.secret_key = ""

    with pytest.raises(ConfigError, match="FLASK_SECRET_KEY"):
        validate_settings(settings)


def test_valid_settings_pass(settings: Settings):
    validate_settings(settings)  # 不應拋出例外


# --------------------------------------------------------------------------
# SQLite PRAGMA（需求書第 60/61 節）
# --------------------------------------------------------------------------


def test_sqlite_pragmas_applied(app, db):
    pragmas = current_pragmas(db.engine)

    assert pragmas["foreign_keys"] == 1
    assert pragmas["busy_timeout"] == 5000
    assert str(pragmas["journal_mode"]).lower() == "wal"


def test_foreign_key_constraint_enforced(db, child):
    """foreign_keys = ON 必須真的生效。"""
    orphan = PointTransaction(
        child_id=99999,
        transaction_type=TransactionType.EARN.value,
        points=1,
        source_type=SourceType.MANUAL.value,
        source_id=None,
        description="孤兒紀錄",
    )
    db.session.add(orphan)

    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


# --------------------------------------------------------------------------
# 資料庫層的重複保護（需求書第 33 節）
# --------------------------------------------------------------------------


def test_unique_constraint_blocks_duplicate_earn(db, child):
    """即使繞過 Service，資料庫層仍會擋下重複加點。"""
    for _ in range(2):
        db.session.add(
            PointTransaction(
                child_id=child.id,
                transaction_type=TransactionType.EARN.value,
                points=2,
                source_type=SourceType.TASK_ASSIGNMENT.value,
                source_id=123,
                description="完成任務",
            )
        )

    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_unique_constraint_blocks_duplicate_assignment(db, child, task, today):
    """同一天同一任務不能有兩筆 assignment。"""
    for _ in range(2):
        db.session.add(
            TaskAssignment(
                task_id=task.id,
                child_id=child.id,
                assignment_date=today,
                task_title_snapshot=task.title,
                task_icon_snapshot=task.icon,
                points_snapshot=task.points,
            )
        )

    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_check_constraint_rejects_zero_points(db, child):
    db.session.add(
        PointTransaction(
            child_id=child.id,
            transaction_type=TransactionType.EARN.value,
            points=0,
            source_type=SourceType.MANUAL.value,
            source_id=None,
            description="零點交易",
        )
    )

    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_check_constraint_rejects_blank_child_name(db):
    child = Child(name="   ", avatar="🐼", theme="SUNNY", pin_hash="x")

    db.session.add(child)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


# --------------------------------------------------------------------------
# 時區（需求書第 12 節）
# --------------------------------------------------------------------------


def test_today_uses_taipei_timezone():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    expected = datetime.now(ZoneInfo("Asia/Taipei")).date()
    assert today_local("Asia/Taipei") == expected


def test_weekday_code_mapping():
    from datetime import date

    # 2026-09-07 是星期一
    assert weekday_code(date(2026, 9, 7)) == "MON"
    assert weekday_code(date(2026, 9, 13)) == "SUN"


def test_utc_stored_but_displayed_local(app):
    """資料庫存 UTC，顯示轉台北時間。"""
    from datetime import datetime

    from family_reward.utils.timezone import to_local

    utc_naive = datetime(2026, 9, 6, 12, 0, 0)
    local = to_local(utc_naive, "Asia/Taipei")

    assert local.hour == 20  # UTC+8
