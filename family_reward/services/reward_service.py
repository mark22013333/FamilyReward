"""禮物管理服務。"""

from __future__ import annotations

from ..exceptions import NotFoundError, ValidationError
from ..extensions import db
from ..models import ActorType, AuditAction, Reward
from . import audit_service


def list_rewards(*, only_active: bool = True) -> list[Reward]:
    query = db.select(Reward)
    if only_active:
        query = query.where(Reward.active.is_(True))
    return list(
        db.session.execute(
            query.order_by(Reward.points_required.asc(), Reward.id.asc())
        ).scalars()
    )


def get_reward(reward_id: int) -> Reward:
    reward = db.session.get(Reward, reward_id)
    if reward is None:
        raise NotFoundError("找不到這個禮物耶 🎁")
    return reward


def create_reward(
    *,
    name: str,
    points_required: int,
    icon: str = "🎁",
    description: str | None = None,
    quantity: int | None = None,
    admin_id: int,
    admin_name: str | None = None,
) -> Reward:
    _validate(name, points_required, quantity)

    reward = Reward(
        name=name.strip(),
        description=(description or "").strip() or None,
        icon=icon or "🎁",
        points_required=points_required,
        quantity=quantity,
        active=True,
    )
    try:
        db.session.add(reward)
        db.session.flush()
        audit_service.record(
            AuditAction.CREATE_REWARD,
            actor_type=ActorType.ADMIN,
            actor_id=admin_id,
            actor_name=admin_name,
            entity_type="REWARD",
            entity_id=reward.id,
            description=f"建立禮物「{reward.name}」需要 {reward.points_required} ⭐",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return reward


def update_reward(
    reward_id: int,
    *,
    name: str,
    points_required: int,
    icon: str = "🎁",
    description: str | None = None,
    quantity: int | None = None,
    active: bool = True,
    admin_id: int,
    admin_name: str | None = None,
) -> Reward:
    """修改禮物。

    注意：既有的兌換紀錄保存了 snapshot，因此改名不會影響歷史。
    """
    _validate(name, points_required, quantity)
    reward = get_reward(reward_id)

    try:
        reward.name = name.strip()
        reward.description = (description or "").strip() or None
        reward.icon = icon or "🎁"
        reward.points_required = points_required
        reward.quantity = quantity
        reward.active = active

        audit_service.record(
            AuditAction.UPDATE_REWARD if active else AuditAction.DEACTIVATE_REWARD,
            actor_type=ActorType.ADMIN,
            actor_id=admin_id,
            actor_name=admin_name,
            entity_type="REWARD",
            entity_id=reward.id,
            description=f"修改禮物「{reward.name}」",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return reward


def deactivate_reward(
    reward_id: int, *, admin_id: int, admin_name: str | None = None
) -> Reward:
    """停用禮物（不做實體刪除，保留歷史完整性）。"""
    reward = get_reward(reward_id)
    try:
        reward.active = False
        audit_service.record(
            AuditAction.DEACTIVATE_REWARD,
            actor_type=ActorType.ADMIN,
            actor_id=admin_id,
            actor_name=admin_name,
            entity_type="REWARD",
            entity_id=reward.id,
            description=f"停用禮物「{reward.name}」",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return reward


def _validate(name: str, points_required: int, quantity: int | None) -> None:
    if not name or not name.strip():
        raise ValidationError("請幫禮物取個名字吧！")
    if len(name.strip()) > 100:
        raise ValidationError("禮物名稱不能超過 100 個字。")
    if not (1 <= points_required <= 10000):
        raise ValidationError("需要的點數必須介於 1 ~ 10000。")
    if quantity is not None and quantity < 0:
        raise ValidationError("數量不能是負數。")
