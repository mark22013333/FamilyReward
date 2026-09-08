"""匯出功能的整合測試（HTTP 層）。

重點：
* 權限（未登入、小孩都不能匯出 CSV）
* 下載標頭正確（這是專案第一個下載端點）
* 獎狀的空資料路徑不會爆
* 匯出是純讀取 —— 不能憑空產生任務紀錄
"""

from __future__ import annotations

import csv
import io
import zipfile

from family_reward.models import AuditLog, TaskAssignment
from family_reward.services import point_service

QS = "year=2026&month=3"


# --------------------------------------------------------------------------
# 權限
# --------------------------------------------------------------------------


def test_anonymous_cannot_export(client):
    for path in (
        "/admin/export",
        "/admin/export/points.csv",
        "/admin/export/tasks.csv",
        "/admin/export/redemptions.csv",
        "/admin/export/all.zip",
    ):
        response = client.get(path)
        assert response.status_code == 302, path
        assert "/login/admin" in response.headers["Location"]


def test_child_cannot_export_csv(client, child, login_child):
    """試算表是家長工具。"""
    login_child(child.id)

    response = client.get("/admin/export/points.csv")

    assert response.status_code != 200


# --------------------------------------------------------------------------
# 下載標頭與內容
# --------------------------------------------------------------------------


def test_points_csv_headers(client, login_admin):
    login_admin()

    response = client.get(f"/admin/export/points.csv?{QS}")

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    disposition = response.headers["Content-Disposition"]
    assert "attachment" in disposition
    assert "family-reward-points-2026-03.csv" in disposition
    # 標頭必須是 latin-1 可編碼（HTTP 規範），中文檔名會 500
    disposition.encode("latin-1")


def test_points_csv_has_bom_and_chinese(client, child, admin_user, login_admin, today):
    """BOM 是讓 Excel 正確顯示中文的關鍵。"""
    point_service.adjust_points(
        child_id=child.id, points=5, reason="主動幫忙洗碗", admin_id=admin_user.id
    )
    login_admin()

    response = client.get(
        f"/admin/export/points.csv?year={today.year}&month={today.month}"
    )

    assert response.data.startswith(b"\xef\xbb\xbf")
    text = response.data.decode("utf-8-sig")
    assert "主動幫忙洗碗" in text
    assert "額外獎勵" in text  # 用中文標籤，不是 BONUS


def test_points_csv_never_leaks_pin_hash(client, child, admin_user, login_admin, today):
    point_service.adjust_points(
        child_id=child.id, points=1, reason="測試", admin_id=admin_user.id
    )
    login_admin()

    response = client.get(
        f"/admin/export/points.csv?year={today.year}&month={today.month}"
    )
    text = response.data.decode("utf-8-sig")

    assert child.pin_hash not in text
    assert "pbkdf2" not in text.lower()
    assert "scrypt" not in text.lower()


def test_csv_is_parseable(client, child, admin_user, login_admin, today):
    point_service.adjust_points(
        child_id=child.id, points=3, reason="測試", admin_id=admin_user.id
    )
    login_admin()

    response = client.get(
        f"/admin/export/points.csv?year={today.year}&month={today.month}"
    )
    rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))

    assert rows[0] == ["日期時間", "小孩", "類型", "點數", "說明"]
    assert len(rows) == 2


def test_tasks_and_redemptions_csv(client, child, task, reward, login_admin, today):
    login_admin()

    for kind in ("tasks", "redemptions"):
        response = client.get(
            f"/admin/export/{kind}.csv?year={today.year}&month={today.month}"
        )
        assert response.status_code == 200, kind
        assert response.data.startswith(b"\xef\xbb\xbf"), kind


def test_export_per_child_uses_id_in_filename(client, child, login_admin):
    """檔名不放小孩姓名。"""
    login_admin()

    response = client.get(f"/admin/export/points.csv?{QS}&child_id={child.id}")

    disposition = response.headers["Content-Disposition"]
    assert f"child{child.id}" in disposition
    assert "小明" not in disposition


# --------------------------------------------------------------------------
# 參數驗證
# --------------------------------------------------------------------------


def test_invalid_month_rejected(client, login_admin):
    login_admin()

    assert client.get("/admin/export/points.csv?year=2026&month=13").status_code == 400
    assert client.get("/admin/export/points.csv?year=2026&month=0").status_code == 400


