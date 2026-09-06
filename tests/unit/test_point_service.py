"""PointService 單元測試。

重點驗證需求書第 43 / 151 節的規則：
Current Balance 與 Lifetime Earned 是兩個不同的概念，不可混用。
"""

from __future__ import annotations

import pytest

from family_reward.exceptions import InsufficientPointsError, InvalidStateError
from family_reward.models import SourceType, TransactionType
from family_reward.services import point_service


def test_balance_starts_at_zero(db, child):
    assert point_service.get_balance(child.id) == 0
    assert point_service.get_lifetime_earned(child.id) == 0


def test_balance_is_sum_of_all_transactions(db, child):
    point_service.add_transaction(
        child_id=child.id,
        transaction_type=TransactionType.EARN,
        points=5,
        source_type=SourceType.TASK_ASSIGNMENT,
        source_id=1,
        description="完成任務 A",
    )
    point_service.add_transaction(
        child_id=child.id,
        transaction_type=TransactionType.REDEEM,
        points=-3,
        source_type=SourceType.REWARD_REDEMPTION,
        source_id=1,
        description="兌換禮物",
    )
    db.session.commit()

    assert point_service.get_balance(child.id) == 2


def test_lifetime_earned_ignores_redeem(db, child):
    """兌換禮物不能讓「歷史累積取得」倒退。"""
    point_service.add_transaction(
        child_id=child.id,
        transaction_type=TransactionType.EARN,
        points=20,
        source_type=SourceType.TASK_ASSIGNMENT,
        source_id=1,
        description="完成任務",
    )
    point_service.add_transaction(
        child_id=child.id,
        transaction_type=TransactionType.REDEEM,
        points=-10,
        source_type=SourceType.REWARD_REDEMPTION,
        source_id=1,
        description="兌換冰淇淋",
    )
    db.session.commit()

    assert point_service.get_balance(child.id) == 10
    assert point_service.get_lifetime_earned(child.id) == 20


def test_lifetime_earned_includes_bonus(db, child):
    point_service.add_transaction(
        child_id=child.id,
        transaction_type=TransactionType.BONUS,
        points=5,
        source_type=SourceType.MANUAL,
        source_id=None,
        description="主動幫忙",
    )
    db.session.commit()

    assert point_service.get_lifetime_earned(child.id) == 5


def test_card_progress_uses_lifetime_earned(db, child):
    """需求書第 42 節：累積 23 點 → 完成 2 張卡，目前第 3 張 3/10。"""
    point_service.add_transaction(
        child_id=child.id,
        transaction_type=TransactionType.EARN,
        points=23,
        source_type=SourceType.TASK_ASSIGNMENT,
        source_id=1,
        description="累積",
    )
    db.session.commit()

    card = point_service.get_card_progress(child.id, points_per_card=10)
    assert card.lifetime_earned == 23
    assert card.completed_cards == 2
    assert card.current_points == 3
    assert card.remaining == 7


def test_card_progress_does_not_regress_after_redeem(db, child):
    """兌換後集點卡不能倒退。"""
    point_service.add_transaction(
        child_id=child.id,
        transaction_type=TransactionType.EARN,
        points=23,
        source_type=SourceType.TASK_ASSIGNMENT,
        source_id=1,
        description="累積",
    )
    db.session.commit()
    before = point_service.get_card_progress(child.id, 10)

    point_service.add_transaction(
        child_id=child.id,
        transaction_type=TransactionType.REDEEM,
        points=-10,
        source_type=SourceType.REWARD_REDEMPTION,
        source_id=1,
        description="兌換",
    )
    db.session.commit()
    after = point_service.get_card_progress(child.id, 10)

    assert after.completed_cards == before.completed_cards == 2
    assert after.lifetime_earned == before.lifetime_earned == 23
    # 但可以花的餘額確實減少了
    assert point_service.get_balance(child.id) == 13


def test_duplicate_source_transaction_is_rejected(db, child):
    """同一來源不能產生第二筆相同類型的交易。"""
    point_service.add_transaction(
        child_id=child.id,
        transaction_type=TransactionType.EARN,
        points=2,
        source_type=SourceType.TASK_ASSIGNMENT,
        source_id=99,
        description="完成任務",
    )
    db.session.commit()

    with pytest.raises(InvalidStateError):
        point_service.add_transaction(
            child_id=child.id,
            transaction_type=TransactionType.EARN,
            points=2,
            source_type=SourceType.TASK_ASSIGNMENT,
            source_id=99,
            description="重複加點",
        )

    assert point_service.get_balance(child.id) == 2


def test_manual_adjustment_creates_ledger_entry(db, child, admin_user):
    point_service.adjust_points(
        child_id=child.id,
        points=5,
        reason="今天主動幫忙整理客廳",
        admin_id=admin_user.id,
        admin_name=admin_user.username,
    )

    assert point_service.get_balance(child.id) == 5
    assert point_service.get_lifetime_earned(child.id) == 5
    transactions = point_service.list_transactions(child.id)
    assert len(transactions) == 1
    assert transactions[0].description == "今天主動幫忙整理客廳"


def test_manual_adjustment_can_be_negative(db, child, admin_user):
    point_service.adjust_points(
        child_id=child.id,
        points=10,
        reason="累積",
        admin_id=admin_user.id,
    )
    point_service.adjust_points(
        child_id=child.id,
        points=-2,
        reason="修正昨天錯誤加點",
        admin_id=admin_user.id,
    )

    assert point_service.get_balance(child.id) == 8
    # 扣點使用 ADJUST，不計入 lifetime earned
    assert point_service.get_lifetime_earned(child.id) == 10


def test_manual_adjustment_cannot_make_balance_negative(db, child, admin_user):
    """需求書第 150 節：預設不允許餘額低於 0。"""
    point_service.adjust_points(
        child_id=child.id, points=3, reason="累積", admin_id=admin_user.id
    )

    with pytest.raises(InsufficientPointsError):
        point_service.adjust_points(
            child_id=child.id,
            points=-10,
            reason="想扣太多",
            admin_id=admin_user.id,
        )

    assert point_service.get_balance(child.id) == 3


def test_multiple_manual_adjustments_allowed(db, child, admin_user):
    """手動調整的 source_id 為 NULL，不應互相衝突。"""
    for i in range(3):
        point_service.adjust_points(
            child_id=child.id, points=1, reason=f"第 {i} 次", admin_id=admin_user.id
        )

    assert point_service.get_balance(child.id) == 3


def test_balances_for_children_batch_query(db, child, other_child, admin_user):
    point_service.adjust_points(
        child_id=child.id, points=7, reason="測試", admin_id=admin_user.id
    )

    balances = point_service.get_balances_for_children([child.id, other_child.id])
    assert balances[child.id] == 7
    assert balances[other_child.id] == 0
