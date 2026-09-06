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
