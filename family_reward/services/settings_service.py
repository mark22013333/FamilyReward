"""後台可修改的系統設定。

## 分層規則（重要）

    資料庫 > config.yaml

`config.yaml` 的值只當「第一次建立資料庫時的種子」，之後一律以資料庫為準。
設定檔不應該有能力覆寫家長在後台改過的東西 —— 這和
`admin_service.ensure_initial_admin` 對 `admin.initial_username` 的處理完全一致。

## 為什麼不做 cache

讀取是「單列 + unique index 的本地 SQLite 查詢」，一頁最多 1 次，成本可忽略。
而 cache 正是這個功能想解決的問題本身（改了設定卻顯示舊值）；
`point_service.get_balance` 的 docstring 也已立下規則：
「永遠即時重算，不依賴任何 cache 欄位」。

如果將來真的量測出瓶頸，正確做法是 request 範圍的 `flask.g` memo，
而不是跨執行緒的模組層 cache（Waitress 有 8 條執行緒，模組 cache 會很難推理）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from flask import current_app

from ..exceptions import ValidationError
from ..extensions import db
from ..models import ActorType, AppSetting, AuditAction
from . import audit_service

logger = logging.getLogger(__name__)

#: 設定的 key 名稱。
KEY_POINTS_PER_CARD = "points_per_card"

#: 集點卡點數的允許範圍。
#: 上限刻意不設太高 —— 集點卡是給小孩看的，設成 9999 等於永遠集不滿。
MIN_POINTS_PER_CARD = 1
MAX_POINTS_PER_CARD = 100


@dataclass(frozen=True)
class CardChangePreview:
    """改變集點卡點數後，某個小孩會受到的影響。

    用途：後台儲存前先告訴家長「小明目前完成 2 張，會變成 1 張」。
    """

    child_name: str
    lifetime_earned: int
    before_cards: int
    before_current: int
    after_cards: int
    after_current: int

    @property
    def changed(self) -> bool:
        return self.before_cards != self.after_cards


# --------------------------------------------------------------------------
# 基本讀寫
# --------------------------------------------------------------------------


def get_raw(key: str) -> str | None:
    """讀取原始字串值；沒有這筆設定就回傳 None。"""
    return db.session.execute(
        db.select(AppSetting.value).where(AppSetting.key == key)
    ).scalar_one_or_none()


def ensure_defaults(points_per_card: int) -> None:
    """確保設定資料列存在（可重複執行，比照 achievement_service.ensure_definitions）。

    只在資料列不存在時建立，絕不覆寫既有的值 ——
    否則每次重新啟動都會把家長改過的設定蓋回 config.yaml 的值。
    """
    if get_raw(KEY_POINTS_PER_CARD) is not None:
        return

    db.session.add(
        AppSetting(key=KEY_POINTS_PER_CARD, value=str(int(points_per_card)))
    )
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    logger.info("已建立預設設定 %s=%s", KEY_POINTS_PER_CARD, points_per_card)


# --------------------------------------------------------------------------
# 集點卡點數
# --------------------------------------------------------------------------


def _fallback_points_per_card() -> int:
    """設定讀不到時退回 config.yaml 的值。"""
    return int(current_app.settings.reward.points_per_card)  # type: ignore[attr-defined]


def get_points_per_card() -> int:
    """讀取目前的「幾點集滿一張集點卡」。

    以資料庫為準；資料列不存在或內容壞掉時退回 config.yaml 的值。

    刻意 fail-soft 而不是拋例外：小孩的首頁不能因為一筆設定不見就整頁壞掉。
    """
    raw = get_raw(KEY_POINTS_PER_CARD)

    if raw is not None:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            logger.warning(
                "設定 %s 不是數字（%r），改用設定檔的值。", KEY_POINTS_PER_CARD, raw
            )
        else:
            if value > 0:
                return value
            logger.warning(
                "設定 %s 是 %d，不是合法的點數，改用設定檔的值。",
                KEY_POINTS_PER_CARD,
                value,
            )

    return _fallback_points_per_card()


def set_points_per_card(
    value: int, *, admin_id: int, admin_name: str | None = None
) -> int:
    """修改「幾點集滿一張集點卡」，回傳修改前的舊值。

    集點卡進度一律由 lifetime_earned 即時重算，所以改了設定之後
    「已完成幾張」會跟著變 —— 這是刻意的設計：只保留一個真相來源，
    不做歷史快照。後台畫面會先把影響告知家長再儲存。

    這個變更完全可逆：把數字改回去，張數就會原樣回來。

    Raises:
        ValidationError: 超出允許範圍，或與目前的值相同。
    """
    # Service 層自己驗範圍，不能只依賴 form ——
    # 腳本或其他程式直接呼叫時也必須擋下來。
    if not (MIN_POINTS_PER_CARD <= value <= MAX_POINTS_PER_CARD):
        raise ValidationError(
            f"集點卡的點數必須介於 {MIN_POINTS_PER_CARD} ~ {MAX_POINTS_PER_CARD} 點。"
        )

    old_value = get_points_per_card()
    if value == old_value:
        raise ValidationError("新的設定和目前的一樣。")

    row = db.session.execute(
        db.select(AppSetting).where(AppSetting.key == KEY_POINTS_PER_CARD)
    ).scalar_one_or_none()

    try:
        if row is None:
            row = AppSetting(key=KEY_POINTS_PER_CARD, value=str(value))
            db.session.add(row)
            db.session.flush()
        else:
            row.value = str(value)

        audit_service.record(
            AuditAction.UPDATE_APP_SETTING,
            actor_type=ActorType.ADMIN,
            actor_id=admin_id,
            actor_name=admin_name,
            entity_type="APP_SETTING",
            entity_id=row.id,
            description=f"集點卡點數由 {old_value} 改為 {value}",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    logger.info("集點卡點數由 %d 改為 %d", old_value, value)
    return old_value


def preview_points_per_card_change(new_value: int) -> list[CardChangePreview]:
    """算出改成 new_value 之後，每個小孩的集點卡張數會怎麼變。

    用同樣的整數運算（lifetime // n、lifetime % n）與 get_card_progress 一致。
    """
    from . import child_service, point_service

    current = get_points_per_card()
    previews: list[CardChangePreview] = []

    for child in child_service.list_children(only_active=True):
        lifetime = point_service.get_lifetime_earned(child.id)
        preview = CardChangePreview(
            child_name=child.display_name,
            lifetime_earned=lifetime,
            before_cards=lifetime // current if current > 0 else 0,
            before_current=lifetime % current if current > 0 else 0,
            after_cards=lifetime // new_value if new_value > 0 else 0,
            after_current=lifetime % new_value if new_value > 0 else 0,
        )
        previews.append(preview)

    return previews


def warn_if_config_ignored(configured_points_per_card: int) -> None:
    """啟動時若 config.yaml 與資料庫不一致就警告。

    背景：使用者很容易改了 config.yaml 卻發現沒生效（`admin.initial_username`
    就發生過這件事）。這裡主動說出來，而不是默默忽略。
    """
    raw = get_raw(KEY_POINTS_PER_CARD)
    if raw is None:
        return

    try:
        stored = int(raw)
    except (TypeError, ValueError):
        return

    if stored != int(configured_points_per_card):
        logger.warning(
            "config.yaml 的 reward.points_per_card 是 %d，但目前實際使用的是 %d。"
            "這個設定只在第一次建立資料庫時生效，改了不會套用。"
            "要修改請到後台的「設定」頁。",
            configured_points_per_card,
            stored,
        )
