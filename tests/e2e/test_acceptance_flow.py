"""端對端驗收測試（真瀏覽器 + 真 Waitress）。

完全依照需求書第 174 節「完整驗收流程」的 1 ~ 23 步驟，
用 Playwright 操作真實畫面驗證，而不是只呼叫 API。
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import ADMIN_PASSWORD, ADMIN_USERNAME

CHILD_NAME = "小明"
CHILD_PIN = "1234"
TASK_TITLE = "整理玩具"
REWARD_NAME = "吃冰淇淋"


# --------------------------------------------------------------------------
# 操作小工具
# --------------------------------------------------------------------------


def submit_main_form(page: Page) -> None:
    """送出頁面主要內容區的表單。

    刻意不用 `button[type=submit]`：那會先命中 header 的登出按鈕。
    """
    page.locator("main form button[type='submit']").first.click()


def admin_login(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/login/admin")
    page.fill("#username", ADMIN_USERNAME)
    page.fill("#password", ADMIN_PASSWORD)
    submit_main_form(page)
    expect(page).to_have_url(re.compile(r"/admin/?$"))


def admin_logout(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/admin/")
    page.click("header form button[type='submit']")
    expect(page).to_have_url(re.compile(r"/$"))


def child_login(page: Page, base_url: str, pin: str = CHILD_PIN) -> None:
    page.goto(f"{base_url}/")
    page.click(f"text={CHILD_NAME}")
    for digit in pin:
        page.click(f"[data-pin-key='{digit}']")
    # 輸滿 4 碼會自動送出
    expect(page).to_have_url(re.compile(r"/child/dashboard"), timeout=10_000)


def child_logout(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/child/dashboard")
    page.click("header form button[type='submit']")
    expect(page).to_have_url(re.compile(r"/$"))


# --------------------------------------------------------------------------
# 主要驗收流程（需求書 174 節步驟 1 ~ 21）
# --------------------------------------------------------------------------


@pytest.mark.e2e
def test_full_acceptance_flow(page: Page, live_server: str, page_errors: list[str]) -> None:
    base_url = live_server

    # --- 步驟 2：開啟首頁 ---
    page.goto(f"{base_url}/")
    expect(page.locator("h1")).to_contain_text("家庭任務集點樂園")
    expect(page.locator("body")).to_contain_text("今天是誰要開始冒險呢")
    # 還沒有小孩時顯示空狀態
    expect(page.locator("body")).to_contain_text("還沒有小朋友的資料")

    # --- 步驟 3：Admin 登入 ---
    admin_login(page, base_url)
    # 需求書第 157 節：仍使用初始密碼要有提醒
    expect(
        page.locator(".alert--warning", has_text="初始管理員密碼")
    ).to_have_count(1)

    # --- 步驟 4：建立 🐼 小明 ---
    page.goto(f"{base_url}/admin/children/new")
    page.fill("#name", CHILD_NAME)
    page.select_option("#avatar", "🐼")
    page.select_option("#theme", "SUNNY")
    page.fill("#pin", CHILD_PIN)
    submit_main_form(page)
    expect(page).to_have_url(re.compile(r"/admin/children$"))
    expect(page.locator("table")).to_contain_text(CHILD_NAME)

    # --- 步驟 5 + 6：建立「🧸 整理玩具 +2」並指派給小明（今天生效）---
    page.goto(f"{base_url}/admin/tasks/new")
    page.fill("#title", TASK_TITLE)
    page.fill("#icon", "🧸")
    page.select_option("#category", "HOUSEWORK")
    page.fill("#points", "2")
    page.select_option("#repeat_type", "DAILY")
    page.check("input[name='child_ids'][value='1']")
    submit_main_form(page)
    expect(page).to_have_url(re.compile(r"/admin/tasks$"))
    expect(page.locator("table")).to_contain_text(TASK_TITLE)

    # --- 步驟 15：建立禮物「🍦 吃冰淇淋 10 點」---
    page.goto(f"{base_url}/admin/rewards/new")
    page.fill("#name", REWARD_NAME)
    page.fill("#icon", "🍦")
    page.fill("#points_required", "10")
    submit_main_form(page)
    expect(page).to_have_url(re.compile(r"/admin/rewards$"))
    expect(page.locator("table")).to_contain_text(REWARD_NAME)

    admin_logout(page, base_url)

    # --- 步驟 7：小明使用 PIN 登入 ---
    child_login(page, base_url)
    expect(page.locator(".greeting__hello")).to_contain_text(CHILD_NAME)

    # --- 步驟 8：看到「🧸 整理玩具 +2 ⭐ [我完成了！]」---
    task_card = page.locator(".card", has_text=TASK_TITLE).first
    expect(task_card).to_contain_text("+2 ⭐")
    expect(task_card.get_by_role("button", name="我完成了！")).to_be_visible()

    # --- 步驟 9：按下「我完成了！」---
    task_card.get_by_role("button", name="我完成了！").click()
    expect(page.locator(".flash")).to_contain_text("收到啦")

    # 送出後不能再按（按鈕消失，改顯示等待中）
    task_card = page.locator(".card", has_text=TASK_TITLE).first
    expect(task_card).to_contain_text("等爸爸媽媽確認")
    expect(task_card.get_by_role("button", name="我完成了！")).to_have_count(0)

    # 此時還沒有點數
    expect(page.locator(".star-balance")).to_contain_text("0")

    child_logout(page, base_url)

    # --- 步驟 10：Admin 看到待確認 ---
    admin_login(page, base_url)
    page.goto(f"{base_url}/admin/approvals")
    approval = page.locator(".card", has_text=TASK_TITLE).first
    expect(approval).to_contain_text(CHILD_NAME)
    expect(approval).to_contain_text("可以獲得 +2 ⭐")

    # --- 步驟 11：Admin 批准 ---
    approval.get_by_role("button", name="完成 👍").click()
    expect(page.locator(".flash")).to_contain_text("已確認完成")

    # --- 步驟 12：確認 PointTransaction 只有一筆 +2 ---
    page.goto(f"{base_url}/admin/points?child_id=1")
    earn_rows = page.locator("table tbody tr", has_text="完成「整理玩具」")
    expect(earn_rows).to_have_count(1)
    expect(earn_rows.first).to_contain_text("+2")

    admin_logout(page, base_url)

    # --- 步驟 13：小明重新進入看到 🎉 +2 ⭐ ---
    child_login(page, base_url)
    # 這裡會同時出現「任務通過」與「解鎖成就」兩張慶祝卡，取任務那張。
    celebrate = page.locator(".celebrate", has_text="太棒了").first
    expect(celebrate).to_contain_text("「整理玩具」通過確認")
    expect(celebrate).to_contain_text("+2 ⭐")
    # 成就也應該同時解鎖（需求書第 109 節）
    expect(page.locator(".celebrate", has_text="解鎖新成就")).to_have_count(1)
    expect(page.locator(".star-balance")).to_contain_text("2")

    # 重新整理不會再播一次（需求書第 107 節）
    page.reload()
    expect(page.locator(".celebrate")).to_have_count(0)

    # 集點卡：2 / 10
    expect(page.locator(".points-card")).to_contain_text("2 / 10")

    child_logout(page, base_url)

    # --- 步驟 14：累積到 10 點，集點卡顯示 10 / 10（完成一張）---
    admin_login(page, base_url)
    page.goto(f"{base_url}/admin/points")
    page.select_option("#child_id", "1")
    page.fill("#points", "8")
    page.fill("#reason", "這週表現很棒")
    submit_main_form(page)
    expect(page.locator(".flash")).to_contain_text("點數已經調整完成")
    admin_logout(page, base_url)

    child_login(page, base_url)
    expect(page.locator(".star-balance")).to_contain_text("10")
    points_card = page.locator(".points-card")
    expect(points_card).to_contain_text("已經完成 1 張集點卡")
    expect(points_card).to_contain_text("歷史總共取得 10 ⭐")

    # --- 步驟 16：小明申請兌換禮物 ---
    page.goto(f"{base_url}/child/rewards")
    reward_card = page.locator(".card", has_text=REWARD_NAME).first
    expect(reward_card).to_contain_text("需要 10 ⭐")
    reward_card.get_by_role("button", name="我要這個！").click()
    expect(page.locator(".flash")).to_contain_text("跟爸爸媽媽說好囉")

    # 申請當下還沒扣點
    page.goto(f"{base_url}/child/dashboard")
    expect(page.locator(".star-balance")).to_contain_text("10")

    child_logout(page, base_url)

    # --- 步驟 17：Admin 批准兌換 ---
    admin_login(page, base_url)
    page.goto(f"{base_url}/admin/redemptions")
    redemption = page.locator(".card", has_text=REWARD_NAME).first
    redemption.get_by_role("button", name="確認兌換 🎁").click()
    expect(page.locator(".flash")).to_contain_text("已確認兌換")

    # --- 步驟 18 + 19：Balance 扣 10，Lifetime Earned 沒有倒退 ---
    page.goto(f"{base_url}/admin/points")
    summary_row = page.locator("table tbody tr", has_text=CHILD_NAME).first
    expect(summary_row).to_contain_text("0 ⭐")   # 目前點數
    expect(summary_row).to_contain_text("10 ⭐")  # 歷史取得
    expect(summary_row).to_contain_text("完成 1 張")  # 集點卡沒有倒退

    admin_logout(page, base_url)

    # --- 步驟 20：Calendar 正常顯示今日任務、完成數、今日點數 ---
    child_login(page, base_url)
    page.goto(f"{base_url}/child/calendar")
    # 等待 API 資料載入完成（載入中的提示會被移除）
    page.wait_for_selector("[data-calendar] .calendar-cell", timeout=10_000)
    today_cell = page.locator(".calendar-cell--today")
    expect(today_cell).to_have_count(1)
    expect(today_cell).to_contain_text("✅ 1/1")
    expect(today_cell).to_contain_text("⭐ +2")

    # 點進今天看明細
    today_cell.click()
    expect(page.locator("body")).to_contain_text(TASK_TITLE)
    expect(page.locator("body")).to_contain_text("今日總共")

    # 集點卡在兌換後仍然是「完成 1 張」
    page.goto(f"{base_url}/child/dashboard")
    expect(page.locator(".points-card")).to_contain_text("已經完成 1 張集點卡")
    expect(page.locator(".star-balance")).to_contain_text("0")

    # 整個流程不能有任何 JavaScript 錯誤或 CSP 違規
    assert page_errors == [], f"頁面出現錯誤：{page_errors}"


# --------------------------------------------------------------------------
# 資料一致性（需求書第 184 節）
# --------------------------------------------------------------------------


@pytest.mark.e2e
def test_double_approve_does_not_double_points(page: Page, live_server: str) -> None:
    """家長連按兩次「完成」，只能加一次點數。"""
    base_url = live_server

    admin_login(page, base_url)
    page.goto(f"{base_url}/admin/children/new")
    page.fill("#name", "小美")
    page.select_option("#avatar", "🦄")
    page.fill("#pin", "5678")
    submit_main_form(page)

    # 找出小美的 id（畫面上不顯示 ID，從編輯連結取得）
    row = page.locator("table tbody tr", has_text="小美").first
    edit_href = row.get_by_role("link", name="修改").get_attribute("href")
    child_id = re.search(r"/children/(\d+)/edit", edit_href).group(1)

    page.goto(f"{base_url}/admin/tasks/new")
    page.fill("#title", "刷牙")
    page.fill("#icon", "🪥")
    page.fill("#points", "1")
    page.select_option("#repeat_type", "DAILY")
    page.check(f"input[name='child_ids'][value='{child_id}']")
    submit_main_form(page)
    admin_logout(page, base_url)

    # 小美完成任務
    page.goto(f"{base_url}/")
    page.click("text=小美")
    for digit in "5678":
        page.click(f"[data-pin-key='{digit}']")
    expect(page).to_have_url(re.compile(r"/child/dashboard"), timeout=10_000)
    page.locator(".card", has_text="刷牙").first.get_by_role(
        "button", name="我完成了！"
    ).click()
    child_logout(page, base_url)

    # 家長批准，然後用「上一頁 + 重送」模擬連按兩次
    admin_login(page, base_url)
    page.goto(f"{base_url}/admin/approvals")
    approve_form = page.locator("form", has=page.get_by_role("button", name="完成 👍")).first
    action = approve_form.get_attribute("action")
    page.get_by_role("button", name="完成 👍").first.click()
    expect(page.locator(".flash")).to_contain_text("已確認完成")

    # 直接重送同一個 POST（等同快速按第二次）。
    # 用 request.post 而不是在頁面裡建表單送出：後者會讓頁面停在
    # 導航途中，下一個 goto 會被瀏覽器取消而拋 ERR_ABORTED。
    token = page.locator("input[name='csrf_token']").first.input_value()
    second = page.request.post(
        f"{base_url}{action}",
        form={"csrf_token": token},
        headers={"Referer": f"{base_url}/admin/approvals"},
    )
    assert second.status < 500, f"重複批准不該造成伺服器錯誤（{second.status}）"

    # 只能有一筆 +1，餘額必須是 1
    page.goto(f"{base_url}/admin/points?child_id={child_id}")
    earn_rows = page.locator("table tbody tr", has_text="完成「刷牙」")
    expect(earn_rows).to_have_count(1)

    summary_row = page.locator("table tbody tr", has_text="小美").first
    expect(summary_row).to_contain_text("1 ⭐")


@pytest.mark.e2e
def test_child_cannot_reach_admin_pages(page: Page, live_server: str) -> None:
    """需求書第 159 節：小孩手動輸入 /admin 必須被擋下。"""
    base_url = live_server

    child_login(page, base_url)

    page.goto(f"{base_url}/admin/")
    expect(page).to_have_url(re.compile(r"/login/admin"))
    expect(page.locator("body")).to_contain_text("秘密基地")

    for path in ("/admin/children", "/admin/points", "/admin/settings"):
        page.goto(f"{base_url}{path}")
        expect(page).to_have_url(re.compile(r"/login/admin"))


@pytest.mark.e2e
def test_insufficient_points_shows_friendly_lock(page: Page, live_server: str) -> None:
    """點數不夠時顯示還差幾顆星星，且沒有兌換按鈕。"""
    base_url = live_server

    admin_login(page, base_url)
    page.goto(f"{base_url}/admin/rewards/new")
    page.fill("#name", "去遊樂園")
    page.fill("#icon", "🎡")
    page.fill("#points_required", "50")
    submit_main_form(page)
    admin_logout(page, base_url)

    child_login(page, base_url)
    page.goto(f"{base_url}/child/rewards")

    locked = page.locator(".card", has_text="去遊樂園").first
    expect(locked).to_contain_text("🔒")
    expect(locked).to_contain_text("還差")
    expect(locked.get_by_role("button", name="我要這個！")).to_have_count(0)


@pytest.mark.e2e
def test_error_pages_are_friendly(page: Page, live_server: str) -> None:
    """需求書第 95 ~ 97 節：錯誤頁面要友善，不得洩漏技術細節。"""
    base_url = live_server

    response = page.goto(f"{base_url}/this-page-does-not-exist")
    assert response is not None and response.status == 404
    body = page.locator("body")
    expect(body).to_contain_text("這個頁面好像跑去玩了")
    # 不得出現 Traceback / SQL / 路徑
    for leak in ("Traceback", "SELECT", "sqlalchemy", "C:\\"):
        assert leak not in page.content(), f"錯誤頁面洩漏了：{leak}"


@pytest.mark.e2e
def test_health_endpoint_minimal(page: Page, live_server: str) -> None:
    """需求書第 93 節：/health 只能回 status。"""
    response = page.request.get(f"{live_server}/health")

    assert response.status == 200
    assert response.json() == {"status": "UP"}


@pytest.mark.e2e
def test_reduced_motion_disables_confetti(
    browser, live_server: str
) -> None:  # noqa: ANN001
    """需求書第 102 節：prefers-reduced-motion 要關閉 Confetti。"""
    context = browser.new_context(
        viewport={"width": 414, "height": 896},
        reduced_motion="reduce",
        locale="zh-TW",
    )
    page = context.new_page()
    try:
        page.goto(f"{live_server}/")
        # CSS 已經把 .confetti-layer 設為 display:none，
        # 這裡驗證 JS 也不會產生節點。
        page.wait_for_load_state()
        assert page.locator(".confetti-layer").count() == 0
        matches = page.evaluate(
            "window.matchMedia('(prefers-reduced-motion: reduce)').matches"
        )
        assert matches is True
    finally:
        context.close()


@pytest.mark.e2e
def test_static_assets_load(page: Page, live_server: str, page_errors: list[str]) -> None:
    """確認 CSS / JS 沒有被 CSP 擋掉，也沒有 404。"""
    failed: list[str] = []
    page.on(
        "response",
        lambda response: failed.append(f"{response.status} {response.url}")
        if response.status >= 400
        else None,
    )

    page.goto(f"{live_server}/")
    page.wait_for_load_state("networkidle")

    assert failed == [], f"有資源載入失敗：{failed}"
    assert page_errors == [], f"頁面出現錯誤：{page_errors}"

    # 確認 CSS 真的生效（背景色來自 variables.css）
    background = page.evaluate(
        "getComputedStyle(document.body).backgroundColor"
    )
    assert background not in ("", "rgba(0, 0, 0, 0)"), "CSS 沒有套用"


@pytest.mark.e2e
def test_mobile_touch_targets(page: Page, live_server: str) -> None:
    """需求書第 100 節：主要操作按鈕至少 48px 高。"""
    page.goto(f"{live_server}/login/admin")
    # 必須等樣式表套用完成，否則量到的是還沒上 CSS 的高度。
    page.wait_for_load_state("networkidle")

    height = page.evaluate(
        "document.querySelector(\"main form button[type='submit']\")"
        ".getBoundingClientRect().height"
    )
    assert height >= 48, f"主要按鈕只有 {height}px，不符合 48px 的要求"

    # 小孩畫面的主要操作按鈕（我完成了！）也要夠大。
    page.goto(f"{live_server}/")
    page.wait_for_load_state("networkidle")
    tile_height = page.evaluate(
        """(() => {
            const el = document.querySelector('.child-tile, main .btn');
            return el ? el.getBoundingClientRect().height : 0;
        })()"""
    )
    assert tile_height >= 48, f"首頁主要按鈕只有 {tile_height}px"


@pytest.mark.e2e
def test_no_horizontal_scroll_on_mobile(page: Page, live_server: str) -> None:
    """手機上不能出現整頁的橫向捲動。"""
    for path in ("/", "/login/admin"):
        page.goto(f"{live_server}{path}")
        page.wait_for_load_state()
        overflow = page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert overflow <= 1, f"{path} 出現橫向捲動（超出 {overflow}px）"
