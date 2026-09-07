"""所有 Model 的匯出點。

Alembic 需要在這裡 import 全部 Model 才能偵測到 schema 變更。
"""

from __future__ import annotations

from .achievement import Achievement, ChildAchievement
from .admin_user import AdminUser
from .app_setting import AppSetting
from .audit_log import AuditLog
from .child import Child
from .enums import (
    ASSIGNMENT_STATUS_LABELS,
    AVATAR_CHOICES,
    EARNING_TRANSACTION_TYPES,
    REDEMPTION_STATUS_LABELS,
    REPEAT_TYPE_LABELS,
    TASK_CATEGORY_LABELS,
    THEME_LABELS,
    ActorType,
    AssignmentStatus,
    AuditAction,
    NotificationType,
    RedemptionStatus,
    RepeatType,
    SourceType,
    TaskCategory,
    Theme,
    TransactionType,
)
from .notification import Notification
from .point_transaction import PointTransaction
from .reward import Reward
from .reward_redemption import RewardRedemption
from .task import Task, TaskAssignee, TaskSchedule
from .task_assignment import TaskAssignment

__all__ = [
    "Achievement",
    "ChildAchievement",
    "AdminUser",
    "AppSetting",
    "AuditLog",
    "Child",
    "Notification",
    "PointTransaction",
    "Reward",
    "RewardRedemption",
    "Task",
    "TaskAssignee",
    "TaskSchedule",
    "TaskAssignment",
    "ActorType",
    "AssignmentStatus",
    "AuditAction",
    "NotificationType",
    "RedemptionStatus",
    "RepeatType",
    "SourceType",
    "TaskCategory",
    "Theme",
    "TransactionType",
    "ASSIGNMENT_STATUS_LABELS",
    "AVATAR_CHOICES",
    "EARNING_TRANSACTION_TYPES",
    "REDEMPTION_STATUS_LABELS",
    "REPEAT_TYPE_LABELS",
    "TASK_CATEGORY_LABELS",
    "THEME_LABELS",
]
