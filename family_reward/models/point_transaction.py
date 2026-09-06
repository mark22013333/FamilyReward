"""點數帳本（Ledger）。

這是整個系統的資料一致性核心，設計原則比照記帳系統：

    不可重複 / 不可憑空消失 / 不可偷偷修改歷史 / 必須有來源 / 必須有原因

禁止在 Child 上放一個 points 欄位然後 `child.points += 2`。
目前餘額一律由 SUM(points) 重算。

兩個重要概念必須分開（README / Service / Test 都有同樣說明）：

    Current Balance  = SUM(所有交易的 points)          → 用來兌換禮物
    Lifetime Earned  = SUM(EARN + BONUS 的 points)     → 用來算集點卡里程碑

集點卡使用 Lifetime Earned，所以兌換禮物不會讓「已完成的集點卡」倒退。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from ..utils.timezone import utcnow


class PointTransaction(db.Model):
    """一筆點數異動。建立後禁止刪除或修改。"""

    __tablename__ = "point_transaction"
    __table_args__ = (
        # 資料庫層的重複加點保護：
        # 同一個來源（例如 TASK_ASSIGNMENT #123）不可能有第二筆 EARN。
        # 家長連按兩次「完成」時，第二次會被這個 constraint 擋下。
        UniqueConstraint(
            "source_type",
            "source_id",
            "transaction_type",
            name="uq_point_transaction_source",
        ),
        CheckConstraint(
            "transaction_type IN ('EARN','DEDUCT','REDEEM','ADJUST','BONUS')",
            name="ck_point_transaction_type",
        ),
        CheckConstraint("points <> 0", name="ck_point_transaction_points_nonzero"),
        Index("ix_point_transaction_child_created", "child_id", "created_at"),
        Index("ix_point_transaction_child_type", "child_id", "transaction_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child.id", ondelete="CASCADE"), nullable=False
    )
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    #: 可正可負。+2 完成任務、-10 兌換禮物。
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    #: 手動調整（MANUAL）沒有對應實體，允許 NULL。
    #: 注意：SQLite 的 UNIQUE 對 NULL 不視為相等，因此多筆手動調整不會互相衝突。
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: 操作者（家長）ID，手動調整時記錄是誰調的。
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("admin_user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, index=True
    )

    child: Mapped["Child"] = relationship(back_populates="transactions")  # noqa: F821

    @property
    def is_positive(self) -> bool:
        return self.points > 0

    @property
    def signed_points(self) -> str:
        """畫面顯示用：+2 / -10"""
        return f"+{self.points}" if self.points > 0 else str(self.points)

    def __repr__(self) -> str:  # pragma: no cover - 僅供除錯
        return (
            f"<PointTransaction {self.id} child={self.child_id} "
            f"{self.transaction_type} {self.points:+d}>"
        )
