"""AssignmentService 單元測試。

涵蓋需求書的 Test Case 1、2、5、6。
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from family_reward.exceptions import (
    InvalidStateError,
    NotFoundError,
    PermissionDeniedError,
)
from family_reward.models import AssignmentStatus, PointTransaction, RepeatType
from family_reward.services import assignment_service, point_service


def test_assignments_generated_for_today(db, child, task, today):
    assignments = assignment_service.ensure_assignments_for_date(child.id, today)

    assert len(assignments) == 1
    assert assignments[0].task_title_snapshot == "整理玩具"
    assert assignments[0].points_snapshot == 2
    assert assignments[0].status == AssignmentStatus.TODO.value


def test_assignments_are_not_duplicated(db, child, task, today):
    """重複呼叫不能產生第二筆（需求書第 24 節）。"""
    assignment_service.ensure_assignments_for_date(child.id, today)
    assignment_service.ensure_assignments_for_date(child.id, today)
    assignments = assignment_service.ensure_assignments_for_date(child.id, today)

    assert len(assignments) == 1


def test_once_task_only_on_start_date(db, child, task, today):
    task.repeat_type = RepeatType.ONCE.value
    task.start_date = today
    db.session.commit()

    assert len(assignment_service.ensure_assignments_for_date(child.id, today)) == 1
    tomorrow = today + timedelta(days=1)
    assert len(assignment_service.ensure_assignments_for_date(child.id, tomorrow)) == 0


def test_inactive_task_generates_nothing(db, child, task, today):
    task.active = False
    db.session.commit()

    assert assignment_service.ensure_assignments_for_date(child.id, today) == []


def test_submit_moves_to_waiting_approval(db, child, task, today):
    assignment = assignment_service.ensure_assignments_for_date(child.id, today)[0]

    result = assignment_service.submit_assignment(assignment.id, child)

    assert result.status == AssignmentStatus.WAITING_APPROVAL.value
    assert result.submitted_at is not None
    # 尚未審核，不得有任何點數
    assert point_service.get_balance(child.id) == 0


def test_submit_twice_is_rejected(db, child, task, today):
    """Test Case 6：重複送出不得產生重複審核。"""
    assignment = assignment_service.ensure_assignments_for_date(child.id, today)[0]
    assignment_service.submit_assignment(assignment.id, child)

    with pytest.raises(InvalidStateError):
        assignment_service.submit_assignment(assignment.id, child)


def test_child_cannot_submit_another_childs_task(db, child, other_child, task, today):
    """Test Case 8：Child A 不能操作 Child B 的任務。"""
    assignment = assignment_service.ensure_assignments_for_date(child.id, today)[0]

    with pytest.raises(PermissionDeniedError):
        assignment_service.submit_assignment(assignment.id, other_child)


def test_approve_adds_points_once(db, child, task, today, admin_user):
    """Test Case 1：任務 +2，批准後 Balance = 2。"""
    assignment = assignment_service.ensure_assignments_for_date(child.id, today)[0]
    assignment_service.submit_assignment(assignment.id, child)

    result = assignment_service.approve_assignment(assignment.id, admin_user.id)

    assert result.status == AssignmentStatus.APPROVED.value
    assert result.earned_points == 2
    assert point_service.get_balance(child.id) == 2


def test_approve_twice_does_not_double_points(db, child, task, today, admin_user):
    """Test Case 2：連按兩次批准只能 +2，不得 +4。"""
    assignment = assignment_service.ensure_assignments_for_date(child.id, today)[0]
    assignment_service.submit_assignment(assignment.id, child)
    assignment_service.approve_assignment(assignment.id, admin_user.id)

    with pytest.raises(InvalidStateError):
        assignment_service.approve_assignment(assignment.id, admin_user.id)

    assert point_service.get_balance(child.id) == 2

    transactions = list(
        db.session.execute(
            db.select(PointTransaction).where(PointTransaction.child_id == child.id)
        ).scalars()
    )
    assert len(transactions) == 1
    assert transactions[0].points == 2


def test_rejected_task_creates_no_points(db, child, task, today, admin_user):
    """Test Case 5：Rejected 不得新增 PointTransaction。"""
    assignment = assignment_service.ensure_assignments_for_date(child.id, today)[0]
    assignment_service.submit_assignment(assignment.id, child)

    result = assignment_service.reject_assignment(
        assignment.id, admin_user.id, "玩具還有一些在地上喔～"
    )

    assert result.status == AssignmentStatus.REJECTED.value
    assert result.earned_points == 0
    assert result.rejection_reason == "玩具還有一些在地上喔～"
    assert point_service.get_balance(child.id) == 0

    count = db.session.execute(
        db.select(db.func.count(PointTransaction.id)).where(
            PointTransaction.child_id == child.id
        )
    ).scalar_one()
    assert count == 0


def test_rejected_task_can_be_resubmitted(db, child, task, today, admin_user):
    """被退回後允許再送出一次。"""
    assignment = assignment_service.ensure_assignments_for_date(child.id, today)[0]
    assignment_service.submit_assignment(assignment.id, child)
    assignment_service.reject_assignment(assignment.id, admin_user.id, "再加油")

    result = assignment_service.submit_assignment(assignment.id, child)
    assert result.status == AssignmentStatus.WAITING_APPROVAL.value

    approved = assignment_service.approve_assignment(assignment.id, admin_user.id)
    assert approved.status == AssignmentStatus.APPROVED.value
    assert point_service.get_balance(child.id) == 2


def test_cannot_approve_task_not_submitted(db, child, task, today, admin_user):
    assignment = assignment_service.ensure_assignments_for_date(child.id, today)[0]

    with pytest.raises(InvalidStateError):
        assignment_service.approve_assignment(assignment.id, admin_user.id)

    assert point_service.get_balance(child.id) == 0


def test_approve_unknown_assignment_raises(db, admin_user):
    with pytest.raises(NotFoundError):
        assignment_service.approve_assignment(99999, admin_user.id)


def test_daily_progress(db, child, task, today, admin_user):
    assignment = assignment_service.ensure_assignments_for_date(child.id, today)[0]
    progress = assignment_service.get_daily_progress(child.id, today)
    assert (progress.total, progress.approved, progress.earned_points) == (1, 0, 0)

    assignment_service.submit_assignment(assignment.id, child)
    progress = assignment_service.get_daily_progress(child.id, today)
    assert progress.waiting == 1

    assignment_service.approve_assignment(assignment.id, admin_user.id)
    progress = assignment_service.get_daily_progress(child.id, today)
    assert (progress.approved, progress.earned_points, progress.percent) == (1, 2, 100)
    assert progress.all_done is True


def test_snapshot_survives_task_rename(db, child, task, today, admin_user):
    """需求書第 121/122 節：Task 改名不能改變歷史紀錄。"""
    assignment = assignment_service.ensure_assignments_for_date(child.id, today)[0]
    assignment_service.submit_assignment(assignment.id, child)
    assignment_service.approve_assignment(assignment.id, admin_user.id)

    task.title = "整理房間"
    task.points = 99
    db.session.commit()

    db.session.refresh(assignment)
    assert assignment.task_title_snapshot == "整理玩具"
    assert assignment.points_snapshot == 2
    assert assignment.earned_points == 2
    assert point_service.get_balance(child.id) == 2


def test_streak_counts_consecutive_days(db, child, task, today, admin_user, make_assignment):
    """連續達成只計算 required 任務。"""
    for offset in range(1, 4):
        day = today - timedelta(days=offset)
        assignment = make_assignment(task, child, day)
        assignment.status = AssignmentStatus.APPROVED.value
        assignment.earned_points = 2
    db.session.commit()

    assert assignment_service.get_streak(child.id, today) == 3


def test_streak_breaks_on_incomplete_day(db, child, task, today, make_assignment):
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)

    incomplete = make_assignment(task, child, yesterday)
    incomplete.status = AssignmentStatus.TODO.value
    older = make_assignment(task, child, two_days_ago)
    older.status = AssignmentStatus.APPROVED.value
    db.session.commit()

    assert assignment_service.get_streak(child.id, today) == 0
