"""用 Email 寄出資料庫備份（異地保存）。

備份檔只放在同一台電腦上，電腦壞掉就一起不見。
寄到信箱等於多一份放在別處的副本。

流程：備份檔（.db）→ 壓成 ZIP（通常可以縮到原本的 1/5 以下）→ SMTP 寄出。

只用標準函式庫（smtplib / email），不需要額外安裝套件。
SMTP 密碼一律從 .env 的 SMTP_PASSWORD 讀取，不寫進 config.yaml，
也不會出現在 log 或稽核紀錄裡。
"""

from __future__ import annotations

import io
import logging
import smtplib
import ssl
import zipfile
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from ..config import Settings
from ..exceptions import AppError
from ..utils.timezone import now_local
from . import backup_service

logger = logging.getLogger(__name__)

#: 多數信箱的附件上限是 20 ~ 25 MB，保守一點。
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


class EmailError(AppError):
    """寄信失敗。message 可以直接顯示給家長看。"""

    default_message = "備份信沒有寄出去，請查看 log。"


def is_configured(settings: Settings) -> bool:
    """寄信功能是否已經設定好、可以使用。"""
    email = settings.email
    return bool(email.enabled and email.smtp_host and email.recipients)


def masked_recipients(settings: Settings) -> list[str]:
    """後台顯示用：把信箱中間遮起來，例如 ma***@gmail.com。"""
    masked: list[str] = []
    for address in settings.email.recipients:
        local, _, domain = address.partition("@")
        visible = local[:2] if len(local) > 2 else local[:1]
        masked.append(f"{visible}***@{domain}")
    return masked


def resolve_backup(settings: Settings, filename: str) -> Path:
    """只允許寄出「備份目錄清單裡」的檔案，避免被拿來寄任意檔案。"""
    for info in backup_service.list_backups(settings.backup.directory):
        if info.path.name == filename:
            return info.path
    raise EmailError("找不到這個備份檔，可能已經被刪除了。")


def build_attachment(backup_path: Path) -> tuple[str, bytes]:
    """把 .db 壓成 ZIP，回傳 (檔名, 內容)。"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(backup_path, arcname=backup_path.name)
    data = buffer.getvalue()
    if len(data) > MAX_ATTACHMENT_BYTES:
        size_mb = round(len(data) / 1024 / 1024, 1)
        raise EmailError(
            f"備份壓縮後仍有 {size_mb} MB，超過信箱附件上限，"
            "請改用隨身碟或雲端硬碟保存。"
        )
    return backup_path.with_suffix(".zip").name, data


def build_message(settings: Settings, backup_path: Path) -> EmailMessage:
    email = settings.email
    sender = email.from_address or email.username
    generated_at = now_local(settings.app.timezone).strftime("%Y/%m/%d %H:%M")
    attachment_name, attachment = build_attachment(backup_path)
    db_size_mb = round(backup_path.stat().st_size / 1024 / 1024, 2)

    message = EmailMessage()
    message["Subject"] = f"[{settings.app.name}] 資料庫備份 {generated_at}"
    message["From"] = sender
    message["To"] = ", ".join(email.recipients)
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=sender.partition("@")[2] or None)

    public_url = (
        f"https://{settings.cloudflare.hostname}" if settings.cloudflare.hostname else ""
    )
    message.set_content(
        f"""這是「{settings.app.name}」自動寄出的資料庫備份。

備份檔：{backup_path.name}
大　小：{db_size_mb} MB（附件已壓縮成 ZIP）
寄出時間：{generated_at}
{f"網　址：{public_url}" if public_url else ""}

如何還原
--------
1. 停止系統（stop.bat，或 Linux 上 systemctl stop）
2. 解壓縮附件，把 .db 檔放進專案的 backup 資料夾
3. 執行 restore.bat（或 scripts/restore_db.py），選擇這個備份

注意
----
備份裡有小孩的資料與點數紀錄，請不要轉寄給其他人。
密碼與 PIN 都是雜湊過的，無法從備份直接看出原本的值。
"""
    )
    message.add_attachment(
        attachment,
        maintype="application",
        subtype="zip",
        filename=attachment_name,
    )
    return message


def _open_connection(settings: Settings) -> smtplib.SMTP:
    email = settings.email
    if email.security == "ssl":
        return smtplib.SMTP_SSL(
            email.smtp_host,
            email.smtp_port,
            timeout=email.timeout_seconds,
            context=ssl.create_default_context(),
        )
    connection = smtplib.SMTP(email.smtp_host, email.smtp_port, timeout=email.timeout_seconds)
    if email.security == "starttls":
        connection.starttls(context=ssl.create_default_context())
    return connection


def send_backup(settings: Settings, backup_path: Path) -> list[str]:
    """把備份寄給 config.yaml 設定的所有收件人，回傳收件人清單。

    失敗時拋出 EmailError（訊息可直接顯示），不會把 SMTP 密碼寫進 log。
    """
    if not is_configured(settings):
        raise EmailError(
            "還沒有設定寄信功能。請在 config/config.yaml 的 email 區段設定 SMTP，"
            "並在 .env 填入 SMTP_PASSWORD，然後重新啟動。"
        )
    if not backup_path.exists():
        raise EmailError("找不到這個備份檔，可能已經被刪除了。")

    message = build_message(settings, backup_path)
    email = settings.email

    try:
        with _open_connection(settings) as connection:
            if email.username:
                connection.login(email.username, settings.smtp_password)
            connection.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        logger.warning("SMTP authentication failed (code=%s)", exc.smtp_code)
        raise EmailError(
            "信箱帳號或密碼不正確。Gmail 請使用「應用程式密碼」，不是平常登入的密碼。"
        ) from exc
    except smtplib.SMTPRecipientsRefused as exc:
        logger.warning("SMTP recipients refused: %s", list(exc.recipients))
        raise EmailError("收件人信箱被拒收，請檢查 email.recipients。") from exc
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("Sending backup email failed: %s: %s", type(exc).__name__, exc)
        raise EmailError(
            f"連不上寄信伺服器（{email.smtp_host}:{email.smtp_port}），"
            "請確認網路與 SMTP 設定。"
        ) from exc

    logger.info(
        "Backup emailed: %s -> %d recipient(s)", backup_path.name, len(email.recipients)
    )
    return list(email.recipients)
