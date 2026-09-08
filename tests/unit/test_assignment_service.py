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


# --------------------------------------------------------------------------
# 補送出前幾天的任務（小孩當天忘記按）
# --------------------------------------------------------------------------


def test_can_submit_yesterdays_task(db, child, task, today):
    """核心情境：昨天忘記按，今天補按。"""
    yesterday = today - timedelta(days=1)
    assignment = assignment_service.ensure_assignments_for_date(child.id, yesterday)[0]

    result = assignment_service.submit_assignment(assignment.id, child, today=today)

    assert result.status == AssignmentStatus.WAITING_APPROVAL.value
    assert result.assignment_date == yesterday


def test_can_submit_within_makeup_window(db, child, task, today):
    """期限內（含最後一天）都可以補。"""
    target = today - timedelta(days=assignment_service.MAKEUP_DAYS)
    assignment = assignment_service.ensure_assignments_for_date(child.id, target)[0]

    result = assignment_service.submit_assignment(assignment.id, child, today=today)

    assert result.status == AssignmentStatus.WAITING_APPROVAL.value


def test_cannot_submit_beyond_makeup_window(db, child, task, today):
    """超過期限就不能補了，要請家長處理。"""
    too_old = today - timedelta(days=assignment_service.MAKEUP_DAYS + 1)
    assignment = assignment_service.ensure_assignments_for_date(child.id, too_old)[0]

    with pytest.raises(InvalidStateError, match="超過"):
        assignment_service.submit_assignment(assignment.id, child, today=today)

    db.session.refresh(assignment)
    assert assignment.status == AssignmentStatus.TODO.value


def test_cannot_submit_future_task(db, child, task, today):
    """明天的事情不可能今天就完成。"""
    tomorrow = today + timedelta(days=1)
    assignment = assignment_service.ensure_assignments_for_date(child.id, tomorrow)[0]

    with pytest.raises(InvalidStateError, match="之後的任務"):
        assignment_service.submit_assignment(assignment.id, child, today=today)


def test_makeup_task_earns_points_normally(db, child, task, today, admin_user):
    """補送出的任務，家長批准後一樣正常加點。"""
    yesterday = today - timedelta(days=1)
    assignment = assignment_service.ensure_assignments_for_date(child.id, yesterday)[0]
    assignment_service.submit_assignment(assignment.id, child, today=today)

    assignment_service.approve_assignment(assignment.id, admin_user.id)

    assert point_service.get_balance(child.id) == 2


def test_makeup_submit_is_audited_with_date(db, child, task, today):
    """稽核紀錄要看得出來這是補送的。"""
    from family_reward.models import AuditLog

    yesterday = today - timedelta(days=1)
    assignment = assignment_service.ensure_assignments_for_date(child.id, yesterday)[0]
    assignment_service.submit_assignment(assignment.id, child, today=today)

    log = db.session.execute(
        db.select(AuditLog).where(AuditLog.action == "SUBMIT_TASK")
    ).scalar_one()

    assert "補送" in log.description


def test_today_submit_not_marked_as_makeup(db, child, task, today):
    """當天送出的不該被標成補送。"""
    from family_reward.models import AuditLog

    assignment = assignment_service.ensure_assignments_for_date(child.id, today)[0]
    assignment_service.submit_assignment(assignment.id, child, today=today)

    log = db.session.execute(
        db.select(AuditLog).where(AuditLog.action == "SUBMIT_TASK")
    ).scalar_one()

    assert "補送" not in log.description


def test_ensure_makeup_window_backfills_missing_days(db, child, task, today):
    """小孩前幾天完全沒開過網站時，要能補建那幾天的紀錄。"""
    assignment_service.ensure_makeup_window(child.id, today)

    for offset in range(1, assignment_service.MAKEUP_DAYS + 1):
        day = today - timedelta(days=offset)
        assert len(assignment_service.list_assignments(child.id, day)) == 1


def test_ensure_makeup_window_does_not_go_too_far_back(db, child, task, today):
    """不可以憑空生出更早以前的歷史紀錄。"""
    assignment_service.ensure_makeup_window(child.id, today)

    too_old = today - timedelta(days=assignment_service.MAKEUP_DAYS + 1)
    assert assignment_service.list_assignments(child.id, too_old) == []


def test_list_makeup_assignments_only_incomplete(db, child, task, today, admin_user):
    """已完成或已送出的不該出現在「還沒完成」清單。"""
    assignment_service.ensure_makeup_window(child.id, today)
    yesterday = today - timedelta(days=1)
    done = assignment_service.list_assignments(child.id, yesterday)[0]
    assignment_service.submit_assignment(done.id, child, today=today)

    pending = assignment_service.list_makeup_assignments(child.id, today)

    assert done.id not in [a.id for a in pending]
    # 其他天的仍然在清單裡
    assert len(pending) == assignment_service.MAKEUP_DAYS - 1


def test_list_makeup_assignments_excludes_today(db, child, task, today):
    """今天的任務屬於「今天的任務」區塊，不該重複出現在補送清單。"""
    assignment_service.ensure_assignments_for_date(child.id, today)
    assignment_service.ensure_makeup_window(child.id, today)

    pending = assignment_service.list_makeup_assignments(child.id, today)

    assert all(a.assignment_date < today for a in pending)


