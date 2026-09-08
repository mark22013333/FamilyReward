"""獎狀資料組裝。

家長端與小孩端都會印獎狀，兩個路由共用這裡的邏輯，
避免同一份畫面有兩套資料組裝方式而慢慢走偏。

## 設計原則（給小孩看的慶祝物，不是對帳單）

* 主角數字是「**這個月**賺到的星星」，不是總餘額 ——
  小孩要看到自己這個月做了什麼，每個月印出來才會不一樣。
* 成就**只顯示已解鎖的**。貼在冰箱上的獎狀出現一堆 🔒 等於展示失敗。
* 連續天數**只在 >= 3 天時顯示**，否則讀起來像責備。
* 絕不放：PIN、生日、被退回的原因、扣點紀錄。

## 純讀取

這裡呼叫的每個函式都不會寫入資料庫。特別注意**不可以**呼叫
`assignment_service.ensure_assignments_for_date()` 或
`achievement_service.check_and_unlock()` —— 否則家長只要「印獎狀」
就會憑空產生任務紀錄。
"""

from __future__ import annotations

from typing import Any

from ..models import Child
from . import (
    achievement_service,
    assignment_service,
    calendar_service,
    point_service,
)
from ..utils.timezone import today_local

#: 連續天數少於這個值就不顯示（避免讀起來像在責備）。
STREAK_DISPLAY_MIN = 3


def build_context(
    child: Child, year: int, month: int, tz_name: str, points_per_card: int
) -> dict[str, Any]:
    """組出獎狀模板需要的所有資料。"""
    start, end = calendar_service.month_range(year, month)
    today = today_local(tz_name)

    # 這個月的統計（一次 aggregate query，不會 N+1）
    summaries = calendar_service.get_month_summary(child.id, year, month)
    month_points = sum(item.earned_points for item in summaries)
    month_approved = sum(item.approved_tasks for item in summaries)
    active_days = sum(1 for item in summaries if item.approved_tasks > 0)

    # 集點卡（以 lifetime 計算，是累積的驕傲）
    card = point_service.get_card_progress(child.id, points_per_card)

    # 成就只留已解鎖的
    unlocked = [
        view.achievement
        for view in achievement_service.list_for_child(child.id)
        if view.unlocked
    ]

    streak = assignment_service.get_streak(child.id, today)
    top_tasks = assignment_service.get_top_tasks_in_range(child.id, start, end)

    return {
        "child": child,
        "year": year,
        "month": month,
        "month_points": month_points,
        "month_approved": month_approved,
        "active_days": active_days,
        "card": card,
        "unlocked_achievements": unlocked,
        "streak": streak if streak >= STREAK_DISPLAY_MIN else 0,
        "top_tasks": top_tasks,
    }
