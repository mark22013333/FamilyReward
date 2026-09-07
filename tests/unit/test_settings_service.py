"""後台可修改設定的單元測試。

核心規則：**資料庫 > config.yaml**。
`config.yaml` 只是第一次建立資料庫時的種子，之後改它不會生效。
"""

from __future__ import annotations

import logging

import pytest

from family_reward.exceptions import ValidationError
from family_reward.models import AppSetting, AuditLog
from family_reward.services import point_service, settings_service


# --------------------------------------------------------------------------
# 種子與讀取
# --------------------------------------------------------------------------


def test_ensure_defaults_creates_row_once(db):
    """可以重複執行，不會產生第二筆，也不會覆寫既有的值。"""
    settings_service.ensure_defaults(10)
    settings_service.ensure_defaults(10)

    rows = list(db.session.execute(db.select(AppSetting)).scalars())
    assert len(rows) == 1
    assert rows[0].key == settings_service.KEY_POINTS_PER_CARD
    assert rows[0].value == "10"


def test_ensure_defaults_does_not_overwrite_existing(db):
    """關鍵：每次重新啟動都會呼叫這個函式，絕不能把家長改過的值蓋回去。"""
    settings_service.set_points_per_card(25, admin_id=1)

    settings_service.ensure_defaults(10)  # 模擬重新啟動

    assert settings_service.get_points_per_card() == 25


def test_get_points_per_card_reads_db_not_config(app, db):
    """整個功能最核心的迴歸測試：讀資料庫，不是讀 config.yaml。"""
    row = db.session.execute(
        db.select(AppSetting).where(
            AppSetting.key == settings_service.KEY_POINTS_PER_CARD
        )
    ).scalar_one()
    row.value = "5"
    db.session.commit()

    # config.yaml 的值仍然是 10
    assert app.settings.reward.points_per_card == 10
    # 但實際使用的是資料庫的 5
    assert settings_service.get_points_per_card() == 5


def test_get_points_per_card_falls_back_when_row_missing(db):
    """資料列不見時退回 config.yaml，不可以拋例外把小孩的首頁弄壞。"""
    db.session.query(AppSetting).delete()
    db.session.commit()

    assert settings_service.get_points_per_card() == 10


@pytest.mark.parametrize("bad_value", ["abc", "", "0", "-5", "3.5"])
def test_get_points_per_card_falls_back_on_garbage(db, caplog, bad_value):
    """內容壞掉時要警告並退回設定檔的值。"""
    row = db.session.execute(
        db.select(AppSetting).where(
            AppSetting.key == settings_service.KEY_POINTS_PER_CARD
        )
    ).scalar_one()
    row.value = bad_value
    db.session.commit()

    with caplog.at_level(logging.WARNING):
        assert settings_service.get_points_per_card() == 10

    assert any("points_per_card" in record.message for record in caplog.records)


# --------------------------------------------------------------------------
# 寫入與驗證
# --------------------------------------------------------------------------


def test_set_points_per_card_updates_value(db):
    old = settings_service.set_points_per_card(20, admin_id=1, admin_name="admin")

    assert old == 10
    assert settings_service.get_points_per_card() == 20


@pytest.mark.parametrize("bad", [0, -1, 101, 9999])
def test_set_points_per_card_rejects_out_of_range(db, bad):
    """Service 層自己驗，不能只依賴 form —— 腳本直接呼叫也要擋。"""
    with pytest.raises(ValidationError, match="必須介於"):
        settings_service.set_points_per_card(bad, admin_id=1)

    assert settings_service.get_points_per_card() == 10


@pytest.mark.parametrize("edge", [1, 100])
def test_set_points_per_card_accepts_boundaries(db, edge):
    settings_service.set_points_per_card(edge, admin_id=1)

    assert settings_service.get_points_per_card() == edge


def test_set_points_per_card_rejects_same_value(db):
    with pytest.raises(ValidationError, match="一樣"):
        settings_service.set_points_per_card(10, admin_id=1)


def test_set_points_per_card_writes_audit_log(db):
    settings_service.set_points_per_card(20, admin_id=1, admin_name="testadmin")

    log = db.session.execute(
        db.select(AuditLog).where(AuditLog.action == "UPDATE_APP_SETTING")
    ).scalar_one()

    assert log.actor_type == "ADMIN"
    assert log.actor_name == "testadmin"
    assert "10" in log.description and "20" in log.description


# --------------------------------------------------------------------------
# 影響預覽
# --------------------------------------------------------------------------


def test_preview_reports_card_count_change(db, child, admin_user):
    """需求書第 42 節的例子：累積 23 點。

    10 點制 → 完成 2 張、目前 3/10
    20 點制 → 完成 1 張、目前 3/20
    """
    point_service.adjust_points(
        child_id=child.id, points=23, reason="測試", admin_id=admin_user.id
    )

    previews = settings_service.preview_points_per_card_change(20)

    assert len(previews) == 1
    preview = previews[0]
    assert preview.lifetime_earned == 23
    assert (preview.before_cards, preview.before_current) == (2, 3)
    assert (preview.after_cards, preview.after_current) == (1, 3)
    assert preview.changed is True


def test_preview_marks_unchanged_when_same(db, child, admin_user):
    point_service.adjust_points(
        child_id=child.id, points=23, reason="測試", admin_id=admin_user.id
    )

    previews = settings_service.preview_points_per_card_change(10)

    assert previews[0].changed is False


def test_preview_ignores_inactive_children(db, child, other_child):
    other_child.active = False
    db.session.commit()

    previews = settings_service.preview_points_per_card_change(5)

    assert [p.child_name for p in previews] == [child.display_name]


# --------------------------------------------------------------------------
# config.yaml 不一致的警告
# --------------------------------------------------------------------------


def test_warns_when_config_differs_from_db(db, caplog):
    settings_service.set_points_per_card(30, admin_id=1)

    with caplog.at_level(logging.WARNING):
        settings_service.warn_if_config_ignored(10)

    messages = " ".join(record.message for record in caplog.records)
    assert "points_per_card" in messages
    assert "第一次建立資料庫" in messages


def test_no_warning_when_config_matches_db(db, caplog):
    with caplog.at_level(logging.WARNING):
        settings_service.warn_if_config_ignored(10)

    assert not [r for r in caplog.records if "points_per_card" in r.message]
