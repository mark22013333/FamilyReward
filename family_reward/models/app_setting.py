"""可以在後台修改的系統設定。

## 為什麼需要這張表

`config.yaml` 要改必須編輯檔案並重新啟動整個系統，對家長來說門檻太高。
有些參數（例如「幾點集滿一張集點卡」）是會想隨時微調的，因此改成存在資料庫，
讓後台可以直接修改、立即生效。

## 與 config.yaml 的關係

`config.yaml` 的值只當作「第一次建立資料庫時的預設值」，
之後一律以資料庫為準 —— 設定檔不應該有能力覆寫家長在後台改過的東西。

這和 `admin.initial_username` 的處理方式完全一致
（見 `admin_service.ensure_initial_admin` 與 `_warn_if_settings_look_ignored`），
全系統只有一套心智模型。

## 為什麼是 key/value 而不是每個設定一個欄位

家庭系統的設定會慢慢增加（`allow_negative_balance`、`ui.sound_enabled` 都是
下一個可能開放的候選）。key/value 表今天的成本和專用欄位相同，
但第二個設定就完全不用再動 schema。

value 一律存字串（而不是 Integer），這樣日後要存布林值或短字串都不必改結構；
型別轉換與驗證集中在 `settings_service`，呼叫端永遠拿到正確的型別。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from ..utils.timezone import utcnow


class AppSetting(db.Model):
    """一筆可在後台修改的設定。"""

    __tablename__ = "app_setting"
    __table_args__ = (
        CheckConstraint("length(trim(key)) > 0", name="ck_app_setting_key_not_blank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: 設定名稱，例如 "points_per_card"。常數定義在 settings_service。
    key: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    #: 一律存字串，型別轉換交給 settings_service。
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover - 僅供除錯
        return f"<AppSetting {self.key}={self.value!r}>"
