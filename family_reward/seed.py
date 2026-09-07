"""初始化與開發用範例資料。

`initialize()` 每次啟動都會執行（可重複執行、不會重複建立）：
    * 建立初始 Admin
    * 建立成就定義

`seed_demo_data()` 只在開發環境手動執行，正式環境不會建立 Demo 小孩。
"""

from __future__ import annotations

import logging
from datetime import date

from flask import Flask

from .config import Settings
from .extensions import db
from .models import Child, Reward, RepeatType, Task, TaskAssignee, TaskCategory
from .services import achievement_service, admin_service, settings_service

logger = logging.getLogger(__name__)


def initialize(app: Flask) -> None:
    """每次啟動都會執行的初始化工作。"""
    settings: Settings = app.settings  # type: ignore[attr-defined]

    with app.app_context():
        created = admin_service.ensure_initial_admin(
            settings.admin.initial_username, settings.admin_initial_password
        )
        if created:
            logger.info(
                "已建立初始管理者「%s」，第一次登入後請立即修改密碼。", created.username
            )

        achievement_service.ensure_definitions()

        # config.yaml 的值只是第一次建立資料庫時的種子，之後以資料庫為準。
        settings_service.ensure_defaults(settings.reward.points_per_card)
        settings_service.warn_if_config_ignored(settings.reward.points_per_card)

        logger.info("Application initialized successfully")


DEMO_TASKS: tuple[tuple[str, str, int, str, bool], ...] = (
    ("刷牙", "🪥", 1, TaskCategory.HYGIENE.value, True),
    ("寫功課", "📚", 2, TaskCategory.HOMEWORK.value, True),
    ("整理玩具", "🧸", 2, TaskCategory.HOUSEWORK.value, False),
    ("洗澡", "🚿", 1, TaskCategory.HYGIENE.value, True),
)

DEMO_REWARDS: tuple[tuple[str, str, int, int | None], ...] = (
    ("吃冰淇淋", "🍦", 10, None),
    ("玩遊戲 30 分鐘", "🎮", 10, None),
    ("選今晚看的電影", "🍿", 15, None),
)


def seed_demo_data(app: Flask, *, pin: str = "1234") -> None:
    """建立開發用的範例資料。正式環境請勿執行。"""
    settings: Settings = app.settings  # type: ignore[attr-defined]
    if settings.is_production:
        raise RuntimeError("正式環境禁止建立 Demo 資料。")

    with app.app_context():
        if db.session.execute(db.select(Child.id)).first() is not None:
            logger.info("已經有小孩資料，略過 Demo 資料建立。")
            return

        child = Child(
            name="小明",
            avatar="🐼",
            theme="SUNNY",
            active=True,
            birthday=date(2018, 5, 20),
        )
        child.set_pin(pin)
        db.session.add(child)
        db.session.flush()

        for title, icon, points, category, required in DEMO_TASKS:
            task = Task(
                title=title,
                icon=icon,
                points=points,
                category=category,
                required=required,
                repeat_type=RepeatType.DAILY.value,
                active=True,
            )
            db.session.add(task)
            db.session.flush()
            db.session.add(TaskAssignee(task_id=task.id, child_id=child.id))

        for name, icon, points_required, quantity in DEMO_REWARDS:
            db.session.add(
                Reward(
                    name=name,
                    icon=icon,
                    points_required=points_required,
                    quantity=quantity,
                    active=True,
                )
            )

        db.session.commit()
        logger.info("Demo 資料建立完成（小孩：小明，PIN：%s）", "*" * len(pin))
