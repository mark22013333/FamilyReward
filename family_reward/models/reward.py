"""禮物。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from ..utils.timezone import utcnow


class Reward(db.Model):
    """可以兌換的禮物。停用採 active=False，不做實體刪除。"""

    __tablename__ = "reward"
    __table_args__ = (
        CheckConstraint(
            "points_required >= 1 AND points_required <= 10000",
            name="ck_reward_points_range",
        ),
        CheckConstraint("quantity IS NULL OR quantity >= 0", name="ck_reward_quantity"),
        CheckConstraint("length(trim(name)) > 0", name="ck_reward_name_not_blank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(8), nullable=False, default="🎁")
    points_required: Mapped[int] = mapped_column(Integer, nullable=False)
    #: NULL 代表數量無限；0 代表已經換完。
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    @property
    def is_unlimited(self) -> bool:
        return self.quantity is None

    @property
    def in_stock(self) -> bool:
        return self.is_unlimited or (self.quantity or 0) > 0

    def __repr__(self) -> str:  # pragma: no cover - 僅供除錯
        return f"<Reward {self.id} {self.name} {self.points_required}pt>"
