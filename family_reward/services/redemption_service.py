"""禮物兌換流程。

固定流程：

    小孩提出申請 → REQUESTED → 家長確認
        → 重新計算 Balance（不相信畫面上的舊數字）
        → 重新檢查 Reward 庫存
        → 新增 -points 的 REDEEM 交易
        → 扣庫存
        → APPROVED

以上所有步驟都在同一個 transaction 內完成，避免一半成功一半失敗。

小孩按一次「我要這個！」不會直接扣點，一定要家長確認。
"""

from __future__ import annotations

from sqlalchemy.orm import selectinload

from ..exceptions import (
    InsufficientPointsError,
    InvalidStateError,
    NotFoundError,
    OutOfStockError,
    PermissionDeniedError,
)
from ..extensions import db
from ..models import (
    ActorType,
    AuditAction,
    Child,
    NotificationType,
    RedemptionStatus,
    Reward,
    RewardRedemption,
    SourceType,
    TransactionType,
)
from ..utils.timezone import utcnow
from . import audit_service, notification_service, point_service


def request_redemption(child: Child, reward_id: int) -> RewardRedemption:
    """小孩提出兌換申請。此時「不」扣點，只是建立一筆 REQUESTED。"""
    reward = db.session.get(Reward, reward_id)
    if reward is None or not reward.active:
        raise NotFoundError("這個禮物暫時看不到耶 🎁")

    if not reward.in_stock:
        raise OutOfStockError("這個禮物暫時沒有庫存了，先看看別的吧！🎁")

    # 前端會把不夠的禮物鎖起來，但後端一定要再檢查一次。
    balance = point_service.get_balance(child.id)
    if balance < reward.points_required:
        shortage = reward.points_required - balance
        raise InsufficientPointsError(
            f"再收集 {shortage} 顆星星就可以換這個禮物囉！💪"
        )

    # 同一個禮物不重複申請，避免小孩連按產生一堆待審。
    existing = db.session.execute(
        db.select(RewardRedemption.id).where(
            RewardRedemption.child_id == child.id,
            RewardRedemption.reward_id == reward_id,
            RewardRedemption.status == RedemptionStatus.REQUESTED.value,
        )
    ).first()
    if existing is not None:
        raise InvalidStateError("已經跟爸爸媽媽說過囉，等一下下！⏳")

    redemption = RewardRedemption(
        child_id=child.id,
        reward_id=reward.id,
        reward_name_snapshot=reward.name,
        reward_icon_snapshot=reward.icon,
        points=reward.points_required,
        status=RedemptionStatus.REQUESTED.value,
        requested_at=utcnow(),
    )

    try:
        db.session.add(redemption)
        db.session.flush()
        audit_service.record(
            AuditAction.REQUEST_REWARD,
            actor_type=ActorType.CHILD,
            actor_id=child.id,
            actor_name=child.name,
            entity_type="REWARD_REDEMPTION",
            entity_id=redemption.id,
            description=f"{child.name} 申請兌換「{reward.name}」{reward.points_required} ⭐",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return redemption


def approve_redemption(
    redemption_id: int, admin_id: int, admin_name: str | None = None
) -> RewardRedemption:
    """家長批准兌換。

    在同一個 transaction 內重新檢查餘額與庫存，
    絕不使用畫面上顯示的舊數字，避免 race condition 造成超額兌換或超賣。
    """
    redemption = db.session.get(RewardRedemption, redemption_id)
    if redemption is None:
        raise NotFoundError("找不到這筆兌換申請。")

    if redemption.status != RedemptionStatus.REQUESTED.value:
        if redemption.status == RedemptionStatus.APPROVED.value:
            raise InvalidStateError("這個禮物已經換過囉！")
        raise InvalidStateError("這筆申請目前不能確認喔。")

    child = db.session.get(Child, redemption.child_id)
    if child is None:
        raise NotFoundError("找不到這位小朋友。")

    reward = db.session.get(Reward, redemption.reward_id)
    if reward is None:
        raise NotFoundError("找不到這個禮物。")

    # --- 在 transaction 內重新驗證，不相信任何舊資料 ---
    balance = point_service.get_balance(child.id)
    if balance < redemption.points:
        shortage = redemption.points - balance
        raise InsufficientPointsError(
            f"{child.name} 目前只有 {balance} ⭐，還差 {shortage} ⭐ 才能兌換。"
        )

    if not reward.in_stock:
        raise OutOfStockError(f"「{reward.name}」已經沒有庫存了。")

    try:
        point_service.add_transaction(
            child_id=child.id,
            transaction_type=TransactionType.REDEEM,
            points=-redemption.points,
            source_type=SourceType.REWARD_REDEMPTION,
            source_id=redemption.id,
            description=f"兌換「{redemption.reward_name_snapshot}」",
            created_by=admin_id,
        )

        if not reward.is_unlimited:
            reward.quantity = (reward.quantity or 0) - 1

        redemption.status = RedemptionStatus.APPROVED.value
        redemption.approved_at = utcnow()
        redemption.approved_by = admin_id

        notification_service.create(
            child_id=child.id,
            notification_type=NotificationType.REWARD_APPROVED,
            title="🎁 換到禮物囉！",
            message=f"「{redemption.reward_name_snapshot}」兌換成功！",
            points=-redemption.points,
        )

        audit_service.record(
            AuditAction.APPROVE_REWARD,
            actor_type=ActorType.ADMIN,
            actor_id=admin_id,
            actor_name=admin_name,
            entity_type="REWARD_REDEMPTION",
            entity_id=redemption.id,
            description=(
                f"批准 {child.name} 兌換「{redemption.reward_name_snapshot}」"
                f"-{redemption.points} ⭐"
            ),
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return redemption


def reject_redemption(
    redemption_id: int,
    admin_id: int,
    reason: str = "",
    admin_name: str | None = None,
) -> RewardRedemption:
    """家長婉拒兌換。不扣任何點數。"""
    redemption = db.session.get(RewardRedemption, redemption_id)
    if redemption is None:
        raise NotFoundError("找不到這筆兌換申請。")
    if redemption.status != RedemptionStatus.REQUESTED.value:
        raise InvalidStateError("這筆申請目前不能婉拒喔。")

    child = db.session.get(Child, redemption.child_id)
    reason = reason.strip() or "這次先留著，下次再換喔！"

    try:
        redemption.status = RedemptionStatus.REJECTED.value
        redemption.rejection_reason = reason
        redemption.cancelled_at = utcnow()

        notification_service.create(
            child_id=redemption.child_id,
            notification_type=NotificationType.REWARD_REJECTED,
            title="🎁 這次先不換喔",
            message=f"「{redemption.reward_name_snapshot}」：{reason}",
        )

        audit_service.record(
            AuditAction.REJECT_REWARD,
            actor_type=ActorType.ADMIN,
            actor_id=admin_id,
            actor_name=admin_name,
            entity_type="REWARD_REDEMPTION",
            entity_id=redemption.id,
            description=(
                f"婉拒 {child.name if child else ''} 兌換"
                f"「{redemption.reward_name_snapshot}」"
            ),
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return redemption


def complete_redemption(
    redemption_id: int, admin_id: int, admin_name: str | None = None
) -> RewardRedemption:
    """標記禮物已經實際交付給小孩。點數在 APPROVED 時就已扣除。"""
    redemption = db.session.get(RewardRedemption, redemption_id)
    if redemption is None:
        raise NotFoundError("找不到這筆兌換申請。")
    if redemption.status != RedemptionStatus.APPROVED.value:
        raise InvalidStateError("這筆申請還不能標記為已完成。")

    try:
        redemption.status = RedemptionStatus.COMPLETED.value
        redemption.completed_at = utcnow()
        audit_service.record(
            AuditAction.COMPLETE_REWARD,
            actor_type=ActorType.ADMIN,
            actor_id=admin_id,
            actor_name=admin_name,
            entity_type="REWARD_REDEMPTION",
            entity_id=redemption.id,
            description=f"「{redemption.reward_name_snapshot}」已交付",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return redemption


def get_redemption_for_child(redemption_id: int, child_id: int) -> RewardRedemption:
    """物件層級授權：小孩只能看自己的兌換紀錄。"""
    redemption = db.session.get(RewardRedemption, redemption_id)
    if redemption is None:
        raise NotFoundError("找不到這筆兌換紀錄。")
    if redemption.child_id != child_id:
        raise PermissionDeniedError("這不是你的兌換紀錄喔！")
    return redemption


def list_pending_redemptions() -> list[RewardRedemption]:
    return list(
        db.session.execute(
            db.select(RewardRedemption)
            .where(RewardRedemption.status == RedemptionStatus.REQUESTED.value)
            .options(selectinload(RewardRedemption.child))
            .order_by(RewardRedemption.requested_at.asc())
        ).scalars()
    )


def count_pending_redemptions() -> int:
    from sqlalchemy import func

    return int(
        db.session.execute(
            db.select(func.count(RewardRedemption.id)).where(
                RewardRedemption.status == RedemptionStatus.REQUESTED.value
            )
        ).scalar_one()
    )


def list_redemptions_for_child(child_id: int, limit: int = 50) -> list[RewardRedemption]:
    return list(
        db.session.execute(
            db.select(RewardRedemption)
            .where(RewardRedemption.child_id == child_id)
            .order_by(RewardRedemption.requested_at.desc())
            .limit(limit)
        ).scalars()
    )


def list_all_redemptions(limit: int = 200) -> list[RewardRedemption]:
    return list(
        db.session.execute(
            db.select(RewardRedemption)
            .options(selectinload(RewardRedemption.child))
            .order_by(RewardRedemption.requested_at.desc())
            .limit(limit)
        ).scalars()
    )


def list_redemptions_in_range(
    child_id: int | None, start: date, end: date, tz_name: str = "Asia/Taipei"
) -> list[RewardRedemption]:
    """區間內的兌換紀錄（舊到新，給匯出用）。

    `requested_at` 存 naive UTC，所以和 point_service 一樣要做時區轉換 ——
    使用者說的「三月」是當地日期。

    `child_id=None` 代表所有小孩。純讀取。
    """
    from datetime import datetime, time, timedelta, timezone

    from ..utils.timezone import get_tz

    tz = get_tz(tz_name)
    local_start = datetime.combine(start, time.min, tzinfo=tz)
    local_end = datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz)
    utc_start = local_start.astimezone(timezone.utc).replace(tzinfo=None)
    utc_end = local_end.astimezone(timezone.utc).replace(tzinfo=None)

    query = db.select(RewardRedemption).where(
        RewardRedemption.requested_at >= utc_start,
        RewardRedemption.requested_at < utc_end,
    )
    if child_id is not None:
        query = query.where(RewardRedemption.child_id == child_id)

    return list(
        db.session.execute(
            query.options(selectinload(RewardRedemption.child)).order_by(
                RewardRedemption.requested_at.asc(), RewardRedemption.id.asc()
            )
        ).scalars()
    )


def get_pending_reward_ids(child_id: int) -> set[int]:
    """取得小孩目前已申請、等待確認的禮物 ID，畫面用來顯示「等待中」。"""
    return set(
        db.session.execute(
            db.select(RewardRedemption.reward_id).where(
                RewardRedemption.child_id == child_id,
                RewardRedemption.status == RedemptionStatus.REQUESTED.value,
            )
        ).scalars()
    )
