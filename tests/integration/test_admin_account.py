"""管理員帳號與密碼修改的測試。

重點：
* 改帳號必須經過密碼確認（避免趁人沒登出時偷改）
* config.yaml 的 initial_username 只在第一次建立時生效
* 同一頁的兩個表單不可以互相干擾
"""

from __future__ import annotations

import pytest

from family_reward.exceptions import ValidationError
from family_reward.models import AdminUser, AuditLog
from family_reward.services import admin_service
from tests.conftest import ADMIN_PASSWORD, ADMIN_USERNAME

NEW_PASSWORD = "brandNewPassword99"


# --------------------------------------------------------------------------
# Service 層
# --------------------------------------------------------------------------


def test_change_username_success(db, admin_user):
    admin_service.change_username(admin_user, "papa", ADMIN_PASSWORD)

    assert admin_user.username == "papa"
    assert admin_service.get_by_username("papa") is not None
    # 舊帳號應該查不到了
    assert admin_service.get_by_username(ADMIN_USERNAME) is None


def test_change_username_requires_correct_password(db, admin_user):
    """沒有正確密碼不能改帳號。"""
    with pytest.raises(ValidationError, match="密碼不正確"):
        admin_service.change_username(admin_user, "papa", "wrong-password")

    assert admin_user.username == ADMIN_USERNAME


def test_change_username_rejects_too_short(db, admin_user):
    with pytest.raises(ValidationError, match="長度"):
        admin_service.change_username(admin_user, "ab", ADMIN_PASSWORD)


def test_change_username_rejects_invalid_characters(db, admin_user):
    """含空白、中文或特殊符號的帳號一律拒絕。

    （「爸爸」只有兩個字，會先被長度檢查擋下，同樣是拒絕。）
    """
    for bad in ("papa mama", "爸爸媽媽", "papa@home", "papa/admin", "papa;drop"):
        with pytest.raises(ValidationError, match="只能使用"):
            admin_service.change_username(admin_user, bad, ADMIN_PASSWORD)

    # 太短的也要擋，只是錯誤訊息不同
    with pytest.raises(ValidationError, match="長度"):
        admin_service.change_username(admin_user, "爸爸", ADMIN_PASSWORD)

    assert admin_user.username == ADMIN_USERNAME


def test_change_username_allows_dot_underscore_hyphen(db, admin_user):
    admin_service.change_username(admin_user, "pa.pa_1-2", ADMIN_PASSWORD)

    assert admin_user.username == "pa.pa_1-2"


def test_change_username_rejects_same_name(db, admin_user):
    with pytest.raises(ValidationError, match="一樣"):
        admin_service.change_username(admin_user, ADMIN_USERNAME, ADMIN_PASSWORD)


def test_change_username_rejects_duplicate(db, admin_user):
    """已經有人用的帳號不能重複。"""
    other = AdminUser(username="mama", active=True)
    other.set_password("anotherPassword123")
    db.session.add(other)
    db.session.commit()

    with pytest.raises(ValidationError, match="已經有人使用"):
        admin_service.change_username(admin_user, "mama", ADMIN_PASSWORD)

    assert admin_user.username == ADMIN_USERNAME


def test_change_username_strips_whitespace(db, admin_user):
    admin_service.change_username(admin_user, "  papa  ", ADMIN_PASSWORD)

    assert admin_user.username == "papa"


def test_change_username_is_audited(db, admin_user):
    admin_service.change_username(admin_user, "papa", ADMIN_PASSWORD)

    log = db.session.execute(
        db.select(AuditLog).where(AuditLog.action == "CHANGE_USERNAME")
    ).scalar_one()

    assert ADMIN_USERNAME in log.description
    assert "papa" in log.description
    # 稽核紀錄不得出現密碼
    assert ADMIN_PASSWORD not in log.description


def test_password_still_works_after_username_change(db, admin_user):
    """改帳號不應該影響密碼。"""
    admin_service.change_username(admin_user, "papa", ADMIN_PASSWORD)

    assert admin_user.verify_password(ADMIN_PASSWORD)


