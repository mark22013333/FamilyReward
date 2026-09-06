"""管理者帳號服務。"""

from __future__ import annotations

import logging

from ..exceptions import ValidationError
from ..extensions import db
from ..models import ActorType, AdminUser, AuditAction
from ..utils.timezone import utcnow
from . import audit_service

logger = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 8
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 50


def get_by_username(username: str) -> AdminUser | None:
    return db.session.execute(
        db.select(AdminUser).where(AdminUser.username == username.strip())
    ).scalar_one_or_none()


def count_admins() -> int:
    from sqlalchemy import func

    return int(db.session.execute(db.select(func.count(AdminUser.id))).scalar_one())


def ensure_initial_admin(username: str, initial_password: str) -> AdminUser | None:
    """第一次啟動時建立初始管理者。已經有管理者就什麼都不做。

    回傳新建立的帳號，若原本就存在則回傳 None。
    """
    if count_admins() > 0:
        # 帳號已存在時，config / .env 的設定值一律不生效。
        # 這件事很容易誤會（使用者改了 .env 卻登不進去），因此主動警告。
        _warn_if_settings_look_ignored(username, initial_password)
        return None

    if not initial_password:
        raise ValidationError(
            "尚未設定 ADMIN_INITIAL_PASSWORD。請參考 .env.example 建立 .env 檔。"
        )

    admin = AdminUser(username=username.strip(), active=True)
    # is_initial=True → 後台會固定顯示「請修改預設管理員密碼」提醒。
    admin.set_password(initial_password, is_initial=True)

    try:
        db.session.add(admin)
        db.session.flush()
        audit_service.record(
            AuditAction.CREATE_ADMIN,
            actor_type=ActorType.SYSTEM,
            entity_type="ADMIN_USER",
            entity_id=admin.id,
            description=f"建立初始管理者「{admin.username}」",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    logger.info("Initial admin created: %s", admin.username)
    return admin


def _warn_if_settings_look_ignored(username: str, initial_password: str) -> None:
    """帳號已存在時，若 config / .env 的值和實際不符就提出警告。

    背景：`admin.initial_username` 與 `ADMIN_INITIAL_PASSWORD` 都只在
    「第一次建立帳號」時生效。使用者常誤以為改了就會套用，結果登不進去
    又不知道原因。這裡在啟動 log 明確說出來。

    注意：只比對「是否相符」，絕不把密碼內容寫進 log。
    """
    admins = list(db.session.execute(db.select(AdminUser)).scalars())
    if not admins:
        return

    configured = (username or "").strip()
    if configured and not any(a.username == configured for a in admins):
        actual = "、".join(a.username for a in admins)
        logger.warning(
            "config.yaml 的 admin.initial_username 是「%s」，但資料庫裡的管理員是「%s」。"
            "這個設定只在第一次建立帳號時生效，現在不會套用。"
            "要改帳號請登入後台的「設定」頁。",
            configured,
            actual,
        )

    if initial_password and not any(
        a.verify_password(initial_password) for a in admins
    ):
        logger.warning(
            ".env 的 ADMIN_INITIAL_PASSWORD 和目前管理員的密碼不同。"
            "這個設定只在第一次建立帳號時生效，改了不會套用到既有帳號。"
            "忘記密碼請執行：.venv\\Scripts\\python.exe scripts\\reset_admin_password.py"
        )


def record_login(admin: AdminUser) -> None:
    try:
        admin.last_login_at = utcnow()
        audit_service.record(
            AuditAction.LOGIN_SUCCESS,
            actor_type=ActorType.ADMIN,
            actor_id=admin.id,
            actor_name=admin.username,
            entity_type="ADMIN_USER",
            entity_id=admin.id,
            description=f"管理者「{admin.username}」登入成功",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def change_username(admin: AdminUser, new_username: str, current_password: str) -> None:
    """修改管理者帳號。

    要求輸入目前密碼，避免有人趁著別人沒登出時偷改帳號。

    注意：`config.yaml` 的 `admin.initial_username` 只在「第一次建立帳號」
    時生效，之後一律以資料庫為準 —— 設定檔不應該有能力覆寫既有帳號。
    """
    new_username = (new_username or "").strip()

    if not admin.verify_password(current_password):
        raise ValidationError("目前的密碼不正確。")

    if not new_username:
        raise ValidationError("請輸入新的帳號。")
    if not (MIN_USERNAME_LENGTH <= len(new_username) <= MAX_USERNAME_LENGTH):
        raise ValidationError(
            f"帳號長度必須介於 {MIN_USERNAME_LENGTH} ~ {MAX_USERNAME_LENGTH} 個字元。"
        )
    # 帳號會出現在登入表單與稽核紀錄，限制字元避免混淆與前後空白問題。
    #
    # 注意：這裡不能用 str.isalnum()，因為它對中文（例如「爸爸媽媽」）也回傳
    # True，會讓中文帳號通過驗證，與錯誤訊息承諾的「英文字母、數字」不符。
    # 因此明確限定 ASCII 字元集。
    if not all(
        ("a" <= char <= "z") or ("A" <= char <= "Z") or ("0" <= char <= "9")
        or char in "._-"
        for char in new_username
    ):
        raise ValidationError("帳號只能使用英文字母、數字，以及 . _ - 這三種符號。")
    if new_username == admin.username:
        raise ValidationError("新帳號和目前的帳號一樣。")

    existing = get_by_username(new_username)
    if existing is not None and existing.id != admin.id:
        raise ValidationError("這個帳號已經有人使用了。")

    old_username = admin.username

    try:
        admin.username = new_username
        audit_service.record(
            AuditAction.CHANGE_USERNAME,
            actor_type=ActorType.ADMIN,
            actor_id=admin.id,
            actor_name=new_username,
            entity_type="ADMIN_USER",
            entity_id=admin.id,
            description=f"管理者帳號由「{old_username}」改為「{new_username}」",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    logger.info("Admin username changed: %s -> %s", old_username, new_username)


def change_password(
    admin: AdminUser, current_password: str, new_password: str, confirm_password: str
) -> None:
    """修改管理者密碼。"""
    if not admin.verify_password(current_password):
        raise ValidationError("目前的密碼不正確。")
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(f"新密碼至少要 {MIN_PASSWORD_LENGTH} 個字元。")
    if new_password != confirm_password:
        raise ValidationError("兩次輸入的新密碼不一樣。")
    if new_password == current_password:
        raise ValidationError("新密碼不能和目前的密碼一樣。")

    try:
        admin.set_password(new_password, is_initial=False)
        audit_service.record(
            AuditAction.CHANGE_PASSWORD,
            actor_type=ActorType.ADMIN,
            actor_id=admin.id,
            actor_name=admin.username,
            entity_type="ADMIN_USER",
            entity_id=admin.id,
            description=f"管理者「{admin.username}」修改密碼",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def record_login_failure(username: str, reason: str = "密碼錯誤") -> None:
    """記錄登入失敗。注意：絕不記錄嘗試的密碼內容。"""
    try:
        audit_service.record(
            AuditAction.LOGIN_FAILURE,
            actor_type=ActorType.ADMIN,
            actor_name=username[:50],
            entity_type="ADMIN_USER",
            description=f"管理者登入失敗（{reason}）",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.warning("無法寫入登入失敗紀錄。")
