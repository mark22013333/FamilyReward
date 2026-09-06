"""小孩管理服務。"""

from __future__ import annotations

from datetime import date

from ..exceptions import NotFoundError, ValidationError
from ..extensions import db
from ..models import AVATAR_CHOICES, ActorType, AuditAction, Child, Theme
from . import audit_service


def list_children(*, only_active: bool = True) -> list[Child]:
    query = db.select(Child)
    if only_active:
        query = query.where(Child.active.is_(True))
    return list(db.session.execute(query.order_by(Child.id.asc())).scalars())


def get_child(child_id: int) -> Child:
    child = db.session.get(Child, child_id)
    if child is None:
        raise NotFoundError("找不到這位小朋友。")
    return child


def create_child(
    *,
    name: str,
    pin: str,
    nickname: str | None = None,
    avatar: str = "🐼",
    theme: str = Theme.SUNNY.value,
    birthday: date | None = None,
    pin_length: int = 4,
    admin_id: int,
    admin_name: str | None = None,
) -> Child:
    _validate_name(name)
    _validate_pin(pin, pin_length)
    avatar = _validate_avatar(avatar)
    theme = _validate_theme(theme)

    child = Child(
        name=name.strip(),
        nickname=(nickname or "").strip() or None,
        avatar=avatar,
        theme=theme,
        birthday=birthday,
        active=True,
    )
    child.set_pin(pin)

    try:
        db.session.add(child)
        db.session.flush()
        audit_service.record(
            AuditAction.CREATE_CHILD,
            actor_type=ActorType.ADMIN,
            actor_id=admin_id,
            actor_name=admin_name,
            entity_type="CHILD",
            entity_id=child.id,
            description=f"建立小孩「{child.name}」",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return child


def update_child(
    child_id: int,
    *,
    name: str,
    nickname: str | None = None,
    avatar: str = "🐼",
    theme: str = Theme.SUNNY.value,
    birthday: date | None = None,
    active: bool = True,
    pin: str | None = None,
    pin_length: int = 4,
    admin_id: int,
    admin_name: str | None = None,
) -> Child:
    """修改小孩資料。pin 留空代表不變更 PIN。"""
    _validate_name(name)
    avatar = _validate_avatar(avatar)
    theme = _validate_theme(theme)
    if pin:
        _validate_pin(pin, pin_length)

    child = get_child(child_id)

    try:
        child.name = name.strip()
        child.nickname = (nickname or "").strip() or None
        child.avatar = avatar
        child.theme = theme
        child.birthday = birthday
        child.active = active
        if pin:
            child.set_pin(pin)

        audit_service.record(
            AuditAction.UPDATE_CHILD if active else AuditAction.DEACTIVATE_CHILD,
            actor_type=ActorType.ADMIN,
            actor_id=admin_id,
            actor_name=admin_name,
            entity_type="CHILD",
            entity_id=child.id,
            description=(
                f"修改小孩「{child.name}」" + ("（同時更新 PIN）" if pin else "")
            ),
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return child


def deactivate_child(
    child_id: int, *, admin_id: int, admin_name: str | None = None
) -> Child:
    """停用小孩（軟刪除，保留所有歷史紀錄）。"""
    child = get_child(child_id)
    try:
        child.active = False
        audit_service.record(
            AuditAction.DEACTIVATE_CHILD,
            actor_type=ActorType.ADMIN,
            actor_id=admin_id,
            actor_name=admin_name,
            entity_type="CHILD",
            entity_id=child.id,
            description=f"停用小孩「{child.name}」",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return child


def _validate_name(name: str) -> None:
    if not name or not name.strip():
        raise ValidationError("請填寫名字喔！")
    if not (1 <= len(name.strip()) <= 50):
        raise ValidationError("名字長度必須介於 1 ~ 50 個字。")


def _validate_pin(pin: str, pin_length: int) -> None:
    if not pin or not pin.isdigit():
        raise ValidationError(f"PIN 必須是 {pin_length} 個數字。")
    if len(pin) != pin_length:
        raise ValidationError(f"PIN 必須剛好 {pin_length} 位數。")


def _validate_avatar(avatar: str) -> str:
    """頭像只能從系統清單挑選，禁止任意輸入。"""
    if avatar not in AVATAR_CHOICES:
        return AVATAR_CHOICES[4]  # 預設 🐼
    return avatar


def _validate_theme(theme: str) -> str:
    """Theme 必須由系統提供，禁止使用者輸入任意 CSS。"""
    if not Theme.has_value(theme):
        return Theme.SUNNY.value
    return theme
