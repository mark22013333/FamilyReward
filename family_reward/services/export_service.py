"""匯出服務 —— 只負責把資料轉成檔案格式，查詢留在各自的 service。

## 為什麼是 CSV 而不是 Excel

`csv` 是 Python 標準函式庫，零新依賴。Excel 能直接開，
記帳軟體、Google Sheets 也都吃 CSV。這符合專案「能用標準函式庫就用」的原則。

## 三個容易被忽略但一定要處理的細節

1. **`utf-8-sig`（含 BOM）** —— 不加 BOM 的話，Excel 在中文 Windows 上
   會用系統代碼頁（CP950）解讀 UTF-8，中文全部變亂碼。
   這和 BAT 檔那個坑是同一類問題。

2. **公式注入** —— 開頭是 `= + - @` 的字串，Excel 會當成公式執行。
   家長輸入的調整理由是自由文字，所以必須處理。

3. **emoji** —— Excel 對 emoji 的支援不一致，所以 CSV 裡的分類標籤
   去掉 emoji 前綴（「🧹 家事」→「家事」）。
   畫面與獎狀上保留 emoji，只有 CSV 去掉。

## 安全性

所有資料列都由**明確列出的欄位**組成，
禁止使用 `vars()`、`__dict__`、`SELECT *` —— 這樣 `pin_hash`
之類的敏感欄位在結構上就不可能被匯出，而不是靠寫程式的人記得避開。
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Iterable, Sequence

from ..models import (
    ASSIGNMENT_STATUS_LABELS,
    REDEMPTION_STATUS_LABELS,
    TASK_CATEGORY_LABELS,
    TRANSACTION_TYPE_LABELS,
    PointTransaction,
    RewardRedemption,
    TaskAssignment,
)
from ..utils.timezone import format_local_datetime, to_local

#: Excel 會把開頭是這些字元的字串當成公式。
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def strip_emoji_prefix(label: str) -> str:
    """把「🧹 家事」變成「家事」。

    只處理「非 ASCII 開頭 + 空白 + 文字」這種標籤格式，
    刻意不引入 emoji 正規表示式套件。
    """
    if not label:
        return label

    parts = label.split(" ", 1)
    if len(parts) == 2 and parts[0] and not parts[0].isascii():
        return parts[1].strip()
    return label


def _sanitise_cell(value: object) -> object:
    """防止 Excel 公式注入。

    開頭是 = + - @ 的字串，Excel 會當成公式執行
    （例如家長把理由寫成「-2 分因為...」）。前面加單引號讓它保持文字。
    數字型別不受影響。
    """
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def to_csv_bytes(header: Sequence[str], rows: Iterable[Sequence[object]]) -> bytes:
    """把標頭與資料列轉成 CSV bytes。

    使用 `utf-8-sig`（含 BOM）+ CRLF，這是 Excel 在 Windows 上的要求。
    回傳 bytes 而不是 str，避免呼叫端不小心又編碼一次。
    """
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(list(header))
    for row in rows:
        writer.writerow([_sanitise_cell(cell) for cell in row])

    return buffer.getvalue().encode("utf-8-sig")


# --------------------------------------------------------------------------
# 各種匯出的欄位定義
#
# 注意：每一份都是「明確列出要哪些欄位」，
# 所以 pin_hash / birthday / password_hash 在結構上不可能被匯出。
# --------------------------------------------------------------------------


POINTS_HEADER = ["日期時間", "小孩", "類型", "點數", "說明"]


def build_points_rows(
    transactions: Iterable[PointTransaction], tz_name: str
) -> list[list[object]]:
    """點數帳本：每一筆加點與扣點。"""
    rows: list[list[object]] = []
    for transaction in transactions:
        child = transaction.child
        rows.append(
            [
                format_local_datetime(transaction.created_at, tz_name),
                child.name if child else "",
                TRANSACTION_TYPE_LABELS.get(
                    transaction.transaction_type, transaction.transaction_type
                ),
                transaction.points,  # 數字保持數字，Excel 才能加總
                transaction.description,
            ]
        )
    return rows


TASKS_HEADER = [
    "日期",
    "小孩",
    "任務",
    "分類",
    "必做",
    "狀態",
    "得到點數",
    "送出時間",
    "確認時間",
]


def build_tasks_rows(
    assignments: Iterable[TaskAssignment], tz_name: str
) -> list[list[object]]:
    """任務完成明細。用 snapshot 欄位，所以任務改名不影響歷史。"""
    rows: list[list[object]] = []
    for assignment in assignments:
        child = assignment.child
        task = assignment.task
        category = (
            strip_emoji_prefix(TASK_CATEGORY_LABELS.get(task.category, task.category))
            if task
            else ""
        )
        rows.append(
            [
                assignment.assignment_date.isoformat(),
                child.name if child else "",
                assignment.task_title_snapshot,
                category,
                "是" if assignment.required_snapshot else "",
                strip_emoji_prefix(
                    ASSIGNMENT_STATUS_LABELS.get(assignment.status, assignment.status)
                ),
                assignment.earned_points,
                format_local_datetime(assignment.submitted_at, tz_name),
                format_local_datetime(assignment.approved_at, tz_name),
            ]
        )
    return rows


REDEMPTIONS_HEADER = ["申請時間", "小孩", "禮物", "花費點數", "狀態", "處理時間"]


def build_redemptions_rows(
    redemptions: Iterable[RewardRedemption], tz_name: str
) -> list[list[object]]:
    """禮物兌換紀錄。"""
    rows: list[list[object]] = []
    for redemption in redemptions:
        child = redemption.child
        handled_at = redemption.approved_at or redemption.cancelled_at
        rows.append(
            [
                format_local_datetime(redemption.requested_at, tz_name),
                child.name if child else "",
                redemption.reward_name_snapshot,
                redemption.points,
                strip_emoji_prefix(
                    REDEMPTION_STATUS_LABELS.get(redemption.status, redemption.status)
                ),
                format_local_datetime(handled_at, tz_name),
            ]
        )
    return rows


# --------------------------------------------------------------------------
# 檔名
# --------------------------------------------------------------------------


def build_full_zip(tz_name: str) -> bytes:
    """把所有紀錄打包成 ZIP（搬家／留存用）。

    這是「資料可攜」的逃生口 —— 即使日後不用這套系統，
    紀錄仍然是人看得懂的 CSV。

    **這不是備份**：不能用來還原系統（沒有 schema、沒有 PIN、沒有設定）。
    ZIP 裡的 README.txt 會把這件事講清楚。
    """
    import zipfile

    from . import assignment_service, point_service, redemption_service
    from ..utils.timezone import now_local

    # 用很寬的範圍把所有資料撈出來（家庭系統的資料量很小）
    wide_start = date(2000, 1, 1)
    wide_end = date(2100, 12, 31)

    generated_at = now_local(tz_name).strftime("%Y/%m/%d %H:%M")
    readme = f"""家庭任務集點樂園 —— 資料匯出