def test_invalid_year_rejected(client, login_admin):
    login_admin()

    assert client.get("/admin/export/points.csv?year=1999&month=3").status_code == 400
    assert client.get("/admin/export/points.csv?year=abc&month=3").status_code == 400


def test_empty_month_still_works(client, login_admin):
    """完全沒有資料的月份也要能匯出（只有標頭）。"""
    login_admin()

    response = client.get("/admin/export/points.csv?year=2020&month=1")

    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))
    assert len(rows) == 1  # 只有標頭


# --------------------------------------------------------------------------
# 純度：匯出不能有副作用
# --------------------------------------------------------------------------


def test_export_creates_no_assignments(client, db, child, task, login_admin):
    """匯出一個過去的月份，不該憑空產生任務紀錄。"""
    login_admin()
    before = db.session.execute(
        db.select(db.func.count(TaskAssignment.id))
    ).scalar_one()

    client.get("/admin/export/tasks.csv?year=2025&month=6")

    after = db.session.execute(
        db.select(db.func.count(TaskAssignment.id))
    ).scalar_one()
    assert before == after


# --------------------------------------------------------------------------
# 稽核
# --------------------------------------------------------------------------


def test_export_is_audited(client, db, login_admin):
    """資料離開這台機器是值得留軌跡的事件。"""
    login_admin()

    client.get(f"/admin/export/points.csv?{QS}")

    log = db.session.execute(
        db.select(AuditLog).where(AuditLog.action == "EXPORT_DATA")
    ).scalars().first()
    assert log is not None
    assert log.actor_type == "ADMIN"
    assert "點數紀錄" in log.description


def test_export_audit_visible_in_history(client, login_admin):
    login_admin()
    client.get(f"/admin/export/points.csv?{QS}")

    body = client.get("/admin/history").get_data(as_text=True)

    assert "EXPORT_DATA" in body


# --------------------------------------------------------------------------
# ZIP 搬家包
# --------------------------------------------------------------------------


def test_zip_export_contains_all_csvs(client, child, admin_user, login_admin):
    point_service.adjust_points(
        child_id=child.id, points=2, reason="測試", admin_id=admin_user.id
    )
    login_admin()

    response = client.get("/admin/export/all.zip")

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/zip"

    archive = zipfile.ZipFile(io.BytesIO(response.data))
    assert set(archive.namelist()) == {
        "README.txt",
        "points.csv",
        "tasks.csv",
        "redemptions.csv",
    }
    # 資料真的有進去
    assert "測試" in archive.read("points.csv").decode("utf-8-sig")


def test_zip_readme_explains_it_is_not_a_backup(client, login_admin):
    """必須講清楚 CSV 不能還原，否則有人會把它當備份。"""
    login_admin()

    archive = zipfile.ZipFile(io.BytesIO(client.get("/admin/export/all.zip").data))
    readme = archive.read("README.txt").decode("utf-8")

    assert "不是備份" in readme
    assert "backup.bat" in readme


def test_zip_never_leaks_pin_hash(client, child, admin_user, login_admin):
    point_service.adjust_points(
        child_id=child.id, points=1, reason="測試", admin_id=admin_user.id
    )
    login_admin()

    data = client.get("/admin/export/all.zip").data
    archive = zipfile.ZipFile(io.BytesIO(data))
    everything = b"".join(archive.read(name) for name in archive.namelist())

    assert child.pin_hash.encode() not in everything
    assert b"pbkdf2" not in everything.lower()


# --------------------------------------------------------------------------
# 獎狀
# --------------------------------------------------------------------------


def test_child_can_view_own_certificate(client, child, login_child):
    login_child(child.id)

    response = client.get("/child/certificate")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert child.display_name in body
    assert "本月小星星獎狀" in body
    assert "爸爸媽媽簽名" in body


def test_certificate_does_not_show_other_child(
    client, child, other_child, login_child, admin_user
):
    """小孩只看得到自己的資料。"""
    point_service.adjust_points(
        child_id=other_child.id, points=99, reason="別人的點數", admin_id=admin_user.id
    )
    login_child(child.id)

    body = client.get("/child/certificate").get_data(as_text=True)

    assert other_child.name not in body
    assert "別人的點數" not in body


