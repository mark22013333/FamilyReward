"""任務完成 → 審核 → 加點的端對端流程（HTTP 層）。"""

from __future__ import annotations

from family_reward.models import AssignmentStatus, PointTransaction
from family_reward.services import assignment_service, point_service


def test_full_approval_flow_via_http(client, child, task, today, login_child, login_admin):
    """小孩送出 → 家長批准 → 點數正確入帳。"""
    # 1. 小孩登入並看到今天的任務
    login_child(child.id)
    dashboard = client.get("/child/dashboard").get_data(as_text=True)
    assert "整理玩具" in dashboard
    assert "我完成了！" in dashboard

    # 2. 小孩送出完成申請
    assignment = assignment_service.list_assignments(child.id, today)[0]
    response = client.post(
        f"/child/tasks/{assignment.id}/submit", follow_redirects=True
    )
    assert response.status_code == 200
    assert "收到啦" in response.get_data(as_text=True)

    # 送出後畫面顯示等待中，且沒有可以再按的按鈕
    dashboard = client.get("/child/dashboard").get_data(as_text=True)
    assert "等爸爸媽媽確認" in dashboard

    # 此時還不能有點數
    assert point_service.get_balance(child.id) == 0

    # 3. 家長登入，在待確認看到這筆
    client.post("/logout/child", follow_redirects=True)
    login_admin()
    approvals = client.get("/admin/approvals").get_data(as_text=True)
    assert "整理玩具" in approvals
    assert "小明" in approvals

    # 4. 家長批准
    response = client.post(
        f"/admin/assignments/{assignment.id}/approve", follow_redirects=True
    )
    assert "已確認完成" in response.get_data(as_text=True)

    # 5. 點數只加一次
    assert point_service.get_balance(child.id) == 2


def test_double_approve_via_http_adds_points_once(
    client, db, child, task, today, login_child, login_admin
):
    """家長快速按兩次「完成」只能 +2。"""
    login_child(child.id)
    client.get("/child/dashboard")
    assignment = assignment_service.list_assignments(child.id, today)[0]
    client.post(f"/child/tasks/{assignment.id}/submit", follow_redirects=True)
    client.post("/logout/child", follow_redirects=True)

    login_admin()
    client.post(f"/admin/assignments/{assignment.id}/approve", follow_redirects=True)
    second = client.post(
        f"/admin/assignments/{assignment.id}/approve", follow_redirects=True
    )

    assert "已經確認過" in second.get_data(as_text=True)
    assert point_service.get_balance(child.id) == 2

    count = db.session.execute(
        db.select(db.func.count(PointTransaction.id)).where(
            PointTransaction.child_id == child.id
        )
    ).scalar_one()
    assert count == 1


def test_reject_flow_shows_friendly_message(
    client, child, task, today, login_child, login_admin
):
    """退回後小孩看得到鼓勵訊息，且沒有拿到點數。"""
    login_child(child.id)
    client.get("/child/dashboard")
    assignment = assignment_service.list_assignments(child.id, today)[0]
    client.post(f"/child/tasks/{assignment.id}/submit", follow_redirects=True)
    client.post("/logout/child", follow_redirects=True)

    login_admin()
    client.post(
        f"/admin/assignments/{assignment.id}/reject",
        data={"reason": "玩具還有一些在地上喔～再整理一下就完成啦！"},
        follow_redirects=True,
    )
    client.post("/logout/admin", follow_redirects=True)

    login_child(child.id)
    dashboard = client.get("/child/dashboard").get_data(as_text=True)
    assert "玩具還有一些在地上喔" in dashboard
    assert "我再試一次！" in dashboard
    assert point_service.get_balance(child.id) == 0


def test_child_cannot_submit_other_childs_assignment_via_http(
    client, child, other_child, task, today, login_child
):
    """需求書第 160 節：手動改 URL 不能操作別人的任務。"""
    login_child(child.id)
    client.get("/child/dashboard")
    assignment = assignment_service.list_assignments(child.id, today)[0]
    client.post("/logout/child", follow_redirects=True)

    # 換成另一個小孩，用同樣的 assignment id 嘗試送出
    login_child(other_child.id, pin="5678")
    response = client.post(f"/child/tasks/{assignment.id}/submit", follow_redirects=True)

    assert "這不是你的任務" in response.get_data(as_text=True)

    from family_reward.extensions import db as _db

    _db.session.refresh(assignment)
    assert assignment.status == AssignmentStatus.TODO.value


