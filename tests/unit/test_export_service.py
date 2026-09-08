"""匯出服務的單元測試。

重點：
* BOM —— 沒有它，Excel 開中文 CSV 會亂碼
* 公式注入 —— 家長輸入的理由可能被 Excel 當成公式執行
* pin_hash 絕不可以出現在任何匯出檔案裡
"""

from __future__ import annotations

import csv
import io
from datetime import date

import pytest

from family_reward.services import export_service, point_service


# --------------------------------------------------------------------------
# 編碼（Excel 相容性）
# --------------------------------------------------------------------------


def test_csv_starts_with_bom():
    """沒有 BOM 的話，Excel 在中文 Windows 上會把 UTF-8 讀成亂碼。"""
    payload = export_service.to_csv_bytes(["日期", "說明"], [["2026-03-01", "刷牙"]])

    assert payload.startswith(b"\xef\xbb\xbf")


def test_csv_roundtrips_chinese():
    payload = export_service.to_csv_bytes(
        ["日期時間", "小孩", "說明"],
        [["2026/03/01 08:00", "小明", "完成「整理玩具」"]],
    )

    text = payload.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))

    assert rows[0] == ["日期時間", "小孩", "說明"]
    assert rows[1] == ["2026/03/01 08:00", "小明", "完成「整理玩具」"]


def test_csv_uses_crlf():
    """Excel 期望 CRLF。"""
    payload = export_service.to_csv_bytes(["a"], [["b"]])

    assert b"\r\n" in payload


def test_csv_handles_empty_rows():
    payload = export_service.to_csv_bytes(["日期", "說明"], [])

    text = payload.decode("utf-8-sig")
    assert text.strip() == "日期,說明"


# --------------------------------------------------------------------------
# 公式注入
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dangerous",
    ["=SUM(A1:A9)", "+1+1", "-2 分因為沒收玩具", "@SUM(A1)"],
)
def test_formula_injection_is_neutralised(dangerous):
    """開頭是 = + - @ 的字串會被 Excel 當公式，必須加單引號。"""
    payload = export_service.to_csv_bytes(["說明"], [[dangerous]])

    text = payload.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[1][0] == "'" + dangerous


def test_normal_text_is_untouched():
    payload = export_service.to_csv_bytes(["說明"], [["完成「刷牙」"]])

    rows = list(csv.reader(io.StringIO(payload.decode("utf-8-sig"))))
    assert rows[1][0] == "完成「刷牙」"


def test_numbers_stay_numbers():
    """點數要保持數字，Excel 才能加總。負數不該被當成公式。"""
    payload = export_service.to_csv_bytes(["點數"], [[-10], [2]])

    rows = list(csv.reader(io.StringIO(payload.decode("utf-8-sig"))))
    assert rows[1][0] == "-10"
    assert rows[2][0] == "2"


# --------------------------------------------------------------------------
# emoji 前綴
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("🧹 家事", "家事"),
        ("📚 功課", "功課"),
        ("⏳ 等爸爸媽媽確認", "等爸爸媽媽確認"),
        ("家事", "家事"),
        ("", ""),
        ("HOUSEWORK", "HOUSEWORK"),
    ],
)
def test_strip_emoji_prefix(label, expected):
    assert export_service.strip_emoji_prefix(label) == expected


def test_strip_emoji_prefix_is_idempotent():
    once = export_service.strip_emoji_prefix("🧹 家事")
    assert export_service.strip_emoji_prefix(once) == once


# --------------------------------------------------------------------------
# 檔名
# --------------------------------------------------------------------------


def test_filename_is_ascii_only():
    """HTTP 標頭只能 latin-1，中文檔名會讓請求直接失敗。"""
    name = export_service.build_filename("points", date(2026, 3, 1), date(2026, 3, 31))

    name.encode("latin-1")  # 不可拋例外
    assert name == "family-reward-points-2026-03.csv"


