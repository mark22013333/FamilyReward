"""行事曆資料。

用 aggregate query 一次算出整個月的統計，避免每天一個 query 造成 N+1。
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func

from ..extensions import db
from ..models import AssignmentStatus, TaskAssignment


@dataclass(frozen=True)
class DaySummary:
    """行事曆上某一天的摘要。"""

    day: date
    total_tasks: int
    approved_tasks: int
    earned_points: int

    def to_dict(self) -> dict[str, object]:
        return {
            "date": self.day.isoformat(),
            "totalTasks": self.total_tasks,
            "approvedTasks": self.approved_tasks,
            "earnedPoints": self.earned_points,
        }


def month_range(year: int, month: int) -> tuple[date, date]:
    """回傳該月份的第一天與最後一天。"""
    if not (1 <= month <= 12):
        raise ValueError("月份必須介於 1 ~ 12。")
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def get_month_summary(child_id: int, year: int, month: int) -> list[DaySummary]:
    """取得某個小孩某個月每一天的任務統計。"""
    start, end = month_range(year, month)

    rows = db.session.execute(
        db.select(
            TaskAssignment.assignment_date,
            func.count(TaskAssignment.id),
            func.coalesce(
                func.sum(
                    db.case(
                        (TaskAssignment.status == AssignmentStatus.APPROVED.value, 1),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(func.sum(TaskAssignment.earned_points), 0),
        )
        .where(
            TaskAssignment.child_id == child_id,
            TaskAssignment.assignment_date >= start,
            TaskAssignment.assignment_date <= end,
        )
        .group_by(TaskAssignment.assignment_date)
        .order_by(TaskAssignment.assignment_date)
    ).all()

    return [
        DaySummary(
            day=row[0] if isinstance(row[0], date) else date.fromisoformat(str(row[0])),
            total_tasks=int(row[1] or 0),
            approved_tasks=int(row[2] or 0),
            earned_points=int(row[3] or 0),
        )
        for row in rows
    ]


def get_day_detail(child_id: int, target: date) -> list[TaskAssignment]:
    """某一天的任務明細。"""
    return list(
        db.session.execute(
            db.select(TaskAssignment)
            .where(
                TaskAssignment.child_id == child_id,
                TaskAssignment.assignment_date == target,
            )
            .order_by(TaskAssignment.id)
        ).scalars()
    )
