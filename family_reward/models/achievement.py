"""成就徽章。

第一版提供幾個基本成就；解鎖判斷寫在 AchievementService，
未來要新增成就只要在 seed 資料加一筆並補上判斷規則即可。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from ..utils.timezone import utcnow


class Achievement(db.Model):
    """成就定義。code 為程式判斷用的穩定識別字串。"""

    __tablename__ = "achievement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    icon: Mapped[str] = mapped_column(String(8), nullable=False, default="🏅")
    #: 達成門檻，語意由 code 決定（例如累積點數或連續天數）。
    threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - 僅供除錯
        return f"<Achievement {self.code}>"


class ChildAchievement(db.Model):
    """小孩已解鎖的成就。"""

    __tablename__ = "child_achievement"
    __table_args__ = (
        UniqueConstraint("child_id", "achievement_id", name="uq_child_achievement"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child.id", ondelete="CASCADE"), nullable=False, index=True
    )
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievement.id", ondelete="CASCADE"), nullable=False
    )
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    achievement: Mapped[Achievement] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - 僅供除錯
        return f"<ChildAchievement child={self.child_id} achievement={self.achievement_id}>"