def test_celebration_shown_once_only(client, child, task, today, login_child, login_admin):
    """需求書第 107 節：Confetti 只在批准後播一次，重新整理不重播。"""
    login_child(child.id)
    client.get("/child/dashboard")
    assignment = assignment_service.list_assignments(child.id, today)[0]
    client.post(f"/child/tasks/{assignment.id}/submit", follow_redirects=True)
    client.post("/logout/child", follow_redirects=True)

    login_admin()
    client.post(f"/admin/assignments/{assignment.id}/approve", follow_redirects=True)
    client.post("/logout/admin", follow_redirects=True)

    # login_child 會 follow redirect 直接進入 dashboard，
    # 慶祝畫面就在這第一次的回應裡。
    first = login_child(child.id).get_data(as_text=True)
    assert "data-celebrate" in first
    assert "通過確認" in first

    # 重新整理不能再播一次（通知已標記為已讀）。
    second = client.get("/child/dashboard").get_data(as_text=True)
    assert "data-celebrate" not in second


def test_points_card_reaches_ten(client, db, child, task, today, admin_user, login_child):
    """驗收步驟 14：累積 10 點後集點卡顯示 10 / 10 完成一張。"""
    point_service.adjust_points(
        child_id=child.id, points=10, reason="測試累積", admin_id=admin_user.id
    )

    login_child(child.id)
    dashboard = client.get("/child/dashboard").get_data(as_text=True)

    card = point_service.get_card_progress(child.id, 10)
    assert card.completed_cards == 1
    assert card.lifetime_earned == 10
    assert "已經完成 1 張集點卡" in dashboard


def test_history_page_shows_transactions(
    client, child, task, today, admin_user, login_child
):
    point_service.adjust_points(
        child_id=child.id, points=5, reason="主動幫忙", admin_id=admin_user.id
    )

    login_child(child.id)
    body = client.get("/child/history").get_data(as_text=True)

    assert "主動幫忙" in body
    assert "+5" in body


def test_calendar_api_returns_summary(client, child, task, today, admin_user, login_child):
    """需求書第 47 節的 Calendar API 格式。"""
    login_child(child.id)
    client.get("/child/dashboard")
    assignment = assignment_service.list_assignments(child.id, today)[0]
    client.post(f"/child/tasks/{assignment.id}/submit", follow_redirects=True)
    assignment_service.approve_assignment(assignment.id, admin_user.id)

    response = client.get(f"/api/calendar?year={today.year}&month={today.month}")
    assert response.status_code == 200

    payload = response.get_json()
    entry = next(item for item in payload if item["date"] == today.isoformat())
    assert entry == {
        "date": today.isoformat(),
        "totalTasks": 1,
        "approvedTasks": 1,
        "earnedPoints": 2,
    }


def test_calendar_api_ignores_child_id_from_query(
    client, child, other_child, task, today, admin_user, login_child
):
    """需求書第 47 節：Child ID 不可以完全相信 Query String。"""
    login_child(child.id)
    client.get("/child/dashboard")
    assignment = assignment_service.list_assignments(child.id, today)[0]
    assignment_service.submit_assignment(assignment.id, child)
    assignment_service.approve_assignment(assignment.id, admin_user.id)

    # 小孩嘗試查別人的資料，後端仍然只回自己的
    response = client.get(
        f"/api/calendar?year={today.year}&month={today.month}&child_id={other_child.id}"
    )

    payload = response.get_json()
    entry = next(item for item in payload if item["date"] == today.isoformat())
    assert entry["approvedTasks"] == 1  # 這是自己的資料，不是 other_child 的


def test_calendar_api_requires_login(client, today):
    response = client.get(f"/api/calendar?year={today.year}&month={today.month}")

    assert response.status_code == 403


def test_calendar_day_detail_page(client, child, task, today, admin_user, login_child):
    login_child(child.id)
    client.get("/child/dashboard")
    assignment = assignment_service.list_assignments(child.id, today)[0]
    assignment_service.submit_assignment(assignment.id, child)
    assignment_service.approve_assignment(assignment.id, admin_user.id)

    body = client.get(f"/child/calendar/{today.isoformat()}").get_data(as_text=True)

    assert "整理玩具" in body
    assert "+2" in body
