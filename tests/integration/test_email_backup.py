"""備份寄到信箱的測試。

一律用假的 SMTP 物件，不會真的連網寄信。
"""

from __future__ import annotations

import io
import smtplib
import sqlite3
import zipfile

import pytest

from family_reward.config import ConfigError, EmailConfig, validate_settings
from family_reward.models import AuditLog
from family_reward.services import backup_service, email_service


class FakeSMTP:
    """記錄寄出的信，模擬 smtplib.SMTP / SMTP_SSL。"""

    sent: list = []
    logins: list = []
    starttls_called = False
    fail_with: Exception | None = None

    def __init__(self, host, port, timeout=None, context=None):  # noqa: ANN001
        self.host = host
        self.port = port

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, *exc):  # noqa: ANN002, ANN204
        return False

    def starttls(self, context=None):  # noqa: ANN001, ANN201
        FakeSMTP.starttls_called = True

    def login(self, username, password):  # noqa: ANN001, ANN201
        if FakeSMTP.fail_with is not None:
            raise FakeSMTP.fail_with
        FakeSMTP.logins.append((username, password))

    def send_message(self, message):  # noqa: ANN001, ANN201
        FakeSMTP.sent.append(message)


@pytest.fixture()
def fake_smtp(monkeypatch):  # noqa: ANN001, ANN201
    FakeSMTP.sent = []
    FakeSMTP.logins = []
    FakeSMTP.starttls_called = False
    FakeSMTP.fail_with = None
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", FakeSMTP)
    return FakeSMTP


@pytest.fixture()
def email_settings(settings):  # noqa: ANN001, ANN201
    settings.email = EmailConfig(
        enabled=True,
        smtp_host="smtp.example.com",
        smtp_port=587,
        security="starttls",
        username="parent@example.com",
        from_address="parent@example.com",
        recipients=["mom@example.com", "dad@example.com"],
    )
    settings.smtp_password = "app-password"
    return settings


def _attachment_db_names(message) -> list[str]:  # noqa: ANN001
    attachment = next(message.iter_attachments())
    with zipfile.ZipFile(io.BytesIO(attachment.get_content())) as archive:
        return archive.namelist()


# --------------------------------------------------------------------------
# 設定
# --------------------------------------------------------------------------


def test_email_disabled_by_default_is_valid(settings):
    assert settings.email.enabled is False
    validate_settings(settings)
    assert email_service.is_configured(settings) is False


def test_enabled_email_requires_host_and_recipients(settings):
    settings.email = EmailConfig(enabled=True)
    with pytest.raises(ConfigError) as excinfo:
        validate_settings(settings)
    assert "smtp_host" in str(excinfo.value)
    assert "recipients" in str(excinfo.value)


def test_invalid_security_rejected(email_settings):
    email_settings.email.security = "tls1"
    with pytest.raises(ConfigError):
        validate_settings(email_settings)