def test_filename_uses_child_id_not_name():
    """姓名不進檔名（會流到下載資料夾、雲端同步、郵件附件）。"""
    name = export_service.build_filename(
        "points", date(2026, 3, 1), date(2026, 3, 31), child_id=3
    )

    assert name == "family-reward-points-child3-2026-03.csv"


def test_filename_for_cross_month_range():
    name = export_service.build_filename("points", date(2026, 1, 5), date(2026, 4, 2))

    assert name == "family-reward-points-2026-01-05_2026-04-02.csv"
    name.encode("latin-1")


# --------------------------------------------------------------------------
# 資料列組裝 + 隱私
# --------------------------------------------------------------------------


def test_points_rows_use_labels_not_raw_codes(db, child, admin_user):
    """不能印出 BONUS / ADJUST 這種原始代碼。"""
    point_service.adjust_points(
        child_id=child.id, points=5, reason="主動幫忙", admin_id=admin_user.id
    )
    transactions = point_service.list_transactions(child.id)

    rows = export_service.build_points_rows(transactions, "Asia/Taipei")

    assert rows[0][2] == "額外獎勵"
    assert rows[0][3] == 5
    assert rows[0][4] == "主動幫忙"
    assert "BONUS" not in str(rows[0])


def test_points_export_never_contains_pin_hash(db, child, admin_user):
    """核心隱私測試：任何匯出都不可以洩漏 PIN 的 hash。"""
    point_service.adjust_points(
        child_id=child.id, points=5, reason="測試", admin_id=admin_user.id
    )
    transactions = point_service.list_transactions(child.id)

    payload = export_service.to_csv_bytes(
        export_service.POINTS_HEADER,
        export_service.build_points_rows(transactions, "Asia/Taipei"),
    )
    text = payload.decode("utf-8-sig")

    assert child.pin_hash not in text
    for marker in ("pin_hash", "pbkdf2", "scrypt", "sha256"):
        assert marker not in text.lower()


def test_points_export_excludes_birthday(db, child, admin_user):
    """生日是 schema 裡唯一的準識別資料，不該出現在匯出檔。"""
    from datetime import date as _date

    child.birthday = _date(2018, 5, 20)
    db.session.commit()
    point_service.adjust_points(
        child_id=child.id, points=1, reason="測試", admin_id=admin_user.id
    )

    payload = export_service.to_csv_bytes(
        export_service.POINTS_HEADER,
        export_service.build_points_rows(
            point_service.list_transactions(child.id), "Asia/Taipei"
        ),
    )

    assert b"2018" not in payload


def test_tasks_rows(db, child, task, today, make_assignment):
    from family_reward.models import AssignmentStatus

    assignment = make_assignment(task, child, today)
    assignment.status = AssignmentStatus.APPROVED.value
    assignment.earned_points = 2
    db.session.commit()

    rows = export_service.build_tasks_rows([assignment], "Asia/Taipei")

    assert rows[0][0] == today.isoformat()
    assert rows[0][2] == "整理玩具"
    assert rows[0][3] == "家事"  # emoji 前綴已去掉
    assert rows[0][6] == 2


def test_tasks_rows_survive_deactivated_task(db, child, task, today, make_assignment):
    """任務被停用後仍要能匯出（用 snapshot）。"""
    assignment = make_assignment(task, child, today)
    task.active = False
    db.session.commit()

    rows = export_service.build_tasks_rows([assignment], "Asia/Taipei")

    assert rows[0][2] == "整理玩具"


def test_redemptions_rows(db, child, reward, admin_user):
    from family_reward.services import redemption_service

    point_service.adjust_points(
        child_id=child.id, points=10, reason="測試", admin_id=admin_user.id
    )
    redemption = redemption_service.request_redemption(child, reward.id)
    redemption_service.approve_redemption(redemption.id, admin_user.id)

    rows = export_service.build_redemptions_rows([redemption], "Asia/Taipei")

    assert rows[0][1] == "小明"
    assert rows[0][2] == "吃冰淇淋"
    assert rows[0][3] == 10
    assert "已經換到" in rows[0][4]
