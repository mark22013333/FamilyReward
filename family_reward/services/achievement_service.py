"""成就服務。

第一版提供四個基本成就。判斷規則集中在 `_is_unlocked()`，
未來要新增成就只要在 seed 加一筆定義並在這裡補一個分支。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func

from ..extensions import db
from ..models import (
    Achievement,
    AssignmentStatus,
    ChildAchievement,
    NotificationType,
    TaskAssignment,
)
from . import notification_service

FIRST_STEP = "FIRST_STEP"
LITTLE_WORKER = "LITTLE_WORKER"
STREAK_MASTER = "STREAK_MASTER"
HUNDRED_CLUB = "HUNDRED_CLUB"

DEFAULT_ACHIEVEMENTS: tuple[dict[str, object], ...] = (
    {
        "code": FIRST_STEP,
        "name": "第一步",
        "description": "完成第一個任務",
        "icon": "🌱",
        "threshold": 1,
    },
    {
        "code": LITTLE_WORKER,
        "name": "小小努力家",
        "description": "總共賺到 10 點",
        "icon": "⭐",
        "threshold": 10,
    },
    {
        "code": STREAK_MASTER,
        "name": "連續達人",
        "description": "連續 7 天完成全部必做任務",
        "icon": "🔥",
        "threshold": 7,
    },
    {
        "code": HUNDRED_CLUB,
        "name": "百點高手",
        "description": "歷史累積取得 100 點",
        "icon": "🏆",
        "threshold": 100,
    },
)


@dataclass(frozen=True)
class AchievementView:
    """畫面顯示用：成就定義 + 是否已解鎖。"""

    achievement: Achievement
    unlocked: bool


def ensure_definitions() -> None:
    """確保成就定義存在（可重複執行）。"""
    existing = set(
        db.session.execute(db.select(Achievement.code)).scalars()
    )
    created = False
    for data in DEFAULT_ACHIEVEMENTS:
        if data["code"] in existing:
            continue
        db.session.add(Achievement(**data))  # type: ignore[arg-type]
        created = True
    if created:
        db.session.commit()


def check_and_unlock(child_id: int, today: date) -> list[Achievement]:
    """檢查並解鎖新達成的成就，回傳這次新解鎖的清單。"""
    from . import assignment_service, point_service

    achievements = list(
        db.session.execute(
            db.select(Achievement).where(Achievement.active.is_(True))
        ).scalars()
    )
    if not achievements:
        return []

    unlocked_ids = set(
        db.session.execute(
            db.select(ChildAchievement.achievement_id).where(
                ChildAchievement.child_id == child_id
            )
        ).scalars()
    )

    lifetime = point_service.get_lifetime_earned(child_id)
    approved_count = int(
        db.session.execute(
            db.select(func.count(TaskAssignment.id)).where(
                TaskAssignment.child_id == child_id,
                TaskAssignment.status == AssignmentStatus.APPROVED.value,
            )
        ).scalar_one()
    )
    streak = assignment_service.get_streak(child_id, today)

    newly: list[Achievement] = []
    for achievement in achievements:
        if achievement.id in unlocked_ids:
            continue
        if not _is_unlocked(achievement, lifetime, approved_count, streak):
            continue

        db.session.add(
            ChildAchievement(child_id=child_id, achievement_id=achievement.id)
        )
        notification_service.create(
            child_id=child_id,
            notification_type=NotificationType.ACHIEVEMENT_UNLOCKED,
            title=f"{achievement.icon} 解鎖新成就！",
            message=f"{achievement.name}：{achievement.description}",
        )
        newly.append(achievement)

    if newly:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    return newly


def _is_unlocked(
    achievement: Achievement, lifetime: int, approved_count: int, streak: int
) -> bool:
    if achievement.code == FIRST_STEP:
        return approved_count >= achievement.threshold
    if achievement.code in (LITTLE_WORKER, HUNDRED_CLUB):
        return lifetime >= achievement.threshold
    if achievement.code == STREAK_MASTER:
        return streak >= achievement.threshold
    return False


def list_for_child(child_id: int) -> list[AchievementView]:
    """列出所有成就與解鎖狀態。"""
    achievements = list(
        db.session.execute(
            db.select(Achievement)
            .where(Achievement.active.is_(True))
            .order_by(Achievement.threshold.asc(), Achievement.id.asc())
        ).scalars()
    )
    unlocked_ids = set(
        db.session.execute(
            db.select(ChildAchievement.achievement_id).where(
                ChildAchievement.child_id == child_id
            )
        ).scalars()
    )
    return [
        AchievementView(achievement=item, unlocked=item.id in unlocked_ids)
        for item in achievements
    ]
