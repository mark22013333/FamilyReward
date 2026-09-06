"""應用程式層級的例外類別。

這些例外代表「使用者操作不合法」，Route 會轉成友善文案顯示，
不會把技術細節（Traceback / SQL）暴露給使用者。
"""

from __future__ import annotations


class AppError(Exception):
    """所有商業邏輯例外的基底。message 是可以直接顯示給使用者的友善文案。"""

    default_message = "哎呀，好像卡住了一下 😵　再試一次看看吧！"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)
        self.message = message or self.default_message


class ValidationError(AppError):
    """輸入資料不合法。"""

    default_message = "填寫的內容好像有一點問題，再檢查一下喔！"


class NotFoundError(AppError):
    """找不到資料。"""

    default_message = "找不到這筆資料耶 🐰"


class PermissionDeniedError(AppError):
    """權限不足。"""

    default_message = "這裡是爸爸媽媽的秘密基地 🔐"


class InvalidStateError(AppError):
    """目前狀態不允許這個操作（例如重複批准）。"""

    default_message = "這個動作剛剛已經完成過囉！"


class InsufficientPointsError(AppError):
    """點數不足。"""

    default_message = "星星還不夠喔，再多完成幾個任務吧！💪"


class OutOfStockError(AppError):
    """禮物數量不足。"""

    default_message = "這個禮物暫時沒有庫存了，先看看別的吧！🎁"
