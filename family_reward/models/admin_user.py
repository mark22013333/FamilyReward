"""家長（管理者）帳號。"""

from __future__ import annotations

from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..utils.timezone import utcnow


class AdminUser(UserMixin, db.Model):
    """管理者帳號。密碼一律 Hash 儲存，禁止明碼。

    繼承 UserMixin 以取得 Flask-Login 需要的介面；
    覆寫 is_active 讓「停用的帳號」無法登入。
    """

    __tablename__ = "admin_user"
    __table_args__ = (
        CheckConstraint("length(trim(username)) > 0", name="ck_admin_username_not_blank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    #: 是否仍在使用初始密碼；為 True 時後台會固定顯示修改密碼提醒。
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        """Flask-Login 用來判斷帳號是否可以登入。"""
        return bool(self.active)

    def set_password(self, password: str, *, is_initial: bool = False) -> None:
        self.password_hash = generate_password_hash(password)
        self.must_change_password = is_initial

    def verify_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:  # pragma: no cover - 僅供除錯
        return f"<AdminUser {self.id} {self.username}>"
