"""任務範本與排程。

設計上分成三層，避免每天真的複製大量資料：

    Task           任務範本（刷牙）
    TaskSchedule   什麼時候要做（DAILY / 每週三 ...）
    TaskAssignment 某一天實際發生的任務（2026-09-06 的刷牙）

TaskAssignment 由 AssignmentService 在小孩開啟當日頁面時「按需產生」，
搭配 unique constraint 確保同一天同一任務不會重複產生。
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
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
from .enums import RepeatType, TaskCategory


class Task(db.Model):
    """任務範本。停用採 active=False，不做實體刪除。"""

    __tablename__ = "task"
    __table_args__ = (
        CheckConstraint("points >= 1 AND points <= 100", name="ck_task_points_range"),
        CheckConstraint("length(trim(title)) > 0", name="ck_task_title_not_blank"),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_task_date_range",
        ),
        Index("ix_task_active_category", "active", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(8), nullable=False, default="⭐")
    category: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TaskCategory.OTHER.value
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    #: Streak（連續達成）只計算 required=True 的任務。
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    repeat_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RepeatType.DAILY.value
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    schedules: Mapped[list["TaskSchedule"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", passive_deletes=True
    )
    assignees: Mapped[list["TaskAssignee"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", passive_deletes=True
    )

    def applies_on(self, target: date) -> bool:
        """判斷這個任務範本在指定日期是否應該產生 assignment。"""
        if not self.active:
            return False
        if self.start_date and target < self.start_date:
            return False
        if self.end_date and target > self.end_date:
            return False

        repeat = self.repeat_type
        if repeat == RepeatType.DAILY.value:
            return True
        if repeat == RepeatType.ONCE.value:
            # ONCE 只在 start_date 當天發生；沒設定 start_date 則不排程。
            return self.start_date is not None and target == self.start_date
        if repeat in (RepeatType.WEEKLY.value, RepeatType.CUSTOM.value):
            from ..utils.timezone import weekday_code

            codes = {schedule.weekday for schedule in self.schedules}
            return weekday_code(target) in codes
        return False

    def __repr__(self) -> str:  # pragma: no cover - 僅供除錯
        return f"<Task {self.id} {self.title}>"


class TaskSchedule(db.Model):
    """任務要在星期幾發生（WEEKLY / CUSTOM 使用）。"""

    __tablename__ = "task_schedule"
    __table_args__ = (
        UniqueConstraint("task_id", "weekday", name="uq_task_schedule_task_weekday"),
        CheckConstraint(
            "weekday IN ('MON','TUE','WED','THU','FRI','SAT','SUN')",
            name="ck_task_schedule_weekday",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekday: Mapped[str] = mapped_column(String(3), nullable=False)

    task: Mapped[Task] = relationship(back_populates="schedules")

    def __repr__(self) -> str:  # pragma: no cover - 僅供除錯
        return f"<TaskSchedule task={self.task_id} {self.weekday}>"


class TaskAssignee(db.Model):
    """任務指派給哪些小孩。"""

    __tablename__ = "task_assignee"
    __table_args__ = (
        UniqueConstraint("task_id", "child_id", name="uq_task_assignee"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child.id", ondelete="CASCADE"), nullable=False, index=True
    )

    task: Mapped[Task] = relationship(back_populates="assignees")
    child: Mapped["Child"] = relationship()  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover - 僅供除錯
        return f"<TaskAssignee task={self.task_id} child={self.child_id}>"
