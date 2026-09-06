"""簡易登入失敗防護。

家庭系統不需要分散式 Rate Limiter，因此不引入 Redis。
這裡用行程內的記憶體字典記錄失敗次數，程式重啟即歸零，
對「防止有人一直猜 PIN」這個情境已經足夠。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..utils.timezone import utcnow


@dataclass
class _Attempt:
    count: int = 0
    locked_until: datetime | None = None


@dataclass
class LoginThrottle:
    """以 key（例如 "admin:alice" 或 "child:3"）為單位記錄失敗次數。"""

    max_attempts: int = 5
    lockout_minutes: int = 5
    _attempts: dict[str, _Attempt] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def is_locked(self, key: str) -> bool:
        with self._lock:
            attempt = self._attempts.get(key)
            if attempt is None or attempt.locked_until is None:
                return False
            if utcnow() >= attempt.locked_until:
                # 鎖定時間過了就重置。
                self._attempts.pop(key, None)
                return False
            return True

    def seconds_remaining(self, key: str) -> int:
        with self._lock:
            attempt = self._attempts.get(key)
            if attempt is None or attempt.locked_until is None:
                return 0
            delta = (attempt.locked_until - utcnow()).total_seconds()
            return max(0, int(delta))

    def record_failure(self, key: str) -> bool:
        """記錄一次失敗，回傳是否因此被鎖定。"""
        with self._lock:
            attempt = self._attempts.setdefault(key, _Attempt())
            attempt.count += 1
            if attempt.count >= self.max_attempts:
                attempt.locked_until = utcnow() + timedelta(minutes=self.lockout_minutes)
                return True
            return False

    def record_success(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._attempts.clear()


#: 全域單一實例；create_app() 會依 config 調整參數。
login_throttle = LoginThrottle()