================================

匯出時間：{generated_at}

檔案說明
--------
points.csv       點數紀錄：每一筆加點與扣點
tasks.csv        任務完成明細
redemptions.csv  禮物兌換紀錄

編碼
----
UTF-8 含 BOM，Excel 可以直接開，中文不會亂碼。

重要：這不是備份
----------------
這些 CSV 是給「人」看的，**不能用來還原系統**。
它沒有包含帳號密碼、PIN、系統設定與資料庫結構。

要能還原的備份請用 backup.bat（產生 .db 檔），
或後台的「⚙️ 設定 → 備份」。
"""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", readme.encode("utf-8"))

        archive.writestr(
            "points.csv",
            to_csv_bytes(
                POINTS_HEADER,
                build_points_rows(
                    point_service.list_transactions_in_range(
                        None, wide_start, wide_end, tz_name
                    ),
                    tz_name,
                ),
            ),
        )
        archive.writestr(
            "tasks.csv",
            to_csv_bytes(
                TASKS_HEADER,
                build_tasks_rows(
                    assignment_service.list_assignments_in_range(
                        None, wide_start, wide_end
                    ),
                    tz_name,
                ),
            ),
        )
        archive.writestr(
            "redemptions.csv",
            to_csv_bytes(
                REDEMPTIONS_HEADER,
                build_redemptions_rows(
                    redemption_service.list_redemptions_in_range(
                        None, wide_start, wide_end, tz_name
                    ),
                    tz_name,
                ),
            ),
        )

    return buffer.getvalue()


def build_filename(kind: str, start: date, end: date, child_id: int | None = None) -> str:
    """組出 ASCII 檔名。

    **必須是純 ASCII** —— HTTP 的 Content-Disposition 標頭只能是 latin-1，
    放中文會直接讓請求失敗（和 BAT 檔那個坑同一類問題）。

    也刻意不放小孩姓名：檔案會進到「下載」資料夾、雲端同步、郵件附件，
    姓名放在檔案內容裡就好。
    """
    scope = f"-child{child_id}" if child_id is not None else ""

    if start.year == end.year and start.month == end.month:
        period = f"{start.year:04d}-{start.month:02d}"
    else:
        period = f"{start.isoformat()}_{end.isoformat()}"

    return f"family-reward-{kind}{scope}-{period}.csv"