def test_recipients_accept_comma_string(tmp_path, monkeypatch):
    from family_reward.config import load_settings

    config = tmp_path / "config.yaml"
    config.write_text(
        "app:\n  env: testing\n"
        "email:\n  enabled: true\n  smtp_host: smtp.example.com\n"
        "  from_address: a@example.com\n  recipients: 'b@example.com, c@example.com'\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("APP_ENV", raising=False)
    loaded = load_settings(config)
    assert loaded.email.recipients == ["b@example.com", "c@example.com"]


def test_masked_recipients_hide_address(email_settings):
    assert email_service.masked_recipients(email_settings) == [
        "mo***@example.com",
        "da***@example.com",
    ]


# --------------------------------------------------------------------------
# 寄信服務
# --------------------------------------------------------------------------


def test_send_backup_attaches_zipped_db(app, email_settings, fake_smtp):
    with app.app_context():
        target = backup_service.create_backup(
            email_settings.database.path, email_settings.backup.directory
        )
        recipients = email_service.send_backup(email_settings, target)

    assert recipients == ["mom@example.com", "dad@example.com"]
    assert fake_smtp.starttls_called
    assert fake_smtp.logins == [("parent@example.com", "app-password")]
    message = fake_smtp.sent[0]
    assert message["To"] == "mom@example.com, dad@example.com"
    assert "資料庫備份" in message["Subject"]
    assert _attachment_db_names(message) == [target.name]


def test_attached_zip_contains_valid_database(app, email_settings, fake_smtp, child):
    with app.app_context():
        target = backup_service.create_backup(
            email_settings.database.path, email_settings.backup.directory
        )
        email_service.send_backup(email_settings, target)

    attachment = next(fake_smtp.sent[0].iter_attachments())
    restored = email_settings.backup.directory / "restored.sqlite"
    with zipfile.ZipFile(io.BytesIO(attachment.get_content())) as archive:
        restored.write_bytes(archive.read(target.name))
    connection = sqlite3.connect(str(restored))
    try:
        names = [row[0] for row in connection.execute("SELECT name FROM child")]
    finally:
        connection.close()
    assert "小明" in names


def test_auth_failure_gives_friendly_message(app, email_settings, fake_smtp):
    fake_smtp.fail_with = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    with app.app_context():
        target = backup_service.create_backup(
            email_settings.database.path, email_settings.backup.directory
        )
        with pytest.raises(email_service.EmailError) as excinfo:
            email_service.send_backup(email_settings, target)
    assert "應用程式密碼" in excinfo.value.message
    assert "app-password" not in excinfo.value.message


def test_resolve_backup_rejects_unknown_file(email_settings):
    with pytest.raises(email_service.EmailError):
        email_service.resolve_backup(email_settings, "../../.env")


# --------------------------------------------------------------------------
# 後台
# --------------------------------------------------------------------------


def test_settings_page_hides_email_button_when_not_configured(client, login_admin):
    login_admin()
    body = client.get("/admin/settings").get_data(as_text=True)
    assert "備份並寄到信箱" not in body
    assert "SMTP_PASSWORD" in body


def test_settings_page_shows_email_button_when_configured(
    client, login_admin, email_settings
):
    login_admin()
    body = client.get("/admin/settings").get_data(as_text=True)
    assert "備份並寄到信箱" in body
    assert "mo***@example.com" in body
    assert "mom@example.com" not in body


def test_email_backup_route_creates_and_sends(
    client, app, login_admin, email_settings, fake_smtp
):
    login_admin()
    response = client.post("/admin/backup/email", follow_redirects=True)

    assert "備份已寄出" in response.get_data(as_text=True)
    assert len(fake_smtp.sent) == 1
    with app.app_context():
        assert len(backup_service.list_backups(email_settings.backup.directory)) == 1
        log = AuditLog.query.filter_by(action="EMAIL_BACKUP").one()
        assert "2 位收件人" in log.description


def test_email_existing_backup_by_filename(
    client, app, login_admin, email_settings, fake_smtp
):
    login_admin()
    client.post("/admin/backup", follow_redirects=True)
    with app.app_context():
        existing = backup_service.get_latest_backup(email_settings.backup.directory)

    client.post(
        "/admin/backup/email",
        data={"filename": existing.path.name},
        follow_redirects=True,
    )

    assert _attachment_db_names(fake_smtp.sent[0]) == [existing.path.name]
    with app.app_context():
        # 寄既有的備份不應該再多建立一份
        assert len(backup_service.list_backups(email_settings.backup.directory)) == 1


def test_email_route_rejects_path_outside_backup_dir(
    client, login_admin, email_settings, fake_smtp
):
    login_admin()
    response = client.post(
        "/admin/backup/email",
        data={"filename": "../test.db"},
        follow_redirects=True,
    )
    assert "找不到這個備份檔" in response.get_data(as_text=True)
    assert fake_smtp.sent == []


def test_email_route_when_not_configured(client, login_admin, fake_smtp):
    login_admin()
    response = client.post("/admin/backup/email", follow_redirects=True)
    assert "還沒有設定寄信功能" in response.get_data(as_text=True)
    assert fake_smtp.sent == []


def test_email_route_requires_admin(client):
    assert client.post("/admin/backup/email").status_code in (302, 400)
