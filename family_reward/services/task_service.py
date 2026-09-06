"""任務範本管理服務。"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import selectinload

from ..exceptions import NotFoundError, ValidationError
from ..extensions import db
from ..models import (
    ActorType,
    AuditAction,
    RepeatType,
    Task,
    TaskAssignee,
    TaskCategory,
    TaskSchedule,
)
from ..utils.timezone import WEEKDAY_CODES
from . import audit_service


def list_tasks(*, only_active: bool = True) -> list[Task]:
    query = db.select(Task).options(
        selectinload(Task.schedules),
        selectinload(Task.assignees).selectinload(TaskAssignee.child),
    )
    if only_active:
        query = query.where(Task.active.is_(True))
    return list(db.session.execute(query.order_by(Task.id.asc())).scalars())


def get_task(task_id: int) -> Task:
    task = db.session.get(Task, task_id)
    if task is None:
        raise NotFoundError("找不到這個任務。")
    return task


def create_task(
    *,
    title: str,
    points: int,
    child_ids: list[int],
    icon: str = "⭐",
    description: str | None = None,
    category: str = TaskCategory.OTHER.value,
    repeat_type: str = RepeatType.DAILY.value,
    weekdays: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    required: bool = False,
    admin_id: int,
    admin_name: str | None = None,
) -> Task:
    _validate(title, points, repeat_type, weekdays, start_date, end_date, child_ids)

    task = Task(
        title=title.strip(),
        description=(description or "").strip() or None,
        icon=icon or "⭐",
        category=category if TaskCategory.has_value(category) else TaskCategory.OTHER.value,
        points=points,
        required=required,
        repeat_type=repeat_type,
        start_date=start_date,
        end_date=end_date,
        active=True,
    )

    try:
        db.session.add(task)
        db.session.flush()
        _sync_schedules(task, repeat_type, weekdays)
        _sync_assignees(task, child_ids)

        audit_service.record(
            AuditAction.CREATE_TASK,
            actor_type=ActorType.ADMIN,
            actor_id=admin_id,
            actor_name=admin_name,
            entity_type="TASK",
            entity_id=task.id,
            description=f"建立任務「{task.title}」+{task.points} ⭐",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return task


def update_task(
    task_id: int,
    *,
    title: str,
    points: int,
    child_ids: list[int],
    icon: str = "⭐",
    description: str | None = None,
    category: str = TaskCategory.OTHER.value,
    repeat_type: str = RepeatType.DAILY.value,
    weekdays: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    required: bool = False,
    active: bool = True,
    admin_id: int,
    admin_name: str | None = None,
) -> Task:
    """修改任務範本。

    既有的 TaskAssignment 保存了 snapshot，因此改名或改點數
    「不會」變動已經發生過的歷史紀錄。
    """
    _validate(title, points, repeat_type, weekdays, start_date, end_date, child_ids)
    task = get_task(task_id)

    try:
        task.title = title.strip()
        task.description = (description or "").strip() or None
        task.icon = icon or "⭐"
        task.category = (
            category if TaskCategory.has_value(category) else TaskCategory.OTHER.value
        )
        task.points = points
        task.required = required
        task.repeat_type = repeat_type
        task.start_date = start_date
        task.end_date = end_date
        task.active = active

        _sync_schedules(task, repeat_type, weekdays)
        _sync_assignees(task, child_ids)

        audit_service.record(
            AuditAction.UPDATE_TASK if active else AuditAction.DEACTIVATE_TASK,
            actor_type=ActorType.ADMIN,
            actor_id=admin_id,
            actor_name=admin_name,
            entity_type="TASK",
            entity_id=task.id,
            description=f"修改任務「{task.title}」",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return task


def deactivate_task(
    task_id: int, *, admin_id: int, admin_name: str | None = None
) -> Task:
    """停用任務（軟刪除）。已產生的當日任務不受影響。"""
    task = get_task(task_id)
    try:
        task.active = False
        audit_service.record(
            AuditAction.DEACTIVATE_TASK,
            actor_type=ActorType.ADMIN,
            actor_id=admin_id,
            actor_name=admin_name,
            entity_type="TASK",
            entity_id=task.id,
            description=f"停用任務「{task.title}」",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return task


def _sync_schedules(task: Task, repeat_type: str, weekdays: list[str] | None) -> None:
    """重建星期排程。ONCE / DAILY 不需要排程資料。"""
    for schedule in list(task.schedules):
        db.session.delete(schedule)
    task.schedules.clear()

    if repeat_type not in (RepeatType.WEEKLY.value, RepeatType.CUSTOM.value):
        return

    for code in dict.fromkeys(weekdays or []):  # 去重且保持順序
        if code in WEEKDAY_CODES:
            db.session.add(TaskSchedule(task_id=task.id, weekday=code))
    db.session.flush()


def _sync_assignees(task: Task, child_ids: list[int]) -> None:
    """重建任務指派對象。"""
    existing = {assignee.child_id: assignee for assignee in task.assignees}
    wanted = set(child_ids)

    for child_id, assignee in existing.items():
        if child_id not in wanted:
            db.session.delete(assignee)

    for child_id in wanted:
        if child_id not in existing:
            db.session.add(TaskAssignee(task_id=task.id, child_id=child_id))
    db.session.flush()


def _validate(
    title: str,
    points: int,
    repeat_type: str,
    weekdays: list[str] | None,
    start_date: date | None,
    end_date: date | None,
    child_ids: list[int],
) -> None:
    if not title or not title.strip():
        raise ValidationError("請幫任務取個名字吧！")
    if len(title.strip()) > 100:
        raise ValidationError("任務名稱不能超過 100 個字。")
    if not (1 <= points <= 100):
        raise ValidationError("點數必須介於 1 ~ 100。")
    if not RepeatType.has_value(repeat_type):
        raise ValidationError("重複方式不正確。")
    if repeat_type in (RepeatType.WEEKLY.value, RepeatType.CUSTOM.value):
        if not weekdays:
            raise ValidationError("請至少選一個星期幾。")
    if repeat_type == RepeatType.ONCE.value and start_date is None:
        raise ValidationError("只做一次的任務，請選擇日期。")
    if start_date and end_date and end_date < start_date:
        raise ValidationError("結束日期不能早於開始日期。")
    if not child_ids:
        raise ValidationError("請至少指派給一位小朋友。")
