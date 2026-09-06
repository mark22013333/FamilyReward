"""後台管理功能的整合測試。"""

from __future__ import annotations

from family_reward.models import AuditLog, Child, Reward, Task
from family_reward.services import point_service


def test_create_child_via_admin(client, db, login_admin):
    """驗收步驟 4：建立 🐼 小明。"""
    login_admin()

    response = client.post(
        "/admin/children/new",
        data={
            "name": "小明",
            "nickname": "",
            "avatar": "🐼",
            "theme": "SUNNY",
            "birthday": "",
            "pin": "1234",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    created = db.session.execute(db.select(Child).where(Child.name == "小明")).scalar_one()
    assert created.avatar == "🐼"
    assert created.active is True
    assert created.verify_pin("1234")


def test_create_task_via_admin(client, db, child, login_admin, today):
    """驗收步驟 5-6：建立 🧸 整理玩具 +2 並指派給小明。"""
    login_admin()

    client.post(
        "/admin/tasks/new",
        data={
            "title": "整理玩具",
            "icon": "🧸",
            "description": "",
            "category": "HOUSEWORK",
            "points": "2",
            "repeat_type": "DAILY",
            "child_ids": [str(child.id)],
        },
        follow_redirects=True,
    )

    created = db.session.execute(
        db.select(Task).where(Task.title == "整理玩具")
    ).scalar_one()
    assert created.points == 2
    assert [a.child_id for a in created.assignees] == [child.id]
    assert created.applies_on(today) is True


def test_create_task_requires_assignee(client, db, child, login_admin):
    login_admin()

    response = client.post(
        "/admin/tasks/new",
        data={
            "title": "沒有指派的任務",
            "icon": "⭐",
            "category": "OTHER",
            "points": "1",
            "repeat_type": "DAILY",
        },
        follow_redirects=True,
    )

    assert "請至少指派給一位小朋友" in response.get_data(as_text=True)
    assert db.session.execute(db.select(Task)).first() is None


def test_weekly_task_requires_weekdays(client, child, login_admin):
    login_admin()

    response = client.post(
        "/admin/tasks/new",
        data={
            "title": "週末任務",
            "icon": "⭐",
            "category": "OTHER",
            "points": "1",
            "repeat_type": "CUSTOM",
            "child_ids": [str(child.id)],
        },
        follow_redirects=True,
    )

    assert "請至少選一個星期幾" in response.get_data(as_text=True)


def test_custom_weekday_task_schedule(client, db, child, login_admin):
    login_admin()

    client.post(
        "/admin/tasks/new",
        data={
            "title": "倒垃圾",
            "icon": "🗑️",
            "category": "HOUSEWORK",
            "points": "2",
            "repeat_type": "CUSTOM",
            "weekdays": ["MON", "WED", "FRI"],
            "child_ids": [str(child.id)],
        },
        follow_redirects=True,
    )

    task = db.session.execute(db.select(Task).where(Task.title == "倒垃圾")).scalar_one()
    assert sorted(s.weekday for s in task.schedules) == ["FRI", "MON", "WED"]

    from datetime import date

    # 2026-09-07 是星期一
    assert task.applies_on(date(2026, 9, 7)) is True
    # 2026-09-08 是星期二
    assert task.applies_on(date(2026, 9, 8)) is False


def test_create_reward_via_admin(client, db, login_admin):
    """驗收步驟 15：建立 🍦 吃冰淇淋 10 點。"""
    login_admin()

    client.post(
        "/admin/rewards/new",
        data={
            "name": "吃冰淇淋",
            "icon": "🍦",
            "description": "",
            "points_required": "10",
            "quantity": "",
        },
        follow_redirects=True,
    )

    created = db.session.execute(
        db.select(Reward).where(Reward.name == "吃冰淇淋")
    ).scalar_one()
    assert created.points_required == 10
    assert created.is_unlimited is True


def test_deactivate_child_is_soft_delete(client, db, child, login_admin):
    """需求書第 120 節：重要資料不做實體刪除。"""
    login_admin()

    client.post(f"/admin/children/{child.id}/deactivate", follow_redirects=True)

    db.session.refresh(child)
    assert child.active is False
    # 資料仍在資料庫裡
    assert db.session.get(Child, child.id) is not None


def test_manual_point_adjustment_via_admin(client, child, login_admin):
    """需求書第 54 節：手動調整必須寫入帳本。"""
    login_admin()

    response = client.post(
        "/admin/points",
        data={
            "child_id": str(child.id),
            "points": "5",
            "reason": "今天主動幫忙整理客廳",
        },
        follow_redirects=True,
    )

    assert "點數已經調整完成" in response.get_data(as_text=True)
    assert point_service.get_balance(child.id) == 5

    transactions = point_service.list_transactions(child.id)
    assert transactions[0].description == "今天主動幫忙整理客廳"


def test_manual_adjustment_rejects_over_deduction(client, child, login_admin, admin_user):
    login_admin()
    point_service.adjust_points(
        child_id=child.id, points=3, reason="先給 3 點", admin_id=admin_user.id
    )

    response = client.post(
        "/admin/points",
        data={"child_id": str(child.id), "points": "-10", "reason": "想扣太多"},
        follow_redirects=True,
    )

    assert "不能扣掉" in response.get_data(as_text=True)
    assert point_service.get_balance(child.id) == 3


def test_audit_log_records_actions(client, db, child, login_admin):
    """需求書第 56/57 節。"""
    login_admin()
    client.post(
        "/admin/points",
        data={"child_id": str(child.id), "points": "2", "reason": "測試"},
        follow_redirects=True,
    )

    body = client.get("/admin/history").get_data(as_text=True)
    assert "MANUAL_POINT_ADJUSTMENT" in body

    logs = list(db.session.execute(db.select(AuditLog)).scalars())
    actions = {log.action for log in logs}
    assert "LOGIN_SUCCESS" in actions
    assert "MANUAL_POINT_ADJUSTMENT" in actions


def test_admin_dashboard_shows_children_progress(
    client, child, task, today, login_admin, admin_user
):
    from family_reward.services import assignment_service

    assignment_service.ensure_assignments_for_date(child.id, today)
    login_admin()

    body = client.get("/admin/").get_data(as_text=True)
    assert "小明" in body
    assert "完成：0 / 1" in body


def test_all_admin_pages_render(client, child, task, reward, login_admin):
    """煙霧測試：每個後台頁面都要能正常渲染。"""
    login_admin()

    for path in (
        "/admin/",
        "/admin/children",
        "/admin/children/new",
        f"/admin/children/{child.id}/edit",
        "/admin/tasks",
        "/admin/tasks/new",
        f"/admin/tasks/{task.id}/edit",
        "/admin/approvals",
        "/admin/rewards",
        "/admin/rewards/new",
        f"/admin/rewards/{reward.id}/edit",
        "/admin/redemptions",
        "/admin/points",
        "/admin/history",
        "/admin/settings",
    ):
        response = client.get(path)
        assert response.status_code == 200, f"{path} 回應 {response.status_code}"


def test_all_child_pages_render(client, child, task, reward, today, login_child):
    login_child(child.id)

    for path in (
        "/child/dashboard",
        "/child/calendar",
        f"/child/calendar/{today.isoformat()}",
        "/child/rewards",
        "/child/history",
    ):
        response = client.get(path)
        assert response.status_code == 200, f"{path} 回應 {response.status_code}"


def test_backup_creates_file(client, app, login_admin):
    """需求書第 64/65 節。"""
    login_admin()

    response = client.post("/admin/backup", follow_redirects=True)

    assert "備份完成" in response.get_data(as_text=True)

    from family_reward.services import backup_service

    backups = backup_service.list_backups(app.settings.backup.directory)
    assert len(backups) == 1
    assert backups[0].path.name.startswith("family-reward-")


def test_backup_file_is_valid_database(client, app, child, login_admin):
    """備份出來的檔案必須是可以讀取的完整資料庫。"""
    import sqlite3

    login_admin()
    client.post("/admin/backup", follow_redirects=True)

    from family_reward.services import backup_service

    backup = backup_service.get_latest_backup(app.settings.backup.directory)
    connection = sqlite3.connect(str(backup.path))
    try:
        names = [row[0] for row in connection.execute("SELECT name FROM child")]
    finally:
        connection.close()

    assert "小明" in names
