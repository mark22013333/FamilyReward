"""稽核紀錄服務。

注意：這裡只 `db.session.add()`，不自己 commit。
呼叫端（Service）會把稽核紀錄與商業資料放在同一個 transaction 裡，
確保「動作成功」與「有稽核紀錄」永遠一致。
"""

from __future__ import annotations

from ..extensions import db
from ..models import ActorType, AuditAction, AuditLog


def record(
    action: AuditAction | str,
    *,
    actor_type: ActorType | str = ActorType.SYSTEM,
    actor_id: int | None = None,
    actor_name: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    description: str = "",
) -> AuditLog:
    """建立一筆稽核紀錄（不 commit）。

    description 禁止寫入密碼 / PIN / Token 等敏感資訊。
    """
    log = AuditLog(
        actor_type=str(actor_type),
        actor_id=actor_id,
        actor_name=actor_name,
        action=str(action),
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
    )
    db.session.add(log)
    return log


def list_recent(limit: int = 100) -> list[AuditLog]:
    """取得最近的稽核紀錄。"""
    return list(
        db.session.execute(
            db.select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)
        ).scalars()
    )
