"""登入與授權的整合測試。

重點：Admin 與 Child 的權限不可以混淆（需求書第 19、159、160 節）。
"""

from __future__ import annotations

from family_reward.models import AuditAction, AuditLog
from family_reward.security.rate_limit import login_throttle
from tests.conftest import ADMIN_PASSWORD, ADMIN_USERNAME, CHILD_PIN


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "UP"}


def test_health_does_not_leak_internals(client):
    """健康檢查不得洩漏資料庫路徑、版本等資訊。"""
    payload = client.get("/health").get_json()

    assert set(payload.keys()) == {"status"}


def test_index_lists_children(client, child):
    response = client.get("/")

    assert response.status_code == 200
    assert "小明" in response.get_data(as_text=True)


def test_index_hides_inactive_children(client, child, db):
    child.active = False
    db.session.commit()

    body = client.get("/").get_data(as_text=True)
    assert "小明" not in body


def test_child_login_success(client, child, login_child):
    response = login_child(child.id)

    assert response.status_code == 200
    assert "小明" in response.get_data(as_text=True)
    # 登入後可以進入自己的頁面
    assert client.get("/child/dashboard").status_code == 200


def test_child_login_wrong_pin(client, child, login_child):
    response = login_child(child.id, pin="9999")

    assert "數字好像不太對" in response.get_data(as_text=True)
    # 沒登入成功 → 被導回首頁
    assert client.get("/child/dashboard").status_code == 302


def test_child_login_failure_is_audited_without_pin(client, child, login_child, db):
    """登入失敗要留紀錄，但絕不能記錄 PIN 內容。"""
    login_child(child.id, pin="9999")

    logs = list(
        db.session.execute(
            db.select(AuditLog).where(AuditLog.action == AuditAction.LOGIN_FAILURE.value)
        ).scalars()
    )
    assert len(logs) == 1
    assert "9999" not in logs[0].description


def test_child_login_throttled_after_repeated_failures(client, child, login_child):
    """連續失敗會被暫時鎖定（需求書第 119 節）。"""
    login_throttle.reset()
    for _ in range(5):
        login_child(child.id, pin="0000")

    response = login_child(child.id, pin=CHILD_PIN)
    assert "休息" in response.get_data(as_text=True)


def test_admin_login_success(client, login_admin):
    response = login_admin()

    assert response.status_code == 200
    assert client.get("/admin/").status_code == 200


def test_admin_login_wrong_password(client, login_admin):
    response = login_admin(password="wrong-password")

    assert "帳號或密碼不正確" in response.get_data(as_text=True)
    assert client.get("/admin/").status_code == 302


def test_admin_login_does_not_reveal_whether_user_exists(client, login_admin):
    """避免帳號列舉：不存在的帳號與錯誤密碼要有相同訊息。"""
    unknown = login_admin(username="nobody", password="whatever").get_data(as_text=True)
    wrong = login_admin(password="wrong-password").get_data(as_text=True)

    assert "帳號或密碼不正確" in unknown
    assert "帳號或密碼不正確" in wrong


def test_anonymous_cannot_access_admin(client):
    """需求書第 159 節：手動輸入 /admin 必須被擋下。"""
    response = client.get("/admin/")

    assert response.status_code == 302
    assert "/login/admin" in response.headers["Location"]


def test_child_cannot_access_admin(client, child, login_child):
    """小孩登入後仍然不能進入後台。"""
    login_child(child.id)

    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/login/admin" in response.headers["Location"]

    # 也不能直接呼叫後台的 POST endpoint
    assert client.post("/admin/backup").status_code in (302, 400)


def test_admin_is_not_treated_as_child(client, login_admin):
    """管理者登入不會自動變成某個小孩。"""
    login_admin()

    response = client.get("/child/dashboard")
    assert response.status_code == 302
    assert "/login/admin" not in response.headers["Location"]


def test_anonymous_cannot_access_child_pages(client):
    response = client.get("/child/dashboard")

    assert response.status_code == 302


def test_child_logout(client, child, login_child):
    login_child(child.id)
    client.post("/logout/child", follow_redirects=True)

    assert client.get("/child/dashboard").status_code == 302


def test_admin_logout(client, login_admin):
    login_admin()
    client.post("/logout/admin", follow_redirects=True)

    assert client.get("/admin/").status_code == 302


def test_initial_admin_must_change_password_warning(client, login_admin):
    """需求書第 157 節：仍使用初始密碼時要固定顯示提醒。"""
    response = login_admin()

    assert "初始管理員密碼" in response.get_data(as_text=True)


def test_change_password_clears_warning(client, login_admin):
    login_admin()

    client.post(
        "/admin/settings",
        data={
            "current_password": ADMIN_PASSWORD,
            "new_password": "brandNewPassword99",
            "confirm_password": "brandNewPassword99",
        },
        follow_redirects=True,
    )

    body = client.get("/admin/").get_data(as_text=True)
    assert "初始管理員密碼" not in body


def test_security_headers_present(client):
    response = client.get("/")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in response.headers


def test_404_page_is_friendly(client):
    response = client.get("/this-page-does-not-exist")

    assert response.status_code == 404
    assert "跑去玩了" in response.get_data(as_text=True)


def test_admin_login_page_renders(client):
    response = client.get("/login/admin")

    assert response.status_code == 200
    assert "秘密基地" in response.get_data(as_text=True)


def test_password_is_hashed_not_plaintext(db, admin_user):
    assert admin_user.password_hash != ADMIN_PASSWORD
    assert ADMIN_PASSWORD not in admin_user.password_hash
    assert admin_user.verify_password(ADMIN_PASSWORD)


def test_child_pin_is_hashed_not_plaintext(db, child):
    assert child.pin_hash != CHILD_PIN
    assert child.verify_pin(CHILD_PIN)


def test_admin_username_is_configured_value(db, admin_user):
    assert admin_user.username == ADMIN_USERNAME