def test_anonymous_cannot_view_certificate(client, child):
    response = client.get("/child/certificate")

    assert response.status_code == 302


def test_certificate_renders_with_no_data(client, child, login_child):
    """零筆交易、沒有任何成就 —— 最容易讓模板爆掉的路徑。"""
    login_child(child.id)

    response = client.get("/child/certificate")

    assert response.status_code == 200
    assert "還沒有紀錄" in response.get_data(as_text=True)


def test_certificate_hides_locked_achievements(client, child, login_child):
    """貼在冰箱上的獎狀不該顯示 🔒 未解鎖的成就。"""
    login_child(child.id)

    body = client.get("/child/certificate").get_data(as_text=True)

    assert "🔒" not in body


def test_certificate_shows_month_points(client, child, admin_user, login_child, today):
    point_service.adjust_points(
        child_id=child.id, points=7, reason="測試", admin_id=admin_user.id
    )
    login_child(child.id)

    body = client.get(
        f"/child/certificate?year={today.year}&month={today.month}"
    ).get_data(as_text=True)

    assert "certificate__hero-number" in body


def test_certificate_is_not_audited(client, db, child, login_child):
    """小孩看自己的頁面不該被記錄 —— 那是監視。"""
    login_child(child.id)
    client.get("/child/certificate")

    logs = list(
        db.session.execute(
            db.select(AuditLog).where(AuditLog.action == "EXPORT_DATA")
        ).scalars()
    )
    assert logs == []


def test_admin_can_print_any_childs_certificate(client, child, login_admin):
    login_admin()

    response = client.get(f"/admin/children/{child.id}/certificate")

    assert response.status_code == 200
    assert child.display_name in response.get_data(as_text=True)


def test_export_page_renders(client, child, login_admin):
    login_admin()

    body = client.get("/admin/export").get_data(as_text=True)

    assert "匯出資料" in body
    # 必須說明匯出與備份的差別
    assert "不能用來還原" in body
    assert child.name in body


# --------------------------------------------------------------------------
# 列印樣式（獎狀必須剛好一張紙）
# --------------------------------------------------------------------------


def test_print_css_hides_navigation():
    """列印時導覽列、按鈕、提示都不能印出來。"""
    from pathlib import Path

    css = (
        Path(__file__).resolve().parent.parent.parent
        / "static"
        / "css"
        / "print.css"
    ).read_text(encoding="utf-8")

    assert "@media print" in css
    for selector in (".no-print", ".topbar", ".bottom-nav", ".flash-stack"):
        assert selector in css, selector


def test_print_css_disables_animations():
    """animations.css 是無條件載入的，列印時元素可能停在動畫中間的變形狀態。"""
    from pathlib import Path

    css = (
        Path(__file__).resolve().parent.parent.parent
        / "static"
        / "css"
        / "print.css"
    ).read_text(encoding="utf-8")

    assert "animation: none !important" in css


def test_print_css_keeps_backgrounds():
    """獎狀的漸層與底色要印得出來，不然會變成白紙黑字。"""
    from pathlib import Path

    css = (
        Path(__file__).resolve().parent.parent.parent
        / "static"
        / "css"
        / "print.css"
    ).read_text(encoding="utf-8")

    assert "print-color-adjust: exact" in css


def test_print_css_shrinks_stamp_grid():
    """迴歸測試：20 點的集點卡曾經把獎狀撐到第二頁。

    列印時必須縮小印章尺寸，獎狀一定要剛好一張 A4。
    """
    from pathlib import Path

    css = (
        Path(__file__).resolve().parent.parent.parent
        / "static"
        / "css"
        / "print.css"
    ).read_text(encoding="utf-8")

    print_block = css.split("@media print", 1)[1]
    assert ".stamp-grid" in print_block
    assert ".stamp {" in print_block


def test_certificate_loads_print_css(client, child, login_child):
    login_child(child.id)

    body = client.get("/child/certificate").get_data(as_text=True)

    assert "css/print.css" in body


def test_certificate_marks_ui_as_no_print(client, child, login_child):
    """回首頁、列印按鈕、操作提示都不該印在獎狀上。"""
    login_child(child.id)

    body = client.get("/child/certificate").get_data(as_text=True)

    assert "no-print" in body
    # 列印按鈕本身必須在 no-print 區塊內
    assert "window.print()" in body
