"""小孩通知服務。

用途：家長批准任務後，小孩下一次進入 Dashboard 顯示一次慶祝畫面 + Confetti。
讀取後立刻標記 read_at，所以重新整理不會一直重播動畫。
"""

from __future__ import annotations

from ..extensions import db
from ..models import Notification, NotificationType
from ..utils.timezone import utcnow


def create(
    *,
    child_id: int,
    notification_type: NotificationType | str,
    title: str,
    message: str,
    points: int | None = None,
) -> Notification:
    """建立通知（不 commit，由呼叫端的 transaction 統一處理）。"""
    notification = Notification(
        child_id=child_id,
        type=str(notification_type),
        title=title,
        message=message,
        points=points,
    )
    db.session.add(notification)
    return notification


def pop_unread(child_id: int, limit: int = 5) -> list[Notification]:
    """取出未讀通知並立即標記為已讀。

    回傳的物件已經 expunge，即使之後 session 變動也能安全在模板中使用。
    """
    notifications = list(
        db.session.execute(
            db.select(Notification)
            .where(Notification.child_id == child_id, Notification.read_at.is_(None))
            .order_by(Notification.created_at.asc())
            .limit(limit)
        ).scalars()
    )
    if not notifications:
        return []

    now = utcnow()
    for notification in notifications:
        notification.read_at = now

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return notifications


def count_unread(child_id: int) -> int:
    from sqlalchemy import func

    return int(
        db.session.execute(
            db.select(func.count(Notification.id)).where(
                Notification.child_id == child_id, Notification.read_at.is_(None)
            )
        ).scalar_one()
    )
