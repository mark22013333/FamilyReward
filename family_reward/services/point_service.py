"""點數服務 —— 整個系統的資料一致性核心。

## 兩個必須分清楚的概念

| 概念            | 計算方式                              | 用途           |
| --------------- | ------------------------------------- | -------------- |
| Current Balance | SUM(所有 PointTransaction.points)     | 兌換禮物       |
| Lifetime Earned | SUM(EARN + BONUS 的 points)           | 集點卡里程碑   |

集點卡刻意使用 Lifetime Earned，這樣小孩兌換禮物之後，
「已經完成過幾張集點卡」不會倒退，才不會覺得努力被拿走了。

## 防止重複加點

`PointTransaction` 有 UNIQUE(source_type, source_id, transaction_type)。
家長連按兩次「完成」時：

1. 程式層：先檢查狀態是否仍為 WAITING_APPROVAL（見 assignment_service）。
2. 資料庫層：即使兩個 request 同時通過檢查，第二筆 INSERT 也會撞 UNIQUE 而失敗。

雙重保護缺一不可。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ..exceptions import InsufficientPointsError, InvalidStateError, ValidationError
from ..extensions import db
from ..models import (
    EARNING_TRANSACTION_TYPES,
    ActorType,
    AuditAction,
    Child,
    PointTransaction,
    SourceType,
    TransactionType,
)
from ..utils.timezone import to_local
from . import audit_service


#: 超過這個點數就不畫星星、改用進度條。
#: 這是版面事實而不是家庭政策（5 格一列，20 點剛好 4 列），
#: 所以放程式常數、不開放設定 —— 比照 admin_service.MIN_PASSWORD_LENGTH。
STAMP_GRID_MAX = 20


@dataclass(frozen=True)
class CardProgress:
    """集點卡進度（以 Lifetime Earned 計算）。"""

    lifetime_earned: int
    points_per_card: int
    completed_cards: int
    current_points: int
    remaining: int

    @property
    def percent(self) -> int:
        if self.points_per_card <= 0:
            return 0
        return int(self.current_points / self.points_per_card * 100)

    @property
    def is_complete(self) -> bool:
        return self.current_points == 0 and self.completed_cards > 0

    @property
    def use_stamp_grid(self) -> bool:
        """是否用星星呈現。

        點數太多時改用進度條，否則幾十顆星星會把版面撐得又長又擠。
        """
        return self.points_per_card <= STAMP_GRID_MAX


def get_balance(child_id: int) -> int:
    """目前可以花的點數 = SUM(所有交易)。

    永遠即時重算，不依賴任何 cache 欄位。
    """
    total = db.session.execute(
        db.select(func.coalesce(func.sum(PointTransaction.points), 0)).where(
            PointTransaction.child_id == child_id
        )
    ).scalar_one()
    return int(total or 0)


def get_lifetime_earned(child_id: int) -> int:
    """歷史累積取得的正向點數（EARN + BONUS）。

    兌換禮物（REDEEM）不會扣減這個數字。
    """
    total = db.session.execute(
        db.select(func.coalesce(func.sum(PointTransaction.points), 0)).where(
            PointTransaction.child_id == child_id,
            PointTransaction.transaction_type.in_(EARNING_TRANSACTION_TYPES),
        )
    ).scalar_one()
    return int(total or 0)


def get_card_progress(child_id: int, points_per_card: int) -> CardProgress:
    """計算集點卡進度。"""
    if points_per_card <= 0:
        raise ValidationError("集點卡的點數設定不正確。")

    lifetime = get_lifetime_earned(child_id)
    completed = lifetime // points_per_card
    current = lifetime % points_per_card
    return CardProgress(
        lifetime_earned=lifetime,
        points_per_card=points_per_card,
        completed_cards=completed,
        current_points=current,
        remaining=points_per_card - current if current else 0,
    )


def has_transaction(source_type: str, source_id: int, transaction_type: str) -> bool:
    """檢查某個來源是否已經產生過該類型的交易。"""
    exists = db.session.execute(
        db.select(PointTransaction.id).where(
            PointTransaction.source_type == str(source_type),
            PointTransaction.source_id == source_id,
            PointTransaction.transaction_type == str(transaction_type),
        )
    ).first()
    return exists is not None


def add_transaction(
    *,
    child_id: int,
    transaction_type: TransactionType | str,
    points: int,
    source_type: SourceType | str,
    source_id: int | None,
    description: str,
    created_by: int | None = None,
) -> PointTransaction:
    """新增一筆點數交易（不 commit，由呼叫端統一 commit）。

    Raises:
        InvalidStateError: 同一來源已經有相同類型的交易（重複加點）。
    """
    if points == 0:
        raise ValidationError("點數不可以是 0。")

    if source_id is not None and has_transaction(
        str(source_type), source_id, str(transaction_type)
    ):
        raise InvalidStateError("這個動作剛剛已經完成過囉！")

    transaction = PointTransaction(
        child_id=child_id,
        transaction_type=str(transaction_type),
        points=points,
        source_type=str(source_type),
        source_id=source_id,
        description=description,
        created_by=created_by,
    )
    db.session.add(transaction)
    # flush 讓 UNIQUE constraint 立刻生效，把資料庫層的重複偵測提前到這裡，
    # 而不是等到最後 commit 才炸開。
    try:
        db.session.flush()
    except IntegrityError as exc:
        db.session.rollback()
        raise InvalidStateError("這個動作剛剛已經完成過囉！") from exc

    return transaction


def adjust_points(
    *,
    child_id: int,
    points: int,
    reason: str,
    admin_id: int,
    admin_name: str | None = None,
    allow_negative_balance: bool = False,
) -> PointTransaction:
    """家長手動調整點數。

    禁止直接寫 child.points，一律新增一筆 ADJUST / BONUS 交易。
    預設不允許把餘額扣成負數。
    """
    if points == 0:
        raise ValidationError("請輸入要增加或減少的點數。")
    if not reason.strip():
        raise ValidationError("請填寫調整的理由，這樣以後才看得懂喔！")

    child = db.session.get(Child, child_id)
    if child is None or not child.active:
        raise ValidationError("找不到這位小朋友。")

    if points < 0 and not allow_negative_balance:
        balance = get_balance(child_id)
        if balance + points < 0:
            raise InsufficientPointsError(
                f"目前只有 {balance} ⭐，不能扣掉 {abs(points)} ⭐ 喔。"
            )

    transaction_type = (
        TransactionType.BONUS if points > 0 else TransactionType.ADJUST
    )

    try:
        transaction = add_transaction(
            child_id=child_id,
            transaction_type=transaction_type,
            points=points,
            source_type=SourceType.MANUAL,
            source_id=None,
            description=reason.strip(),
            created_by=admin_id,
        )
        audit_service.record(
            AuditAction.MANUAL_POINT_ADJUSTMENT,
            actor_type=ActorType.ADMIN,
            actor_id=admin_id,
            actor_name=admin_name,
            entity_type="CHILD",
            entity_id=child_id,
            description=f"手動調整 {child.name} {points:+d} ⭐：{reason.strip()}",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return transaction


def list_transactions(child_id: int, limit: int = 200) -> list[PointTransaction]:
    """取得某個小孩的點數紀錄（新到舊）。"""
    return list(
        db.session.execute(
            db.select(PointTransaction)
            .where(PointTransaction.child_id == child_id)
            .order_by(PointTransaction.created_at.desc(), PointTransaction.id.desc())
            .limit(limit)
        ).scalars()
    )


def group_transactions_by_day(
    transactions: list[PointTransaction], tz_name: str
) -> list[tuple[date, list[PointTransaction]]]:
    """把交易依照當地日期分組，方便畫面顯示「今天 / 昨天」。"""
    grouped: dict[date, list[PointTransaction]] = {}
    for transaction in transactions:
        local: datetime | None = to_local(transaction.created_at, tz_name)
        day = local.date() if local else transaction.created_at.date()
        grouped.setdefault(day, []).append(transaction)
    return sorted(grouped.items(), key=lambda item: item[0], reverse=True)


def get_balances_for_children(child_ids: list[int]) -> dict[int, int]:
    """一次查出多個小孩的餘額，避免 Dashboard 產生 N+1 query。"""
    if not child_ids:
        return {}
    rows = db.session.execute(
        db.select(
            PointTransaction.child_id,
            func.coalesce(func.sum(PointTransaction.points), 0),
        )
        .where(PointTransaction.child_id.in_(child_ids))
        .group_by(PointTransaction.child_id)
    ).all()
    result = {child_id: 0 for child_id in child_ids}
    result.update({int(row[0]): int(row[1] or 0) for row in rows})
    return result
