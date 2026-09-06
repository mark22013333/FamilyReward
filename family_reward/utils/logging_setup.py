"""應用程式 Log 設定。

規則：Log 內禁止出現 Password / PIN / Session ID / CSRF Token /
Secret / Cloudflare Token。寫 Log 時只記錄 ID 與動作名稱。
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    log_path: Path,
    level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    console: bool = True,
) -> logging.Logger:
    """設定 root logger：檔案 rotation + 主控台輸出。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 重複呼叫（例如測試）時先清掉舊 handler，避免 log 重複輸出。
    for handler in list(root.handlers):
        if getattr(handler, "_family_reward", False):
            root.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    file_handler = RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler._family_reward = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)

    if console:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler._family_reward = True  # type: ignore[attr-defined]
        root.addHandler(stream_handler)

    # werkzeug 的存取紀錄在正式環境太吵，降為 WARNING。
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    return logging.getLogger("family_reward")
