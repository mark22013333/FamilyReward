"""小孩資料。

刻意不蒐集身分證、學校、地址、電話與真實照片。
頭像只能從系統提供的 Emoji 清單挑選。
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..utils.timezone import utcnow
from .enums import Theme


class Child(db.Model):
    """小孩。PIN 一律 Hash 儲存，禁止明碼。"""

    __tablename__ = "child"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_child_name_not_blank"),
        CheckConstraint("length(name) <= 50", name="ck_child_name_length"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)
    avatar: Mapped[str] = mapped_column(String(8), nullable=False, default="🐼")
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    theme: Mapped[str] = mapped_column(String(20), nullable=False, default=Theme.SUNNY.value)
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    assignments: Mapped[list["TaskAssignment"]] = relationship(  # noqa: F821
        back_populates="child", cascade="all, delete-orphan", passive_deletes=True
    )
    transactions: Mapped[list["PointTransaction"]] = relationship(  # noqa: F821
        back_populates="child", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def display_name(self) -> str:
        """畫面上優先顯示暱稱。"""
        return self.nickname or self.name

    @property
    def avatar_name(self) -> str:
        return f"{self.avatar} {self.display_name}"

    def set_pin(self, pin: str) -> None:
        self.pin_hash = generate_password_hash(pin)

    def verify_pin(self, pin: str) -> bool:
        return check_password_hash(self.pin_hash, pin)

    def is_birthday(self, today: date) -> bool:
        if not self.birthday:
            return False
        return (self.birthday.month, self.birthday.day) == (today.month, today.day)

    def __repr__(self) -> str:  # pragma: no cover - 僅供除錯
        return f"<Child {self.id} {self.name}>"