# --------------------------------------------------------------------------
# initial_username 的語意（只在第一次建立時生效）
# --------------------------------------------------------------------------


def test_initial_username_ignored_when_admin_exists(db, admin_user):
    """已經有管理員時，再呼叫 ensure_initial_admin 不能新建也不能改名。"""
    result = admin_service.ensure_initial_admin("completely-different", "somePassword123")

    assert result is None
    assert admin_service.count_admins() == 1
    assert admin_user.username == ADMIN_USERNAME


def test_initial_username_used_on_first_creation(db):
    """沒有任何管理員時，才會依 initial_username 建立。"""
    db.session.query(AdminUser).delete()
    db.session.commit()
    assert admin_service.count_admins() == 0

    created = admin_service.ensure_initial_admin("firstboot", "initialPassword123")

    assert created is not None
    assert created.username == "firstboot"
    assert created.must_change_password is True


# --------------------------------------------------------------------------
# HTTP 層：兩個表單不可互相干擾
# --------------------------------------------------------------------------


def test_change_username_via_http(client, db, admin_user, login_admin):
    login_admin()

    response = client.post(
        "/admin/settings",
        data={
            "action": "change_username",
            "new_username": "papa",
            "current_password": ADMIN_PASSWORD,
        },
        follow_redirects=True,
    )

    assert "帳號已經修改成功" in response.get_data(as_text=True)
    db.session.refresh(admin_user)
    assert admin_user.username == "papa"


def test_can_login_with_new_username(client, db, admin_user, login_admin):
    login_admin()
    client.post(
        "/admin/settings",
        data={
            "action": "change_username",
            "new_username": "papa",
            "current_password": ADMIN_PASSWORD,
        },
        follow_redirects=True,
    )
    client.post("/logout/admin", follow_redirects=True)

    # 舊帳號應該不能登入了
    old = login_admin(username=ADMIN_USERNAME, password=ADMIN_PASSWORD)
    assert "帳號或密碼不正確" in old.get_data(as_text=True)

    # 新帳號可以
    new = login_admin(username="papa", password=ADMIN_PASSWORD)
    assert client.get("/admin/").status_code == 200
    assert "帳號或密碼不正確" not in new.get_data(as_text=True)


def test_password_form_does_not_trigger_username_errors(client, db, admin_user, login_admin):
    """送出改密碼的表單時，不該跳出改帳號的欄位錯誤。"""
    login_admin()

    response = client.post(
        "/admin/settings",
        data={
            "action": "change_password",
            "current_password": ADMIN_PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)
    assert "密碼已經修改成功" in body
    assert "請輸入新的帳號" not in body
    # 帳號不能被動到
    db.session.refresh(admin_user)
    assert admin_user.username == ADMIN_USERNAME


def test_username_form_does_not_trigger_password_errors(client, db, admin_user, login_admin):
    """送出改帳號的表單時，不該跳出改密碼的欄位錯誤。"""
    login_admin()

    response = client.post(
        "/admin/settings",
        data={
            "action": "change_username",
            "new_username": "papa",
            "current_password": ADMIN_PASSWORD,
        },
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)
    assert "帳號已經修改成功" in body
    assert "請輸入新密碼" not in body
    # 密碼不能被動到
    db.session.refresh(admin_user)
    assert admin_user.verify_password(ADMIN_PASSWORD)


def test_settings_page_shows_current_username(client, admin_user, login_admin):
    login_admin()

    body = client.get("/admin/settings").get_data(as_text=True)

    assert ADMIN_USERNAME in body
    assert "管理員帳號" in body


def test_change_username_wrong_password_via_http(client, db, admin_user, login_admin):
    login_admin()

    response = client.post(
        "/admin/settings",
        data={
            "action": "change_username",
            "new_username": "papa",
            "current_password": "wrong-password",
        },
        follow_redirects=True,
    )

    assert "密碼不正確" in response.get_data(as_text=True)
    db.session.refresh(admin_user)
    assert admin_user.username == ADMIN_USERNAME


def test_anonymous_cannot_change_username(client, admin_user):
    """沒登入不能改帳號。"""
    response = client.post(
        "/admin/settings",
        data={
            "action": "change_username",
            "new_username": "hacker",
            "current_password": ADMIN_PASSWORD,
        },
    )

    assert response.status_code == 302
    assert "/login/admin" in response.headers["Location"]


def test_child_cannot_change_admin_username(client, db, child, admin_user, login_child):
    """小孩登入後也不能改管理員帳號。"""
    login_child(child.id)

    response = client.post(
        "/admin/settings",
        data={
            "action": "change_username",
            "new_username": "hacker",
            "current_password": ADMIN_PASSWORD,
        },
    )

    assert response.status_code == 302
    db.session.refresh(admin_user)
    assert admin_user.username == ADMIN_USERNAME


# --------------------------------------------------------------------------
# 查詢帳號的輔助腳本
# --------------------------------------------------------------------------


def test_show_admin_script_reports_username(app):
    """scripts/show_admin.py 要能查出目前的帳號，且不得洩漏密碼。"""
    import subprocess
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent
    script = project_root / "scripts" / "show_admin.py"

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        timeout=60,
        cwd=str(project_root),
    )

    output = result.stdout.decode("utf-8", errors="replace")
    # 使用正式設定檔，因此只驗證輸出格式與「不洩漏 hash」。
    assert "管理員帳號" in output or "找不到資料庫" in output
    assert "password_hash" not in output
    assert "pbkdf2" not in output.lower() and "scrypt" not in output.lower()


