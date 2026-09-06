"""小孩通知。

主要用途：家長批准任務後，小孩下次進入 Dashboard 顯示慶祝畫面 + Confetti，
且只播放一次（讀取後標記 read_at），避免每次重新整理都放動畫。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from ..utils.timezone import utcnow


class Notification(db.Model):
    __tablename__ = "notification"
    __table_args__ = (
        Index("ix_notification_child_unread", "child_id", "read_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: 顯示用的點數變化，例如 +2。None 代表不顯示點數。
    points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    child: Mapped["Child"] = relationship()  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover - 僅供除錯
        return f"<Notification {self.id} child={self.child_id} {self.type}>"
