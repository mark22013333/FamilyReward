"""Cloudflare Tunnel 相關設定的測試。

重點（實際踩過的坑）：

`cloudflare.enabled` 的語意是「要不要由 start.bat 自己啟動一個 cloudflared」。
如果使用者把 tunnel 註冊成 Windows 服務（儀表板管理型），enabled 會是 false，
但流量「仍然」經過 Cloudflare 的 proxy。

如果 Secure cookie 與 ProxyFix 只看 enabled，就會在這種情況下：
    * Session cookie 沒有 Secure 旗標
    * X-Forwarded-Proto 被忽略，Flask 以為自己是 http
所以改用 `behind_proxy`（enabled 或有設定 hostname）。
"""

from __future__ import annotations

import pytest

from family_reward import create_app


def _build(settings, **overrides):  # noqa: ANN001, ANN202
    for key, value in overrides.items():
        section, _, field = key.partition("__")
        setattr(getattr(settings, section), field, value)
    return create_app(settings=settings, setup_log=False)


# --------------------------------------------------------------------------
# behind_proxy 的判斷
# --------------------------------------------------------------------------


def test_not_behind_proxy_by_default(settings):
    """純本機使用：沒有 hostname 也沒有啟用 cloudflared。"""
    settings.cloudflare.enabled = False
    settings.cloudflare.hostname = ""

    assert settings.behind_proxy is False


def test_behind_proxy_when_hostname_set(settings):
    """儀表板管理型：enabled=false 但有對外網域，仍然在 proxy 後面。"""
    settings.cloudflare.enabled = False
    settings.cloudflare.hostname = "familyreward.longhopick.com"

    assert settings.behind_proxy is True


def test_behind_proxy_when_enabled(settings):
    """本機設定檔型：由 start.bat 啟動 cloudflared。"""
    settings.cloudflare.enabled = True
    settings.cloudflare.hostname = ""

    assert settings.behind_proxy is True


def test_blank_hostname_is_not_behind_proxy(settings):
    """只有空白字元不算有設定網域。"""
    settings.cloudflare.enabled = False
    settings.cloudflare.hostname = "   "

    assert settings.behind_proxy is False


# --------------------------------------------------------------------------
# Secure cookie
# --------------------------------------------------------------------------


def test_secure_cookie_enabled_for_dashboard_managed_tunnel(settings):
    """這是真正踩到的坑：enabled=false 但有 hostname 時也要有 Secure。"""
    settings.app.env = "production"
    settings.cloudflare.enabled = False
    settings.cloudflare.hostname = "familyreward.longhopick.com"

    app = create_app(settings=settings, setup_log=False)

    assert app.config["SESSION_COOKIE_SECURE"] is True


def test_secure_cookie_off_for_local_only(settings):
    """純本機（http://127.0.0.1）不能要求 Secure，否則會登不進去。"""
    settings.app.env = "production"
    settings.cloudflare.enabled = False
    settings.cloudflare.hostname = ""

    app = create_app(settings=settings, setup_log=False)

    assert app.config["SESSION_COOKIE_SECURE"] is False


def test_secure_cookie_off_in_development(settings):
    settings.app.env = "development"
    settings.cloudflare.hostname = "familyreward.longhopick.com"

    app = create_app(settings=settings, setup_log=False)

    assert app.config["SESSION_COOKIE_SECURE"] is False


def test_cookie_always_httponly_and_samesite(settings):
    app = create_app(settings=settings, setup_log=False)

    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


# --------------------------------------------------------------------------
# ProxyFix
# --------------------------------------------------------------------------


def test_proxyfix_applied_for_dashboard_managed_tunnel(settings):
    settings.cloudflare.enabled = False
    settings.cloudflare.hostname = "familyreward.longhopick.com"

    app = create_app(settings=settings, setup_log=False)

    assert type(app.wsgi_app).__name__ == "ProxyFix"


def test_proxyfix_not_applied_for_local_only(settings):
    settings.cloudflare.enabled = False
    settings.cloudflare.hostname = ""

    app = create_app(settings=settings, setup_log=False)

    assert type(app.wsgi_app).__name__ != "ProxyFix"


def test_proxyfix_trusts_only_one_hop(settings):
    """不可以盲目相信任意 Proxy Header。"""
    settings.cloudflare.hostname = "familyreward.longhopick.com"

    app = create_app(settings=settings, setup_log=False)

    assert app.wsgi_app.x_for == 1
    assert app.wsgi_app.x_proto == 1
    assert app.wsgi_app.x_host == 1


def test_forwarded_proto_is_honoured(settings):
    """經過 tunnel 時，X-Forwarded-Proto: https 要讓 Flask 認為是 https。"""
    settings.cloudflare.hostname = "familyreward.longhopick.com"
    app = create_app(settings=settings, setup_log=False)
    app.config.update(TESTING=True)

    seen = {}

    @app.route("/__scheme")
    def scheme():  # noqa: ANN202
        from flask import request

        seen["scheme"] = request.scheme
        return "ok"

    client = app.test_client()
    client.get("/__scheme", headers={"X-Forwarded-Proto": "https"})

    assert seen["scheme"] == "https"


# --------------------------------------------------------------------------
# 後台設定頁顯示公開網址
# --------------------------------------------------------------------------


def test_settings_page_shows_public_hostname(settings, login_admin):  # noqa: ANN001
    settings.cloudflare.hostname = "familyreward.longhopick.com"
    app = create_app(settings=settings, setup_log=False)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    from family_reward.extensions import db as _db
    from family_reward.services import admin_service
    from tests.conftest import ADMIN_PASSWORD, ADMIN_USERNAME

    with app.app_context():
        _db.create_all()
        admin_service.ensure_initial_admin(ADMIN_USERNAME, ADMIN_PASSWORD)

    client = app.test_client()
    client.post(
        "/login/admin",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        follow_redirects=True,
    )
    body = client.get("/admin/settings").get_data(as_text=True)

    assert "familyreward.longhopick.com" in body

    with app.app_context():
        _db.session.remove()
        _db.drop_all()


# --------------------------------------------------------------------------
# 設定小幫手腳本
# --------------------------------------------------------------------------


def test_cloudflare_setup_script_runs():
    """cloudflare_setup.py 應該能在任何環境下正常結束，不能拋例外。"""
    import subprocess
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent
    script = project_root / "scripts" / "cloudflare_setup.py"

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        timeout=120,
        cwd=str(project_root),
    )
    output = result.stdout.decode("utf-8", errors="replace")

    assert result.returncode in (0, 1)
    assert "Cloudflare Tunnel" in output
    # 不得洩漏憑證內容
    assert "BEGIN" not in output
    assert "token" not in output.lower() or "--token" in output.lower()


def test_cloudflare_setup_bat_is_ascii_crlf():
    """和其他 BAT 一樣的規則：純 ASCII + CRLF。"""
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent
    path = project_root / "cloudflare-setup.bat"
    assert path.exists()

    data = path.read_bytes()
    data.decode("ascii")  # 非 ASCII 會直接拋例外
    assert data.count(b"\n") - data.count(b"\r\n") == 0