# --------------------------------------------------------------------------
# 「改了 .env 卻沒生效」的警告（實際踩過的坑）
# --------------------------------------------------------------------------


def test_warns_when_env_password_differs(db, admin_user, caplog):
    """改了 .env 的密碼但帳號已存在時，啟動要明確警告，不能默默忽略。"""
    import logging

    with caplog.at_level(logging.WARNING):
        admin_service.ensure_initial_admin(ADMIN_USERNAME, "a-completely-different-pw")

    messages = " ".join(record.message for record in caplog.records)
    assert "ADMIN_INITIAL_PASSWORD" in messages
    assert "第一次建立帳號" in messages
    # 絕不可以把密碼內容寫進 log
    assert "a-completely-different-pw" not in messages


def test_warns_when_config_username_differs(db, admin_user, caplog):
    import logging

    with caplog.at_level(logging.WARNING):
        admin_service.ensure_initial_admin("totally-different", ADMIN_PASSWORD)

    messages = " ".join(record.message for record in caplog.records)
    assert "initial_username" in messages
    assert "totally-different" in messages
    assert ADMIN_USERNAME in messages


def test_no_warning_when_settings_match(db, admin_user, caplog):
    """設定與實際相符時不該吵使用者。"""
    import logging

    with caplog.at_level(logging.WARNING):
        admin_service.ensure_initial_admin(ADMIN_USERNAME, ADMIN_PASSWORD)

    messages = " ".join(record.message for record in caplog.records)
    assert "ADMIN_INITIAL_PASSWORD" not in messages
    assert "initial_username" not in messages


def test_env_password_never_overwrites_existing(db, admin_user):
    """核心規則：.env 不能覆寫既有帳號的密碼。"""
    admin_service.ensure_initial_admin(ADMIN_USERNAME, "attacker-supplied-password")

    assert admin_user.verify_password(ADMIN_PASSWORD)
    assert not admin_user.verify_password("attacker-supplied-password")


def test_reset_password_script_exists_and_is_documented():
    """警告訊息裡提到的腳本必須真的存在。"""
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent
    assert (project_root / "scripts" / "reset_admin_password.py").exists()


def test_show_admin_reports_login_url(app):
    """show_admin.py 要顯示正確的登入網址（連錯 port 是常見問題）。"""
    import subprocess
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent
    result = subprocess.run(
        [sys.executable, str(project_root / "scripts" / "show_admin.py")],
        capture_output=True,
        timeout=60,
        cwd=str(project_root),
    )
    output = result.stdout.decode("utf-8", errors="replace")

    assert "登入網址" in output or "找不到資料庫" in output
    assert "reset_admin_password.py" in output or "找不到資料庫" in output
