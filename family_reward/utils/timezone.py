"""時間工具。

系統對外顯示與「今天是哪一天」的判斷一律使用設定的時區（預設 Asia/Taipei），
資料庫則統一存 UTC，避免夏令時間或機器時區改變造成資料錯亂。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Asia/Taipei"

WEEKDAY_ZH = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
# Python 的 weekday(): 週一=0 ... 週日=6；資料庫存的星期代碼採用同樣順序。
WEEKDAY_CODES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
WEEKDAY_CODE_ZH = {
    "MON": "一",
    "TUE": "二",
    "WED": "三",
    "THU": "四",
    "FRI": "五",
    "SAT": "六",
    "SUN": "日",
}


def get_tz(name: str = DEFAULT_TIMEZONE) -> ZoneInfo:
    return ZoneInfo(name)


def utcnow() -> datetime:
    """回傳目前的 UTC 時間（naive，供資料庫欄位使用）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def now_local(tz_name: str = DEFAULT_TIMEZONE) -> datetime:
    """回傳目前的當地時間。"""
    return datetime.now(get_tz(tz_name))


def today_local(tz_name: str = DEFAULT_TIMEZONE) -> date:
    """回傳當地時區的今天日期，任務判斷一律以此為準。"""
    return now_local(tz_name).date()


def to_local(value: datetime | None, tz_name: str = DEFAULT_TIMEZONE) -> datetime | None:
    """把資料庫存的 UTC naive datetime 轉成當地時間。"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(get_tz(tz_name))


def format_local_time(value: datetime | None, tz_name: str = DEFAULT_TIMEZONE) -> str:
    local = to_local(value, tz_name)
    return local.strftime("%H:%M") if local else ""


def format_local_datetime(value: datetime | None, tz_name: str = DEFAULT_TIMEZONE) -> str:
    local = to_local(value, tz_name)
    return local.strftime("%Y/%m/%d %H:%M") if local else ""


def format_date_friendly(value: date) -> str:
    """例如：9 月 6 日 星期日"""
    return f"{value.month} 月 {value.day} 日 {WEEKDAY_ZH[value.weekday()]}"


def weekday_code(value: date) -> str:
    """回傳該日期對應的星期代碼（MON ~ SUN）。"""
    return WEEKDAY_CODES[value.weekday()]
