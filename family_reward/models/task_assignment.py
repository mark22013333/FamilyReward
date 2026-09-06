"""某一天實際發生的任務。

重要：這裡保存了 task_title / task_icon / points 的 snapshot。
即使之後 Task 範本改名或改點數，歷史紀錄仍維持當時的樣子。
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from ..utils.timezone import utcnow
from .enums import AssignmentStatus


class TaskAssignment(db.Model):
    """任務指派 / 完成紀錄。"""

    __tablename__ = "task_assignment"
    __table_args__ = (
        # 同一天、同一個小孩、同一個任務範本只會有一筆，防止重複產生。
        UniqueConstraint(
            "task_id", "child_id", "assignment_date", name="uq_assignment_task_child_date"
        ),
        CheckConstraint(
            "status IN ('TODO','WAITING_APPROVAL','APPROVED','REJECTED')",
            name="ck_assignment_status",
        ),
        CheckConstraint("points_snapshot >= 0", name="ck_assignment_points_snapshot"),
        CheckConstraint("earned_points >= 0", name="ck_assignment_earned_points"),
        Index("ix_assignment_child_date", "child_id", "assignment_date"),
        Index("ix_assignment_status", "status"),
        Index("ix_assignment_status_date", "status", "assignment_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child.id", ondelete="CASCADE"), nullable=False
    )
    assignment_date: Mapped[date] = mapped_column(Date, nullable=False)

    # --- 當次 snapshot：Task 之後改名也不影響歷史 ---
    task_title_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    task_icon_snapshot: Mapped[str] = mapped_column(String(8), nullable=False, default="⭐")
    points_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    required_snapshot: Mapped[bool] = mapped_column(
        db.Boolean, nullable=False, default=False
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AssignmentStatus.TODO.value
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("admin_user.id", ondelete="SET NULL"), nullable=True
    )
    #: 實際入帳的點數；只有 APPROVED 才會 > 0。
    earned_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    child: Mapped["Child"] = relationship(back_populates="assignments")  # noqa: F821
    task: Mapped["Task"] = relationship()  # noqa: F821

    @property
    def is_pending_approval(self) -> bool:
        return self.status == AssignmentStatus.WAITING_APPROVAL.value

    @property
    def is_approved(self) -> bool:
        return self.status == AssignmentStatus.APPROVED.value

    @property
    def can_submit(self) -> bool:
        """TODO 與 REJECTED 都允許送出（被退回後可以再努力一次）。"""
        return self.status in (
            AssignmentStatus.TODO.value,
            AssignmentStatus.REJECTED.value,
        )

    def __repr__(self) -> str:  # pragma: no cover - 僅供除錯
        return f"<TaskAssignment {self.id} child={self.child_id} {self.status}>"
