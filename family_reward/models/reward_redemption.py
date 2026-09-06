"""禮物兌換申請。

同樣保存 reward_name / points 的 snapshot，
即使禮物之後改名或停用，歷史紀錄仍顯示當時的名稱與點數。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from ..utils.timezone import utcnow
from .enums import RedemptionStatus


class RewardRedemption(db.Model):
    """兌換申請。小孩提出 → 家長確認才扣點。"""

    __tablename__ = "reward_redemption"
    __table_args__ = (
        CheckConstraint(
            "status IN ('REQUESTED','APPROVED','COMPLETED','CANCELLED','REJECTED')",
            name="ck_redemption_status",
        ),
        CheckConstraint("points >= 0", name="ck_redemption_points"),
        Index("ix_redemption_child_requested", "child_id", "requested_at"),
        Index("ix_redemption_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child.id", ondelete="CASCADE"), nullable=False
    )
    reward_id: Mapped[int] = mapped_column(
        ForeignKey("reward.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # --- 當次 snapshot ---
    reward_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    reward_icon_snapshot: Mapped[str] = mapped_column(String(8), nullable=False, default="🎁")
    #: 申請當下所需的點數，實際扣款以此為準。
    points: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RedemptionStatus.REQUESTED.value
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("admin_user.id", ondelete="SET NULL"), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    child: Mapped["Child"] = relationship()  # noqa: F821
    reward: Mapped["Reward"] = relationship()  # noqa: F821

    @property
    def is_pending(self) -> bool:
        return self.status == RedemptionStatus.REQUESTED.value

    def __repr__(self) -> str:  # pragma: no cover - 僅供除錯
        return f"<RewardRedemption {self.id} child={self.child_id} {self.status}>"
