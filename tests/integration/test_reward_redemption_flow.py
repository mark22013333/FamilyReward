"""禮物兌換的端對端流程（HTTP 層）。"""

from __future__ import annotations

import pytest

from family_reward.models import RedemptionStatus, Reward
from family_reward.services import point_service, redemption_service


@pytest.fixture()
def rich_child(db, child, admin_user):
    point_service.adjust_points(
        child_id=child.id, points=13, reason="測試用點數", admin_id=admin_user.id
    )
    return child


def test_full_redemption_flow(client, rich_child, reward, login_child, login_admin):
    """驗收步驟 15-19：小孩申請 → 家長批准 → 正確扣點且 Lifetime 不倒退。"""
    # 1. 小孩看到自己換得起的禮物
    login_child(rich_child.id)
    rewards_page = client.get("/child/rewards").get_data(as_text=True)
    assert "吃冰淇淋" in rewards_page
    assert "我要這個！" in rewards_page

    # 2. 小孩申請
    response = client.post(
        f"/child/rewards/{reward.id}/request", follow_redirects=True
    )
    assert "跟爸爸媽媽說好囉" in response.get_data(as_text=True)
    # 申請當下不扣點
    assert point_service.get_balance(rich_child.id) == 13

    # 再次進入頁面顯示等待中
    assert "等爸爸媽媽確認" in client.get("/child/rewards").get_data(as_text=True)

    # 3. 家長批准
    client.post("/logout/child", follow_redirects=True)
    login_admin()
    pending_page = client.get("/admin/redemptions").get_data(as_text=True)
    assert "吃冰淇淋" in pending_page

    redemption = redemption_service.list_pending_redemptions()[0]
    response = client.post(
        f"/admin/redemptions/{redemption.id}/approve", follow_redirects=True
    )
    assert "已確認兌換" in response.get_data(as_text=True)

    # 4. 餘額正確扣 10，Lifetime 不變
    assert point_service.get_balance(rich_child.id) == 3
    assert point_service.get_lifetime_earned(rich_child.id) == 13


def test_locked_reward_shows_shortfall(client, child, reward, login_child, db):
    """點數不足時顯示還差幾顆星星，且沒有兌換按鈕。"""
    expensive = Reward(name="小玩具", icon="🧸", points_required=20, active=True)
    db.session.add(expensive)
    db.session.commit()

    login_child(child.id)
    body = client.get("/child/rewards").get_data(as_text=True)

    assert "還差 20" in body
    assert "我要這個！" not in body


def test_backend_rejects_request_without_points(client, child, reward, login_child):
    """需求書第 40 節：不能只依靠前端 disabled button。"""
    login_child(child.id)

    response = client.post(f"/child/rewards/{reward.id}/request", follow_redirects=True)

    assert "再收集 10 顆星星" in response.get_data(as_text=True)
    assert redemption_service.list_pending_redemptions() == []


def test_double_approve_deducts_once(client, rich_child, reward, login_child, login_admin):
    login_child(rich_child.id)
    client.post(f"/child/rewards/{reward.id}/request", follow_redirects=True)
    client.post("/logout/child", follow_redirects=True)

    login_admin()
    redemption = redemption_service.list_pending_redemptions()[0]
    client.post(f"/admin/redemptions/{redemption.id}/approve", follow_redirects=True)
    second = client.post(
        f"/admin/redemptions/{redemption.id}/approve", follow_redirects=True
    )

    assert "已經換過" in second.get_data(as_text=True)
    assert point_service.get_balance(rich_child.id) == 3


def test_reject_keeps_points(client, rich_child, reward, login_child, login_admin):
    login_child(rich_child.id)
    client.post(f"/child/rewards/{reward.id}/request", follow_redirects=True)
    client.post("/logout/child", follow_redirects=True)

    login_admin()
    redemption = redemption_service.list_pending_redemptions()[0]
    client.post(
        f"/admin/redemptions/{redemption.id}/reject",
        data={"reason": "這次先留著，下次再換喔！"},
        follow_redirects=True,
    )

    assert point_service.get_balance(rich_child.id) == 13


def test_complete_redemption_marks_delivered(
    client, rich_child, reward, login_child, login_admin, db
):
    login_child(rich_child.id)
    client.post(f"/child/rewards/{reward.id}/request", follow_redirects=True)
    client.post("/logout/child", follow_redirects=True)

    login_admin()
    redemption = redemption_service.list_pending_redemptions()[0]
    client.post(f"/admin/redemptions/{redemption.id}/approve", follow_redirects=True)
    client.post(f"/admin/redemptions/{redemption.id}/complete", follow_redirects=True)

    db.session.refresh(redemption)
    assert redemption.status == RedemptionStatus.COMPLETED.value
    assert redemption.completed_at is not None
    # 標記送達不會再扣一次點
    assert point_service.get_balance(rich_child.id) == 3


def test_empty_reward_shelf_message(client, child, login_child):
    login_child(child.id)

    body = client.get("/child/rewards").get_data(as_text=True)
    assert "禮物櫃目前還是空的" in body


def test_inactive_reward_hidden_from_child(client, rich_child, reward, login_child, db):
    reward.active = False
    db.session.commit()

    login_child(rich_child.id)
    assert "吃冰淇淋" not in client.get("/child/rewards").get_data(as_text=True)


def test_history_keeps_name_after_reward_deactivated(
    client, rich_child, reward, login_child, login_admin, db
):
    """需求書第 121 節：禮物停用後歷史仍顯示當時的名稱。"""
    login_child(rich_child.id)
    client.post(f"/child/rewards/{reward.id}/request", follow_redirects=True)
    client.post("/logout/child", follow_redirects=True)

    login_admin()
    redemption = redemption_service.list_pending_redemptions()[0]
    client.post(f"/admin/redemptions/{redemption.id}/approve", follow_redirects=True)
    client.post("/logout/admin", follow_redirects=True)

    reward.active = False
    reward.name = "改了名字的禮物"
    db.session.commit()

    login_child(rich_child.id)
    body = client.get("/child/rewards").get_data(as_text=True)
    assert "吃冰淇淋" in body  # 歷史紀錄仍是舊名稱
