"""小孩頁面：今天的任務、行事曆、禮物、我的紀錄。

所有頁面都用 @child_required 保護，
需要指定某筆資料時一律以 session 中的 child.id 為準，
不接受從網址傳進來的 child_id（避免看到別人的資料）。
"""

from __future__ import annotations

from datetime import date

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from ..exceptions import AppError
from ..forms import ConfirmForm
from ..models import ASSIGNMENT_STATUS_LABELS, AssignmentStatus
from ..security.auth import child_required, get_current_child
from ..services import (
    achievement_service,
    assignment_service,
    calendar_service,
    notification_service,
    point_service,
    redemption_service,
    reward_service,
    settings_service,
)
from ..utils.timezone import today_local

child_bp = Blueprint("child", __name__, url_prefix="/child")


def _tz() -> str:
    return current_app.settings.app.timezone  # type: ignore[attr-defined]


def _points_per_card() -> int:
    """讀取目前的集點卡點數。

    每個 request 都重新讀資料庫，所以家長在後台改了之後
    下一次載入頁面就會生效，不需要重新啟動。
    """
    return settings_service.get_points_per_card()


@child_bp.route("/dashboard")
@child_required
def dashboard():  # noqa: ANN201
    """小孩首頁：星星、集點卡、今天的任務、下一個禮物。"""
    child = get_current_child()
    assert child is not None
    today = today_local(_tz())

    assignments = assignment_service.ensure_assignments_for_date(child.id, today)
    progress = assignment_service.get_daily_progress(child.id, today)
    balance = point_service.get_balance(child.id)
    card = point_service.get_card_progress(child.id, _points_per_card())
    streak = assignment_service.get_streak(child.id, today)

    # 解鎖新成就（會順便產生通知），再一次取出所有未讀通知播放動畫。
    achievement_service.check_and_unlock(child.id, today)
    notifications = notification_service.pop_unread(child.id)

    # 下一個禮物：優先顯示已經換得起的，否則顯示最接近的。
    rewards = reward_service.list_rewards(only_active=True)
    affordable = [r for r in rewards if r.in_stock and r.points_required <= balance]
    upcoming = [r for r in rewards if r.in_stock and r.points_required > balance]
    next_reward = (
        max(affordable, key=lambda r: r.points_required)
        if affordable
        else (min(upcoming, key=lambda r: r.points_required) if upcoming else None)
    )

    return render_template(
        "child/dashboard.html",
        child=child,
        today=today,
        assignments=assignments,
        progress=progress,
        balance=balance,
        card=card,
        streak=streak,
        notifications=notifications,
        next_reward=next_reward,
        form=ConfirmForm(),
        status_labels=ASSIGNMENT_STATUS_LABELS,
        AssignmentStatus=AssignmentStatus,
    )


@child_bp.route("/tasks/<int:assignment_id>/submit", methods=["POST"])
@child_required
def submit_task(assignment_id: int):  # noqa: ANN201
    """小孩按下「我完成了！」。採 PRG 避免重新整理重複送出。"""
    child = get_current_child()
    assert child is not None

    form = ConfirmForm()
    if not form.validate_on_submit():
        flash("哎呀，好像卡住了一下 😵　再試一次看看吧！", "error")
        return redirect(url_for("child.dashboard"))

    try:
        assignment_service.submit_assignment(assignment_id, child)
        flash(
            "收到啦！🎉　等爸爸媽媽確認完成後，星星就會跑進你的集點卡！",
            "success",
        )
    except AppError as exc:
        flash(exc.message, "error")

    return redirect(url_for("child.dashboard"))


@child_bp.route("/calendar")
@child_required
def calendar():  # noqa: ANN201
    """行事曆（月視圖）。"""
    child = get_current_child()
    assert child is not None
    today = today_local(_tz())

    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
        if not (1 <= month <= 12) or not (2000 <= year <= 2100):
            raise ValueError
    except (TypeError, ValueError):
        year, month = today.year, today.month

    return render_template(
        "child/calendar.html", child=child, year=year, month=month, today=today
    )


@child_bp.route("/calendar/<day>")
@child_required
def calendar_day(day: str):  # noqa: ANN201
    """某一天的任務明細。"""
    child = get_current_child()
    assert child is not None

    try:
        target = date.fromisoformat(day)
    except ValueError:
        flash("日期格式不太對喔。", "error")
        return redirect(url_for("child.calendar"))

    assignments = calendar_service.get_day_detail(child.id, target)
    earned = sum(a.earned_points for a in assignments)

    return render_template(
        "child/calendar_day.html",
        child=child,
        target=target,
        assignments=assignments,
        earned=earned,
        AssignmentStatus=AssignmentStatus,
    )


@child_bp.route("/rewards")
@child_required
def rewards():  # noqa: ANN201
    """禮物櫃。"""
    child = get_current_child()
    assert child is not None

    balance = point_service.get_balance(child.id)
    all_rewards = reward_service.list_rewards(only_active=True)
    pending_ids = redemption_service.get_pending_reward_ids(child.id)
    my_redemptions = redemption_service.list_redemptions_for_child(child.id, limit=20)

    return render_template(
        "child/rewards.html",
        child=child,
        balance=balance,
        rewards=all_rewards,
        pending_ids=pending_ids,
        redemptions=my_redemptions,
        form=ConfirmForm(),
    )


@child_bp.route("/rewards/<int:reward_id>/request", methods=["POST"])
@child_required
def request_reward(reward_id: int):  # noqa: ANN201
    """小孩申請兌換禮物。此時不扣點，等家長確認。"""
    child = get_current_child()
    assert child is not None

    form = ConfirmForm()
    if not form.validate_on_submit():
        flash("哎呀，好像卡住了一下 😵　再試一次看看吧！", "error")
        return redirect(url_for("child.rewards"))

    try:
        redemption_service.request_redemption(child, reward_id)
        flash("跟爸爸媽媽說好囉！等一下下就知道結果啦 🎁", "success")
    except AppError as exc:
        flash(exc.message, "error")

    return redirect(url_for("child.rewards"))


@child_bp.route("/history")
@child_required
def history():  # noqa: ANN201
    """我的紀錄：點數歷史與成就。"""
    child = get_current_child()
    assert child is not None

    transactions = point_service.list_transactions(child.id, limit=200)
    grouped = point_service.group_transactions_by_day(transactions, _tz())
    balance = point_service.get_balance(child.id)
    card = point_service.get_card_progress(child.id, _points_per_card())
    achievements = achievement_service.list_for_child(child.id)
    today = today_local(_tz())

    return render_template(
        "child/history.html",
        child=child,
        grouped=grouped,
        balance=balance,
        card=card,
        achievements=achievements,
        today=today,
    )
