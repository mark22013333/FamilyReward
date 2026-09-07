"""後台集點卡設定的整合測試（HTTP 層）。

最重要的是 `test_change_points_per_card_takes_effect_immediately` ——
這個功能存在的理由就是「不用重新啟動」。
"""

from __future__ import annotations

from family_reward.models import AppSetting
from family_reward.services import point_service, settings_service
from tests.conftest import ADMIN_PASSWORD


def _set_via_http(client, value, follow=True):  # noqa: ANN001, ANN202
    return client.post(
        "/admin/settings",
        data={"action": "change_points_per_card", "points_per_card": str(value)},
        follow_redirects=follow,
    )


# --------------------------------------------------------------------------
# 畫面
# --------------------------------------------------------------------------


def test_settings_page_shows_points_per_card_form(client, login_admin):
    login_admin()

    body = client.get("/admin/settings").get_data(as_text=True)

    assert "集點卡" in body
    assert "change_points_per_card" in body
    assert 'name="points_per_card"' in body


def test_settings_page_shows_effect_preview(client, child, admin_user, login_admin):
    """伺服器先算好現狀，沒有 JS 也看得到。"""
    point_service.adjust_points(
        child_id=child.id, points=23, reason="測試", admin_id=admin_user.id
    )
    login_admin()

    body = client.get("/admin/settings").get_data(as_text=True)

    assert child.display_name in body
    assert "目前完成 2 張" in body
    # JS 即時預覽需要的資料
    assert "data-lifetimes" in body


def test_settings_page_shows_current_value_not_yaml(client, db, login_admin):
    """唯讀那列要顯示實際使用的值，不是 config.yaml 的舊值。"""
    settings_service.set_points_per_card(35, admin_id=1)
    login_admin()

    body = client.get("/admin/settings").get_data(as_text=True)

    assert "35 點" in body


# --------------------------------------------------------------------------
# 核心：立即生效
# --------------------------------------------------------------------------


def test_change_points_per_card_takes_effect_immediately(
    client, child, admin_user, login_admin, login_child
):
    """後台改設定 → 不重啟、不重建 app → 小孩畫面立刻反映新分母。

    這是整個功能的驗收條件。
    """
    point_service.adjust_points(
        child_id=child.id, points=23, reason="測試", admin_id=admin_user.id
    )

    login_admin()
    response = _set_via_http(client, 5)
    assert "已改成 5 點一張" in response.get_data(as_text=True)
    client.post("/logout/admin", follow_redirects=True)

    # 同一個 app、同一個 process，沒有任何重啟
    login_child(child.id)
    dashboard = client.get("/child/dashboard").get_data(as_text=True)

    assert "3 / 5" in dashboard
    assert "已經完成 4 張集點卡" in dashboard


def test_flash_message_reports_actual_effect(
    client, child, admin_user, login_admin
):
    point_service.adjust_points(
        child_id=child.id, points=23, reason="測試", admin_id=admin_user.id
    )
    login_admin()

    body = _set_via_http(client, 5).get_data(as_text=True)

    assert f"{child.display_name} 完成 4 張" in body


def test_change_is_reversible(client, child, admin_user, login_admin, login_child):
    """改回原本的數字，張數就完全回來。"""
    point_service.adjust_points(
        child_id=child.id, points=23, reason="測試", admin_id=admin_user.id
    )

    login_admin()
    _set_via_http(client, 50)
    _set_via_http(client, 10)
    client.post("/logout/admin", follow_redirects=True)

    login_child(child.id)
    dashboard = client.get("/child/dashboard").get_data(as_text=True)

    assert "3 / 10" in dashboard
    assert "已經完成 2 張集點卡" in dashboard


def test_large_value_switches_to_progress_bar(
    client, child, admin_user, login_admin, login_child
):
    """超過 20 點就不畫星星，改用進度條。"""
    point_service.adjust_points(
        child_id=child.id, points=23, reason="測試", admin_id=admin_user.id
    )

    login_admin()
    _set_via_http(client, 50)
    client.post("/logout/admin", follow_redirects=True)

    login_child(child.id)
    dashboard = client.get("/child/dashboard").get_data(as_text=True)

    assert "progress__bar" in dashboard
    assert 'class="stamp' not in dashboard
    assert "23 / 50" in dashboard


def test_small_value_keeps_stamps(
    client, child, admin_user, login_admin, login_child
):
    login_admin()
    _set_via_http(client, 20)
    client.post("/logout/admin", follow_redirects=True)

    login_child(child.id)
    dashboard = client.get("/child/dashboard").get_data(as_text=True)

    assert 'class="stamp' in dashboard


# --------------------------------------------------------------------------
# 驗證與稽核
# --------------------------------------------------------------------------


def test_rejects_zero_via_http(client, db, login_admin):
    login_admin()

    body = _set_via_http(client, 0).get_data(as_text=True)

    assert "必須介於" in body
    assert settings_service.get_points_per_card() == 10


def test_rejects_too_large_via_http(client, db, login_admin):
    login_admin()

    body = _set_via_http(client, 999).get_data(as_text=True)

    assert "必須介於" in body
    assert settings_service.get_points_per_card() == 10


def test_rejects_non_numeric_via_http(client, db, login_admin):
    login_admin()

    _set_via_http(client, "abc")

    assert settings_service.get_points_per_card() == 10


def test_change_writes_audit_log_visible_in_history(client, db, login_admin):
    login_admin()
    _set_via_http(client, 25)

    body = client.get("/admin/history").get_data(as_text=True)

    assert "UPDATE_APP_SETTING" in body
    assert "集點卡點數由 10 改為 25" in body


# --------------------------------------------------------------------------
# 權限
# --------------------------------------------------------------------------


def test_anonymous_cannot_change_points_per_card(client, db):
    response = _set_via_http(client, 5, follow=False)

    assert response.status_code == 302
    assert "/login/admin" in response.headers["Location"]
    assert settings_service.get_points_per_card() == 10


def test_child_cannot_change_points_per_card(client, db, child, login_child):
    login_child(child.id)

    response = _set_via_http(client, 5, follow=False)

    assert response.status_code == 302
    assert settings_service.get_points_per_card() == 10


# --------------------------------------------------------------------------
# 迴歸：新表單不可干擾既有的兩個表單
# --------------------------------------------------------------------------


def test_username_form_still_works(client, db, admin_user, login_admin):
    login_admin()

    body = client.post(
        "/admin/settings",
        data={
            "action": "change_username",
            "new_username": "papa",
            "current_password": ADMIN_PASSWORD,
        },
        follow_redirects=True,
    ).get_data(as_text=True)

    assert "帳號已經修改成功" in body
    # 不該跳出集點卡欄位的錯誤
    assert "請填寫幾點集滿一張集點卡" not in body
    assert settings_service.get_points_per_card() == 10


def test_points_card_form_does_not_touch_account(client, db, admin_user, login_admin):
    login_admin()

    _set_via_http(client, 15)

    db.session.refresh(admin_user)
    assert admin_user.verify_password(ADMIN_PASSWORD)
    assert settings_service.get_points_per_card() == 15


def test_only_one_setting_row_after_many_changes(client, db, login_admin):
    """反覆修改不該產生多筆資料列。"""
    login_admin()
    for value in (5, 20, 50, 10, 30):
        _set_via_http(client, value)

    rows = list(db.session.execute(db.select(AppSetting)).scalars())
    assert len(rows) == 1
    assert settings_service.get_points_per_card() == 30