def test_list_makeup_includes_rejected(db, child, task, today, admin_user):
    """被退回的過去任務也應該可以再補送。"""
    yesterday = today - timedelta(days=1)
    assignment = assignment_service.ensure_assignments_for_date(child.id, yesterday)[0]
    assignment_service.submit_assignment(assignment.id, child, today=today)
    assignment_service.reject_assignment(assignment.id, admin_user.id, "再檢查一下")

    pending = assignment_service.list_makeup_assignments(child.id, today)

    assert assignment.id in [a.id for a in pending]


def test_can_make_up_helper(db, child, task, today):
    """畫面用來決定要不要顯示補按按鈕。"""
    yesterday = today - timedelta(days=1)
    recent = assignment_service.ensure_assignments_for_date(child.id, yesterday)[0]
    too_old = assignment_service.ensure_assignments_for_date(
        child.id, today - timedelta(days=assignment_service.MAKEUP_DAYS + 1)
    )[0]

    assert assignment_service.can_make_up(recent, today) is True
    assert assignment_service.can_make_up(too_old, today) is False


def test_child_cannot_make_up_other_childs_task(db, child, other_child, task, today):
    """補送一樣要做物件層級授權。"""
    yesterday = today - timedelta(days=1)
    assignment = assignment_service.ensure_assignments_for_date(child.id, yesterday)[0]

    with pytest.raises(PermissionDeniedError):
        assignment_service.submit_assignment(assignment.id, other_child, today=today)


# --------------------------------------------------------------------------
# 日期區間查詢（匯出／獎狀用）
# --------------------------------------------------------------------------


def test_list_assignments_in_range_inclusive(db, child, task, today, make_assignment):
    """區間含頭含尾。"""
    for offset in (0, 1, 2, 3):
        make_assignment(task, child, today - timedelta(days=offset))

    rows = assignment_service.list_assignments_in_range(
        child.id, today - timedelta(days=2), today
    )

    assert [r.assignment_date for r in rows] == [
        today - timedelta(days=2),
        today - timedelta(days=1),
        today,
    ]


def test_list_assignments_in_range_all_children(
    db, child, other_child, task, today, make_assignment
):
    make_assignment(task, child, today)
    make_assignment(task, other_child, today)

    rows = assignment_service.list_assignments_in_range(None, today, today)

    assert {r.child_id for r in rows} == {child.id, other_child.id}


def test_list_assignments_in_range_creates_nothing(db, child, task, today):
    """純度測試：絕不能誤接 ensure_assignments_for_date。

    對一個從來沒開過的日期查詢，不該憑空產生任務紀錄。
    """
    from family_reward.models import TaskAssignment

    long_ago = today - timedelta(days=90)
    assignment_service.list_assignments_in_range(child.id, long_ago, long_ago)

    count = db.session.execute(
        db.select(db.func.count(TaskAssignment.id))
    ).scalar_one()
    assert count == 0


def test_get_top_tasks_counts_only_approved(
    db, child, task, today, admin_user, make_assignment
):
    """只算真的通過確認的。"""
    approved = make_assignment(task, child, today - timedelta(days=1))
    approved.status = AssignmentStatus.APPROVED.value
    pending = make_assignment(task, child, today)
    pending.status = AssignmentStatus.WAITING_APPROVAL.value
    db.session.commit()

    top = assignment_service.get_top_tasks_in_range(
        child.id, today - timedelta(days=7), today
    )

    assert top == [("整理玩具", "🧸", 1)]


def test_get_top_tasks_respects_limit(db, child, today, make_assignment):
    """多個任務時依次數排序並尊重 limit。"""
    from family_reward.models import RepeatType, Task, TaskAssignee, TaskCategory

    # 建三個任務，完成次數分別 3/2/1
    for index, (title, times) in enumerate(
        [("任務A", 3), ("任務B", 2), ("任務C", 1)]
    ):
        item = Task(
            title=title,
            icon="⭐",
            points=1,
            category=TaskCategory.OTHER.value,
            repeat_type=RepeatType.DAILY.value,
            active=True,
        )
        db.session.add(item)
        db.session.flush()
        db.session.add(TaskAssignee(task_id=item.id, child_id=child.id))
        db.session.commit()
        for day_offset in range(times):
            a = make_assignment(item, child, today - timedelta(days=day_offset))
            a.status = AssignmentStatus.APPROVED.value
        db.session.commit()

    top = assignment_service.get_top_tasks_in_range(
        child.id, today - timedelta(days=7), today, limit=2
    )

    assert [(t[0], t[2]) for t in top] == [("任務A", 3), ("任務B", 2)]


def test_get_top_tasks_uses_snapshot_after_rename(
    db, child, task, today, make_assignment
):
    """任務改名後，歷史統計仍顯示當時的名稱。"""
    a = make_assignment(task, child, today)
    a.status = AssignmentStatus.APPROVED.value
    db.session.commit()

    task.title = "改名後的任務"
    db.session.commit()

    top = assignment_service.get_top_tasks_in_range(child.id, today, today)

    assert top[0][0] == "整理玩具"


def test_get_top_tasks_empty_when_no_data(db, child, today):
    assert assignment_service.get_top_tasks_in_range(child.id, today, today) == []
