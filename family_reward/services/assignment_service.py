"""任務指派與審核流程。

固定流程：

    TODO → 小孩按「我完成了！」→ WAITING_APPROVAL → 家長審核 → APPROVED / REJECTED

* APPROVED：新增一筆 EARN PointTransaction（同一個 assignment 最多一筆）。
* REJECTED：不產生任何點數；小孩可以再送出一次。

TaskAssignment 採「按需產生」：小孩開啟當日頁面時才依 Task 範本產生當天的紀錄，
避免每天預先複製大量資料，並以 UNIQUE(task_id, child_id, assignment_date) 防止重複。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from ..exceptions import InvalidStateError, NotFoundError, PermissionDeniedError
from ..extensions import db
from ..models import (
    ActorType,
    AssignmentStatus,
    AuditAction,
    Child,
    NotificationType,
    SourceType,
    Task,
    TaskAssignee,
    TaskAssignment,
    TransactionType,
)
from ..utils.timezone import utcnow
from . import audit_service, notification_service, point_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DailyProgress:
    """某一天的完成進度。"""

    total: int
    approved: int
    waiting: int
    earned_points: int

    @property
    def percent(self) -> int:
        if self.total <= 0:
            return 0
        return int(self.approved / self.total * 100)

    @property
    def all_done(self) -> bool:
        return self.total > 0 and self.approved == self.total


def ensure_assignments_for_date(child_id: int, target: date) -> list[TaskAssignment]:
    """確保某個小孩在指定日期的任務紀錄都已建立，並回傳當日全部任務。

    這個函式可以安全地重複呼叫：已存在的不會重複建立。
    """
    child = db.session.get(Child, child_id)
    if child is None or not child.active:
        raise NotFoundError("找不到這位小朋友。")

    # 一次撈出指派給這個小孩、且仍啟用的任務範本（含排程），避免 N+1。
    tasks = list(
        db.session.execute(
            db.select(Task)
            .join(TaskAssignee, TaskAssignee.task_id == Task.id)
            .where(TaskAssignee.child_id == child_id, Task.active.is_(True))
            .options(selectinload(Task.schedules))
        ).scalars()
    )

    existing_task_ids = set(
        db.session.execute(
            db.select(TaskAssignment.task_id).where(
                TaskAssignment.child_id == child_id,
                TaskAssignment.assignment_date == target,
            )
        ).scalars()
    )

    created = False
    for task in tasks:
        if task.id in existing_task_ids:
            continue
        if not task.applies_on(target):
            continue
        db.session.add(
            TaskAssignment(
                task_id=task.id,
                child_id=child_id,
                assignment_date=target,
                # snapshot：之後 Task 改名也不影響這一天的歷史。
                task_title_snapshot=task.title,
                task_icon_snapshot=task.icon,
                points_snapshot=task.points,
                required_snapshot=task.required,
                status=AssignmentStatus.TODO.value,
            )
        )
        created = True

    if created:
        try:
            db.session.commit()
        except IntegrityError:
            # 兩個 request 同時進來時，其中一個會撞 UNIQUE constraint。
            # 這是預期內的情況：另一邊已經建立好了，直接沿用。
            db.session.rollback()
            logger.debug("任務紀錄已由其他請求建立，略過重複建立。")

    return list_assignments(child_id, target)


def list_assignments(child_id: int, target: date) -> list[TaskAssignment]:
    """取得某個小孩在指定日期的所有任務。"""
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


def get_assignment_for_child(assignment_id: int, child_id: int) -> TaskAssignment:
    """取得任務，同時做物件層級授權檢查。

    小孩手動改 URL 想操作別人的任務時，這裡會擋下來。
    """
    assignment = db.session.get(TaskAssignment, assignment_id)
    if assignment is None:
        raise NotFoundError("找不到這個任務耶 🐰")
    if assignment.child_id != child_id:
        raise PermissionDeniedError("這不是你的任務喔！")
    return assignment


def submit_assignment(assignment_id: int, child: Child) -> TaskAssignment:
    """小孩送出完成申請：TODO / REJECTED → WAITING_APPROVAL。"""
    assignment = get_assignment_for_child(assignment_id, child.id)

    if not assignment.can_submit:
        if assignment.status == AssignmentStatus.WAITING_APPROVAL.value:
            raise InvalidStateError("已經送出囉，等爸爸媽媽確認一下！⏳")
        raise InvalidStateError("這個任務已經完成啦！🎉")

    try:
        assignment.status = AssignmentStatus.WAITING_APPROVAL.value
        assignment.submitted_at = utcnow()
        assignment.completed_at = utcnow()
        assignment.rejection_reason = None

        audit_service.record(
            AuditAction.SUBMIT_TASK,
            actor_type=ActorType.CHILD,
            actor_id=child.id,
            actor_name=child.name,
            entity_type="TASK_ASSIGNMENT",
            entity_id=assignment.id,
            description=f"{child.name} 送出「{assignment.task_title_snapshot}」完成申請",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return assignment


def approve_assignment(
    assignment_id: int, admin_id: int, admin_name: str | None = None
) -> TaskAssignment:
    """家長批准任務，並在同一個 transaction 內加點。

    重複呼叫時：
    * 程式層先檢查狀態必須是 WAITING_APPROVAL。
    * 資料庫層有 UNIQUE(source_type, source_id, transaction_type) 兜底。

    因此連按兩次「完成」只會 +2，不會 +4。
    """
    assignment = db.session.get(TaskAssignment, assignment_id)
    if assignment is None:
        raise NotFoundError("找不到這個任務。")

    if assignment.status != AssignmentStatus.WAITING_APPROVAL.value:
        if assignment.status == AssignmentStatus.APPROVED.value:
            raise InvalidStateError("這個任務已經確認過囉！")
        raise InvalidStateError("這個任務還沒送出，沒辦法確認喔。")

    points = assignment.points_snapshot
    child = db.session.get(Child, assignment.child_id)
    child_name = child.name if child else "小朋友"

    try:
        assignment.status = AssignmentStatus.APPROVED.value
        assignment.approved_at = utcnow()
        assignment.approved_by = admin_id
        assignment.earned_points = points
        assignment.rejection_reason = None

        if points > 0:
            point_service.add_transaction(
                child_id=assignment.child_id,
                transaction_type=TransactionType.EARN,
                points=points,
                source_type=SourceType.TASK_ASSIGNMENT,
                source_id=assignment.id,
                description=f"完成「{assignment.task_title_snapshot}」",
                created_by=admin_id,
            )

        notification_service.create(
            child_id=assignment.child_id,
            notification_type=NotificationType.TASK_APPROVED,
            title="🎉 太棒了！",
            message=f"「{assignment.task_title_snapshot}」通過確認！",
            points=points,
        )

        audit_service.record(
            AuditAction.APPROVE_TASK,
            actor_type=ActorType.ADMIN,
            actor_id=admin_id,
            actor_name=admin_name,
            entity_type="TASK_ASSIGNMENT",
            entity_id=assignment.id,
            description=(
                f"批准 {child_name} 完成「{assignment.task_title_snapshot}」+{points} ⭐"
            ),
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return assignment


def reject_assignment(
    assignment_id: int,
    admin_id: int,
    reason: str = "",
    admin_name: str | None = None,
) -> TaskAssignment:
    """家長退回任務。絕不產生任何點數。"""
    assignment = db.session.get(TaskAssignment, assignment_id)
    if assignment is None:
        raise NotFoundError("找不到這個任務。")

    if assignment.status != AssignmentStatus.WAITING_APPROVAL.value:
        raise InvalidStateError("這個任務目前不能退回喔。")

    child = db.session.get(Child, assignment.child_id)
    child_name = child.name if child else "小朋友"
    reason = reason.strip() or "再檢查一下就完成啦！💪"

    try:
        assignment.status = AssignmentStatus.REJECTED.value
        assignment.rejection_reason = reason
        assignment.approved_at = None
        assignment.approved_by = admin_id
        assignment.earned_points = 0

        notification_service.create(
            child_id=assignment.child_id,
            notification_type=NotificationType.TASK_REJECTED,
            title="💪 再努力一下下",
            message=f"「{assignment.task_title_snapshot}」：{reason}",
            points=None,
        )

        audit_service.record(
            AuditAction.REJECT_TASK,
            actor_type=ActorType.ADMIN,
            actor_id=admin_id,
            actor_name=admin_name,
            entity_type="TASK_ASSIGNMENT",
            entity_id=assignment.id,
            description=f"退回 {child_name} 的「{assignment.task_title_snapshot}」",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return assignment


def list_pending_approvals() -> list[TaskAssignment]:
    """待確認清單（含小孩資料，避免 N+1）。"""
    return list(
        db.session.execute(
            db.select(TaskAssignment)
            .where(TaskAssignment.status == AssignmentStatus.WAITING_APPROVAL.value)
            .options(selectinload(TaskAssignment.child))
            .order_by(TaskAssignment.submitted_at.asc())
        ).scalars()
    )


def count_pending_approvals() -> int:
    return int(
        db.session.execute(
            db.select(func.count(TaskAssignment.id)).where(
                TaskAssignment.status == AssignmentStatus.WAITING_APPROVAL.value
            )
        ).scalar_one()
    )


def get_daily_progress(child_id: int, target: date) -> DailyProgress:
    """用一次 aggregate query 取得當日進度，避免 N+1。"""
    row = db.session.execute(
        db.select(
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
            func.coalesce(
                func.sum(
                    db.case(
                        (
                            TaskAssignment.status
                            == AssignmentStatus.WAITING_APPROVAL.value,
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(func.sum(TaskAssignment.earned_points), 0),
        ).where(
            TaskAssignment.child_id == child_id,
            TaskAssignment.assignment_date == target,
        )
    ).one()

    return DailyProgress(
        total=int(row[0] or 0),
        approved=int(row[1] or 0),
        waiting=int(row[2] or 0),
        earned_points=int(row[3] or 0),
    )


def get_streak(child_id: int, today: date, max_days: int = 60) -> int:
    """連續完成天數。

    規則：當天所有 required 任務都 APPROVED 才算一天。
    今天還沒完成不算中斷（從昨天往回數）。
    """
    from datetime import timedelta

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
        )
        .where(
            TaskAssignment.child_id == child_id,
            TaskAssignment.required_snapshot.is_(True),
            TaskAssignment.assignment_date <= today,
            TaskAssignment.assignment_date >= today - timedelta(days=max_days),
        )
        .group_by(TaskAssignment.assignment_date)
    ).all()

    by_date = {row[0]: (int(row[1]), int(row[2])) for row in rows}

    streak = 0
    cursor = today
    # 今天可能還在進行中，若今天尚未全部完成則從昨天開始計算。
    total, approved = by_date.get(today, (0, 0))
    if total == 0 or approved < total:
        cursor = today - timedelta(days=1)

    for _ in range(max_days):
        total, approved = by_date.get(cursor, (0, 0))
        if total == 0 or approved < total:
            break
        streak += 1
        cursor -= timedelta(days=1)

    return streak
