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


# --------------------------------------------------------------------------
# 集點卡顯示方式的門檻（星星 vs 進度條）
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("points_per_card", "expect_stamps"),
    [(1, True), (10, True), (20, True), (21, False), (50, False), (100, False)],
)
def test_use_stamp_grid_threshold(db, child, points_per_card, expect_stamps):
    """20 點以內用星星，超過改用進度條（否則版面會被撐爆）。"""
    card = point_service.get_card_progress(child.id, points_per_card)

    assert card.use_stamp_grid is expect_stamps


def test_card_progress_recomputes_from_lifetime_on_new_setting(db, child, admin_user):
    """改變點數設定後，張數直接由 lifetime 重算（刻意不保留舊的張數）。

    這個測試同時是「直接重算」這個設計決策的可執行規格。
    """
    point_service.adjust_points(
        child_id=child.id, points=23, reason="測試", admin_id=admin_user.id
    )

    at_ten = point_service.get_card_progress(child.id, 10)
    at_five = point_service.get_card_progress(child.id, 5)
    at_fifty = point_service.get_card_progress(child.id, 50)

    assert (at_ten.completed_cards, at_ten.current_points) == (2, 3)
    assert (at_five.completed_cards, at_five.current_points) == (4, 3)
    assert (at_fifty.completed_cards, at_fifty.current_points) == (0, 23)

    # lifetime 本身完全不受設定影響
    assert at_ten.lifetime_earned == at_five.lifetime_earned == 23


def test_card_progress_change_is_reversible(db, child, admin_user):
    """改回原本的數字，張數就完全回來 —— 沒有資料被破壞。"""
    point_service.adjust_points(
        child_id=child.id, points=23, reason="測試", admin_id=admin_user.id
    )

    before = point_service.get_card_progress(child.id, 10)
    point_service.get_card_progress(child.id, 50)  # 中間改成 50
    after = point_service.get_card_progress(child.id, 10)

    assert before == after


# --------------------------------------------------------------------------
# 日期區間查詢（匯出用）
# --------------------------------------------------------------------------


def test_range_query_respects_local_timezone(db, child):
    """最容易出錯的地方：created_at 存 UTC，但使用者說的月份是台北時間。

    台北 2026-03-01 07:00 的交易，資料庫存的是 UTC 2026-02-28 23:00。
    它必須算在「三月」，不能算在二月。
    """
    from datetime import date, datetime

    from family_reward.models import PointTransaction

    # 直接塞一筆 UTC 2026-02-28 23:00 的紀錄（= 台北 3/1 07:00）
    db.session.add(
        PointTransaction(
            child_id=child.id,
            transaction_type=TransactionType.EARN.value,
            points=2,
            source_type=SourceType.TASK_ASSIGNMENT.value,
            source_id=9001,
            description="台北三月一日清晨",
            created_at=datetime(2026, 2, 28, 23, 0),
        )
    )
    db.session.commit()

    march = point_service.list_transactions_in_range(
        child.id, date(2026, 3, 1), date(2026, 3, 31), "Asia/Taipei"
    )
    february = point_service.list_transactions_in_range(
        child.id, date(2026, 2, 1), date(2026, 2, 28), "Asia/Taipei"
    )

    assert [t.description for t in march] == ["台北三月一日清晨"]
    assert february == []


def test_range_query_excludes_next_month_boundary(db, child):
    """台北 4/1 00:30（UTC 3/31 16:30）不能算在三月。"""
    from datetime import date, datetime

    from family_reward.models import PointTransaction

    db.session.add(
        PointTransaction(
            child_id=child.id,
            transaction_type=TransactionType.EARN.value,
            points=1,
            source_type=SourceType.TASK_ASSIGNMENT.value,
            source_id=9002,
            description="台北四月一日凌晨",
            created_at=datetime(2026, 3, 31, 16, 30),
        )
    )
    db.session.commit()

    march = point_service.list_transactions_in_range(
        child.id, date(2026, 3, 1), date(2026, 3, 31), "Asia/Taipei"
    )
    april = point_service.list_transactions_in_range(
        child.id, date(2026, 4, 1), date(2026, 4, 30), "Asia/Taipei"
    )

    assert march == []
    assert [t.description for t in april] == ["台北四月一日凌晨"]


def test_range_query_is_ascending(db, child, admin_user):
    """匯出用舊到新（和畫面用的 list_transactions 相反）。"""
    from datetime import date

    for i in range(3):
        point_service.adjust_points(
            child_id=child.id, points=1, reason=f"第 {i} 筆", admin_id=admin_user.id
        )

    today = __import__("family_reward.utils.timezone", fromlist=["x"]).today_local(
        "Asia/Taipei"
    )
    rows = point_service.list_transactions_in_range(
        child.id, today, today, "Asia/Taipei"
    )

    assert [r.description for r in rows] == ["第 0 筆", "第 1 筆", "第 2 筆"]


def test_range_query_all_children_when_child_id_none(db, child, other_child, admin_user):
    from family_reward.utils.timezone import today_local

    point_service.adjust_points(
        child_id=child.id, points=1, reason="A", admin_id=admin_user.id
    )
    point_service.adjust_points(
        child_id=other_child.id, points=1, reason="B", admin_id=admin_user.id
    )
    today = today_local("Asia/Taipei")

    rows = point_service.list_transactions_in_range(None, today, today, "Asia/Taipei")

    assert {r.description for r in rows} == {"A", "B"}


def test_range_query_creates_nothing(db, child):
    """純度：匯出查詢絕不能產生任何資料。"""
    from datetime import date

    from family_reward.models import PointTransaction

    before = db.session.execute(
        db.select(db.func.count(PointTransaction.id))
    ).scalar_one()

    point_service.list_transactions_in_range(
        child.id, date(2020, 1, 1), date(2020, 1, 31), "Asia/Taipei"
    )

    after = db.session.execute(
        db.select(db.func.count(PointTransaction.id))
    ).scalar_one()
    assert before == after
