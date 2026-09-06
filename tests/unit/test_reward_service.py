"""Reward / Redemption 單元測試。

涵蓋需求書的 Test Case 3、4、7、8。
"""

from __future__ import annotations

import pytest

from family_reward.exceptions import (
    InsufficientPointsError,
    InvalidStateError,
    OutOfStockError,
    PermissionDeniedError,
    ValidationError,
)
from family_reward.models import RedemptionStatus, Reward
from family_reward.services import point_service, redemption_service, reward_service


@pytest.fixture()
def rich_child(db, child, admin_user):
    """給小孩 13 點，方便測試兌換。"""
    point_service.adjust_points(
        child_id=child.id, points=13, reason="測試用點數", admin_id=admin_user.id
    )
    return child


def test_request_then_approve_deducts_points(db, rich_child, reward, admin_user):
    """Test Case 3：13 點兌換 10 點禮物 → 剩 3 點。"""
    redemption = redemption_service.request_redemption(rich_child, reward.id)
    assert redemption.status == RedemptionStatus.REQUESTED.value
    # 申請當下不扣點
    assert point_service.get_balance(rich_child.id) == 13

    result = redemption_service.approve_redemption(redemption.id, admin_user.id)

    assert result.status == RedemptionStatus.APPROVED.value
    assert point_service.get_balance(rich_child.id) == 3


def test_lifetime_earned_unchanged_after_redeem(db, rich_child, reward, admin_user):
    """需求書驗收 19：兌換不能讓 Lifetime Earned 倒退。"""
    lifetime_before = point_service.get_lifetime_earned(rich_child.id)

    redemption = redemption_service.request_redemption(rich_child, reward.id)
    redemption_service.approve_redemption(redemption.id, admin_user.id)

    assert point_service.get_lifetime_earned(rich_child.id) == lifetime_before == 13


def test_cannot_request_without_enough_points(db, child, reward):
    """點數不足時，申請階段就會被擋下。"""
    with pytest.raises(InsufficientPointsError):
        redemption_service.request_redemption(child, reward.id)


def test_approve_rejected_when_points_dropped(db, child, reward, admin_user):
    """Test Case 4：目前 3 點卻要批准 10 點的兌換 → 必須拒絕，不得變 -7。

    模擬情境：小孩申請時有足夠點數，但家長批准前點數被調整掉了。
    """
    point_service.adjust_points(
        child_id=child.id, points=10, reason="先給 10 點", admin_id=admin_user.id
    )
    redemption = redemption_service.request_redemption(child, reward.id)

    # 家長批准之前，點數被扣掉 7 點
    point_service.adjust_points(
        child_id=child.id, points=-7, reason="修正加點", admin_id=admin_user.id
    )
    assert point_service.get_balance(child.id) == 3

    with pytest.raises(InsufficientPointsError):
        redemption_service.approve_redemption(redemption.id, admin_user.id)

    # 餘額不得變成負數
    assert point_service.get_balance(child.id) == 3
    db.session.refresh(redemption)
    assert redemption.status == RedemptionStatus.REQUESTED.value


def test_approve_twice_does_not_double_deduct(db, rich_child, reward, admin_user):
    """同一筆兌換最多只能扣一次點。"""
    redemption = redemption_service.request_redemption(rich_child, reward.id)
    redemption_service.approve_redemption(redemption.id, admin_user.id)

    with pytest.raises(InvalidStateError):
        redemption_service.approve_redemption(redemption.id, admin_user.id)

    assert point_service.get_balance(rich_child.id) == 3


def test_stock_decrements_and_blocks_second_redeem(db, child, other_child, admin_user):
    """Test Case 7：庫存 1，第一次成功後變 0，第二次不得成功。"""
    limited = Reward(name="小玩具", icon="🧸", points_required=5, quantity=1, active=True)
    db.session.add(limited)
    db.session.commit()

    for kid in (child, other_child):
        point_service.adjust_points(
            child_id=kid.id, points=10, reason="測試", admin_id=admin_user.id
        )

    first = redemption_service.request_redemption(child, limited.id)
    second = redemption_service.request_redemption(other_child, limited.id)

    redemption_service.approve_redemption(first.id, admin_user.id)
    db.session.refresh(limited)
    assert limited.quantity == 0

    with pytest.raises(OutOfStockError):
        redemption_service.approve_redemption(second.id, admin_user.id)

    # 第二位小孩的點數不能被扣
    assert point_service.get_balance(other_child.id) == 10


def test_cannot_request_out_of_stock_reward(db, child, admin_user):
    sold_out = Reward(name="限量禮物", icon="🎁", points_required=1, quantity=0, active=True)
    db.session.add(sold_out)
    db.session.commit()
    point_service.adjust_points(
        child_id=child.id, points=10, reason="測試", admin_id=admin_user.id
    )

    with pytest.raises(OutOfStockError):
        redemption_service.request_redemption(child, sold_out.id)


def test_duplicate_pending_request_rejected(db, rich_child, reward):
    redemption_service.request_redemption(rich_child, reward.id)

    with pytest.raises(InvalidStateError):
        redemption_service.request_redemption(rich_child, reward.id)


def test_reject_redemption_does_not_deduct(db, rich_child, reward, admin_user):
    redemption = redemption_service.request_redemption(rich_child, reward.id)

    result = redemption_service.reject_redemption(
        redemption.id, admin_user.id, "這次先留著喔"
    )

    assert result.status == RedemptionStatus.REJECTED.value
    assert point_service.get_balance(rich_child.id) == 13


def test_child_cannot_access_other_childs_redemption(db, rich_child, other_child, reward):
    """Test Case 8：小孩不能存取別人的兌換紀錄。"""
    redemption = redemption_service.request_redemption(rich_child, reward.id)

    with pytest.raises(PermissionDeniedError):
        redemption_service.get_redemption_for_child(redemption.id, other_child.id)


def test_redemption_snapshot_survives_reward_rename(db, rich_child, reward, admin_user):
    """禮物改名不影響歷史兌換紀錄。"""
    redemption = redemption_service.request_redemption(rich_child, reward.id)
    redemption_service.approve_redemption(redemption.id, admin_user.id)

    reward.name = "超級冰淇淋"
    reward.points_required = 999
    db.session.commit()

    db.session.refresh(redemption)
    assert redemption.reward_name_snapshot == "吃冰淇淋"
    assert redemption.points == 10


def test_unlimited_reward_quantity_never_changes(db, rich_child, reward, admin_user):
    assert reward.is_unlimited

    redemption = redemption_service.request_redemption(rich_child, reward.id)
    redemption_service.approve_redemption(redemption.id, admin_user.id)

    db.session.refresh(reward)
    assert reward.quantity is None


# --------------------------------------------------------------------------
# RewardService 驗證
# --------------------------------------------------------------------------


def test_create_reward_validates_points(db, admin_user):
    with pytest.raises(ValidationError):
        reward_service.create_reward(
            name="太貴的禮物", points_required=99999, admin_id=admin_user.id
        )


def test_create_reward_requires_name(db, admin_user):
    with pytest.raises(ValidationError):
        reward_service.create_reward(
            name="   ", points_required=10, admin_id=admin_user.id
        )


def test_deactivate_reward_is_soft_delete(db, reward, admin_user):
    reward_service.deactivate_reward(reward.id, admin_id=admin_user.id)

    db.session.refresh(reward)
    assert reward.active is False
    # 資料仍在，只是不再顯示
    assert reward_service.get_reward(reward.id) is not None
    assert reward.id not in [r.id for r in reward_service.list_rewards(only_active=True)]
