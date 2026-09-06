"""稽核紀錄。建立後禁止刪除或修改。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from ..utils.timezone import utcnow


class AuditLog(db.Model):
    """誰、在什麼時候、對什麼資料、做了什麼事。

    刻意不使用 ForeignKey：即使關聯資料被停用，稽核紀錄仍要完整保存。
    禁止寫入密碼 / PIN / Session ID / Token 等敏感資訊。
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_created", "created_at"),
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_actor", "actor_type", "actor_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - 僅供除錯
        return f"<AuditLog {self.id} {self.actor_type} {self.action}>"
