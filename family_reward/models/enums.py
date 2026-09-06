"""系統中所有狀態值的 Enum 定義。

一律使用 Enum，禁止在程式各處散落 magic string。
資料庫存的是字串值（str Enum），方便直接讀 DB 也看得懂。
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """Python 3.10 沒有內建 enum.StrEnum，這裡自行定義。"""

    def __str__(self) -> str:
        return self.value

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls.values()


class ActorType(StrEnum):
    ADMIN = "ADMIN"
    CHILD = "CHILD"
    SYSTEM = "SYSTEM"


class TaskCategory(StrEnum):
    HOUSEWORK = "HOUSEWORK"
    HOMEWORK = "HOMEWORK"
    HYGIENE = "HYGIENE"
    HABIT = "HABIT"
    BEHAVIOR = "BEHAVIOR"
    OTHER = "OTHER"


TASK_CATEGORY_LABELS: dict[str, str] = {
    TaskCategory.HOUSEWORK.value: "🧹 家事",
    TaskCategory.HOMEWORK.value: "📚 功課",
    TaskCategory.HYGIENE.value: "🪥 生活習慣",
    TaskCategory.HABIT.value: "🌱 習慣養成",
    TaskCategory.BEHAVIOR.value: "❤️ 好行為",
    TaskCategory.OTHER.value: "⭐ 其他",
}


class RepeatType(StrEnum):
    ONCE = "ONCE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    CUSTOM = "CUSTOM"


REPEAT_TYPE_LABELS: dict[str, str] = {
    RepeatType.ONCE.value: "只做一次",
    RepeatType.DAILY.value: "每天",
    RepeatType.WEEKLY.value: "每週一次",
    RepeatType.CUSTOM.value: "自訂星期",
}


class AssignmentStatus(StrEnum):
    TODO = "TODO"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


ASSIGNMENT_STATUS_LABELS: dict[str, str] = {
    AssignmentStatus.TODO.value: "還沒完成",
    AssignmentStatus.WAITING_APPROVAL.value: "⏳ 等爸爸媽媽確認",
    AssignmentStatus.APPROVED.value: "✅ 完成",
    AssignmentStatus.REJECTED.value: "💪 再努力一下",
}


class TransactionType(StrEnum):
    EARN = "EARN"
    DEDUCT = "DEDUCT"
    REDEEM = "REDEEM"
    ADJUST = "ADJUST"
    BONUS = "BONUS"


#: 計入「歷史累積取得點數（Lifetime Earned）」的交易種類。
#: 集點卡里程碑使用 Lifetime Earned，兌換禮物不會讓它倒退。
EARNING_TRANSACTION_TYPES: tuple[str, ...] = (
    TransactionType.EARN.value,
    TransactionType.BONUS.value,
)


class SourceType(StrEnum):
    TASK_ASSIGNMENT = "TASK_ASSIGNMENT"
    REWARD_REDEMPTION = "REWARD_REDEMPTION"
    MANUAL = "MANUAL"


class RedemptionStatus(StrEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


REDEMPTION_STATUS_LABELS: dict[str, str] = {
    RedemptionStatus.REQUESTED.value: "⏳ 等爸爸媽媽確認",
    RedemptionStatus.APPROVED.value: "🎉 已經換到囉",
    RedemptionStatus.COMPLETED.value: "🎁 已經拿到囉",
    RedemptionStatus.CANCELLED.value: "已取消",
    RedemptionStatus.REJECTED.value: "這次先不換喔",
}


class NotificationType(StrEnum):
    TASK_APPROVED = "TASK_APPROVED"
    TASK_REJECTED = "TASK_REJECTED"
    REWARD_APPROVED = "REWARD_APPROVED"
    REWARD_REJECTED = "REWARD_REJECTED"
    POINT_ADJUSTED = "POINT_ADJUSTED"
    ACHIEVEMENT_UNLOCKED = "ACHIEVEMENT_UNLOCKED"


class AuditAction(StrEnum):
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    LOGOUT = "LOGOUT"
    CHANGE_PASSWORD = "CHANGE_PASSWORD"

    CREATE_CHILD = "CREATE_CHILD"
    UPDATE_CHILD = "UPDATE_CHILD"
    DEACTIVATE_CHILD = "DEACTIVATE_CHILD"

    CREATE_TASK = "CREATE_TASK"
    UPDATE_TASK = "UPDATE_TASK"
    DEACTIVATE_TASK = "DEACTIVATE_TASK"

    SUBMIT_TASK = "SUBMIT_TASK"
    APPROVE_TASK = "APPROVE_TASK"
    REJECT_TASK = "REJECT_TASK"

    MANUAL_POINT_ADJUSTMENT = "MANUAL_POINT_ADJUSTMENT"

    CREATE_REWARD = "CREATE_REWARD"
    UPDATE_REWARD = "UPDATE_REWARD"
    DEACTIVATE_REWARD = "DEACTIVATE_REWARD"

    REQUEST_REWARD = "REQUEST_REWARD"
    APPROVE_REWARD = "APPROVE_REWARD"
    REJECT_REWARD = "REJECT_REWARD"
    COMPLETE_REWARD = "COMPLETE_REWARD"

    BACKUP_DATABASE = "BACKUP_DATABASE"
    CREATE_ADMIN = "CREATE_ADMIN"


class Theme(StrEnum):
    SUNNY = "SUNNY"
    OCEAN = "OCEAN"
    FOREST = "FOREST"
    CANDY = "CANDY"
    SPACE = "SPACE"


THEME_LABELS: dict[str, str] = {
    Theme.SUNNY.value: "☀️ 陽光",
    Theme.OCEAN.value: "🌊 海洋",
    Theme.FOREST.value: "🌲 森林",
    Theme.CANDY.value: "🍬 糖果",
    Theme.SPACE.value: "🚀 太空",
}

#: 第一版只提供 Emoji 頭像，避免圖片上傳的資安與儲存問題。
AVATAR_CHOICES: tuple[str, ...] = (
    "🐶", "🐱", "🐰", "🦊", "🐼", "🦁", "🐯",
    "🐸", "🐨", "🦄", "🐙", "🐧", "🐻", "🐹",
)
