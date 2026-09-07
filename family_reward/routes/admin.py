"""家長後台。

所有頁面都以 @admin_required 保護；
小孩即使手動輸入 /admin 也只會被導向管理者登入頁。
"""

from __future__ import annotations

import logging

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from ..exceptions import AppError
from ..forms import (
    ChangePasswordForm,
    ChangeUsernameForm,
    ChildForm,
    ConfirmForm,
    PointAdjustmentForm,
    PointsPerCardForm,
    RejectForm,
    RewardForm,
    TaskForm,
)
from ..models import ActorType, AuditAction, RepeatType
from ..security.auth import admin_required
from ..services import (
    admin_service,
    assignment_service,
    audit_service,
    backup_service,
    child_service,
    point_service,
    redemption_service,
    reward_service,
    settings_service,
    task_service,
)
from ..utils.timezone import today_local

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _settings():  # noqa: ANN202
    return current_app.settings  # type: ignore[attr-defined]


def _tz() -> str:
    return _settings().app.timezone


@admin_bp.before_request
@admin_required
def _require_admin():  # noqa: ANN202
    """整個 blueprint 統一要求管理者身分。"""
    return None


@admin_bp.context_processor
def _inject_badges():  # noqa: ANN202
    """導覽列上的待辦數字。"""
    return {
        "pending_task_count": assignment_service.count_pending_approvals(),
        "pending_reward_count": redemption_service.count_pending_redemptions(),
        "must_change_password": bool(
            getattr(current_user, "must_change_password", False)
        ),
    }


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------


@admin_bp.route("/")
def dashboard():  # noqa: ANN201
    today = today_local(_tz())
    children = child_service.list_children(only_active=True)

    # 一次查出所有餘額，避免 N+1。
    balances = point_service.get_balances_for_children([c.id for c in children])
    rows = [
        {
            "child": child,
            "progress": assignment_service.get_daily_progress(child.id, today),
            "balance": balances.get(child.id, 0),
        }
        for child in children
    ]

    settings = _settings()
    latest_backup = backup_service.get_latest_backup(settings.backup.directory)
    days_since = backup_service.days_since_last_backup(settings.backup.directory)
    backup_overdue = days_since is None or days_since >= settings.backup.reminder_days

    return render_template(
        "admin/dashboard.html",
        today=today,
        rows=rows,
        latest_backup=latest_backup,
        days_since_backup=days_since,
        backup_overdue=backup_overdue,
        reminder_days=settings.backup.reminder_days,
        form=ConfirmForm(),
    )


# --------------------------------------------------------------------------
# 待確認
# --------------------------------------------------------------------------


@admin_bp.route("/approvals")
def approvals():  # noqa: ANN201
    return render_template(
        "admin/approvals.html",
        assignments=assignment_service.list_pending_approvals(),
        form=ConfirmForm(),
        reject_form=RejectForm(),
    )


@admin_bp.route("/assignments/<int:assignment_id>/approve", methods=["POST"])
def approve_assignment(assignment_id: int):  # noqa: ANN201
    form = ConfirmForm()
    if not form.validate_on_submit():
        flash("操作沒有成功，請再試一次。", "error")
        return redirect(url_for("admin.approvals"))

    try:
        assignment = assignment_service.approve_assignment(
            assignment_id, current_user.id, current_user.username
        )
        flash(
            f"✅ 已確認完成「{assignment.task_title_snapshot}」"
            f"+{assignment.earned_points} ⭐",
            "success",
        )
    except AppError as exc:
        flash(exc.message, "error")

    return redirect(url_for("admin.approvals"))


@admin_bp.route("/assignments/<int:assignment_id>/reject", methods=["POST"])
def reject_assignment(assignment_id: int):  # noqa: ANN201
    form = RejectForm()
    if not form.validate_on_submit():
        flash("操作沒有成功，請再試一次。", "error")
        return redirect(url_for("admin.approvals"))

    try:
        assignment_service.reject_assignment(
            assignment_id,
            current_user.id,
            form.reason.data or "",
            current_user.username,
        )
        flash("已經把任務退回，並留了一句鼓勵給小朋友 💪", "success")
    except AppError as exc:
        flash(exc.message, "error")

    return redirect(url_for("admin.approvals"))


# --------------------------------------------------------------------------
# 小孩管理
# --------------------------------------------------------------------------


@admin_bp.route("/children")
def children():  # noqa: ANN201
    all_children = child_service.list_children(only_active=False)
    balances = point_service.get_balances_for_children([c.id for c in all_children])
    return render_template(
        "admin/children.html",
        children=all_children,
        balances=balances,
        form=ConfirmForm(),
    )


@admin_bp.route("/children/new", methods=["GET", "POST"])
def create_child():  # noqa: ANN201
    form = ChildForm()
    pin_length = _settings().security.child_pin_length

    if form.validate_on_submit():
        try:
            if not form.pin.data:
                raise AppError(f"請設定 {pin_length} 位數的 PIN。")
            child = child_service.create_child(
                name=form.name.data or "",
                pin=form.pin.data,
                nickname=form.nickname.data,
                avatar=form.avatar.data or "🐼",
                theme=form.theme.data or "SUNNY",
                birthday=form.birthday.data,
                pin_length=pin_length,
                admin_id=current_user.id,
                admin_name=current_user.username,
            )
            flash(f"已經建立「{child.avatar} {child.name}」囉！", "success")
            return redirect(url_for("admin.children"))
        except AppError as exc:
            flash(exc.message, "error")

    return render_template(
        "admin/child_form.html", form=form, child=None, pin_length=pin_length
    )


@admin_bp.route("/children/<int:child_id>/edit", methods=["GET", "POST"])
def edit_child(child_id: int):  # noqa: ANN201
    child = child_service.get_child(child_id)
    form = ChildForm(obj=child)
    pin_length = _settings().security.child_pin_length

    if form.validate_on_submit():
        try:
            child_service.update_child(
                child_id,
                name=form.name.data or "",
                nickname=form.nickname.data,
                avatar=form.avatar.data or "🐼",
                theme=form.theme.data or "SUNNY",
                birthday=form.birthday.data,
                active=bool(form.active.data),
                pin=form.pin.data or None,
                pin_length=pin_length,
                admin_id=current_user.id,
                admin_name=current_user.username,
            )
            flash("資料已經更新囉！", "success")
            return redirect(url_for("admin.children"))
        except AppError as exc:
            flash(exc.message, "error")

    if request.method == "GET":
        form.pin.data = ""  # 不把既有 PIN 帶回畫面（本來就只有 hash）

    return render_template(
        "admin/child_form.html", form=form, child=child, pin_length=pin_length
    )


@admin_bp.route("/children/<int:child_id>/deactivate", methods=["POST"])
def deactivate_child(child_id: int):  # noqa: ANN201
    form = ConfirmForm()
    if not form.validate_on_submit():
        flash("操作沒有成功，請再試一次。", "error")
        return redirect(url_for("admin.children"))

    try:
        child = child_service.deactivate_child(
            child_id, admin_id=current_user.id, admin_name=current_user.username
        )
        flash(f"已經停用「{child.name}」，歷史紀錄仍然保留。", "success")
    except AppError as exc:
        flash(exc.message, "error")

    return redirect(url_for("admin.children"))


# --------------------------------------------------------------------------
# 任務管理
# --------------------------------------------------------------------------


def _prepare_task_form(form: TaskForm) -> None:
    """填入可指派的小孩清單。"""
    form.child_ids.choices = [
        (child.id, f"{child.avatar} {child.name}")
        for child in child_service.list_children(only_active=True)
    ]


@admin_bp.route("/tasks")
def tasks():  # noqa: ANN201
    return render_template(
        "admin/tasks.html",
        tasks=task_service.list_tasks(only_active=False),
        form=ConfirmForm(),
        RepeatType=RepeatType,
    )


@admin_bp.route("/tasks/new", methods=["GET", "POST"])
def create_task():  # noqa: ANN201
    form = TaskForm()
    _prepare_task_form(form)

    if form.validate_on_submit():
        try:
            task = task_service.create_task(
                title=form.title.data or "",
                points=int(form.points.data or 1),
                child_ids=list(form.child_ids.data or []),
                icon=form.icon.data or "⭐",
                description=form.description.data,
                category=form.category.data or "OTHER",
                repeat_type=form.repeat_type.data or "DAILY",
                weekdays=list(form.weekdays.data or []),
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                required=bool(form.required.data),
                admin_id=current_user.id,
                admin_name=current_user.username,
            )
            flash(f"已經建立任務「{task.icon} {task.title}」囉！", "success")
            return redirect(url_for("admin.tasks"))
        except AppError as exc:
            flash(exc.message, "error")

    return render_template("admin/task_form.html", form=form, task=None)


@admin_bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id: int):  # noqa: ANN201
    task = task_service.get_task(task_id)
    form = TaskForm(obj=task)
    _prepare_task_form(form)

    if request.method == "GET":
        form.weekdays.data = [schedule.weekday for schedule in task.schedules]
        form.child_ids.data = [assignee.child_id for assignee in task.assignees]

    if form.validate_on_submit():
        try:
            task_service.update_task(
                task_id,
                title=form.title.data or "",
                points=int(form.points.data or 1),
                child_ids=list(form.child_ids.data or []),
                icon=form.icon.data or "⭐",
                description=form.description.data,
                category=form.category.data or "OTHER",
                repeat_type=form.repeat_type.data or "DAILY",
                weekdays=list(form.weekdays.data or []),
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                required=bool(form.required.data),
                active=bool(form.active.data),
                admin_id=current_user.id,
                admin_name=current_user.username,
            )
            flash("任務已經更新囉！", "success")
            return redirect(url_for("admin.tasks"))
        except AppError as exc:
            flash(exc.message, "error")

    return render_template("admin/task_form.html", form=form, task=task)


@admin_bp.route("/tasks/<int:task_id>/deactivate", methods=["POST"])
def deactivate_task(task_id: int):  # noqa: ANN201
    form = ConfirmForm()
    if not form.validate_on_submit():
        flash("操作沒有成功，請再試一次。", "error")
        return redirect(url_for("admin.tasks"))

    try:
        task = task_service.deactivate_task(
            task_id, admin_id=current_user.id, admin_name=current_user.username
        )
        flash(f"已經停用任務「{task.title}」。", "success")
    except AppError as exc:
        flash(exc.message, "error")

    return redirect(url_for("admin.tasks"))


# --------------------------------------------------------------------------
# 禮物管理
# --------------------------------------------------------------------------


@admin_bp.route("/rewards")
def rewards():  # noqa: ANN201
    return render_template(
        "admin/rewards.html",
        rewards=reward_service.list_rewards(only_active=False),
        form=ConfirmForm(),
    )


@admin_bp.route("/rewards/new", methods=["GET", "POST"])
def create_reward():  # noqa: ANN201
    form = RewardForm()

    if form.validate_on_submit():
        try:
            reward = reward_service.create_reward(
                name=form.name.data or "",
                points_required=int(form.points_required.data or 1),
                icon=form.icon.data or "🎁",
                description=form.description.data,
                quantity=form.quantity.data,
                admin_id=current_user.id,
                admin_name=current_user.username,
            )
            flash(f"已經放入禮物「{reward.icon} {reward.name}」囉！", "success")
            return redirect(url_for("admin.rewards"))
        except AppError as exc:
            flash(exc.message, "error")

    return render_template("admin/reward_form.html", form=form, reward=None)


@admin_bp.route("/rewards/<int:reward_id>/edit", methods=["GET", "POST"])
def edit_reward(reward_id: int):  # noqa: ANN201
    reward = reward_service.get_reward(reward_id)
    form = RewardForm(obj=reward)

    if form.validate_on_submit():
        try:
            reward_service.update_reward(
                reward_id,
                name=form.name.data or "",
                points_required=int(form.points_required.data or 1),
                icon=form.icon.data or "🎁",
                description=form.description.data,
                quantity=form.quantity.data,
                active=bool(form.active.data),
                admin_id=current_user.id,
                admin_name=current_user.username,
            )
            flash("禮物已經更新囉！", "success")
            return redirect(url_for("admin.rewards"))
        except AppError as exc:
            flash(exc.message, "error")

    return render_template("admin/reward_form.html", form=form, reward=reward)


@admin_bp.route("/rewards/<int:reward_id>/deactivate", methods=["POST"])
def deactivate_reward(reward_id: int):  # noqa: ANN201
    form = ConfirmForm()
    if not form.validate_on_submit():
        flash("操作沒有成功，請再試一次。", "error")
        return redirect(url_for("admin.rewards"))

    try:
        reward = reward_service.deactivate_reward(
            reward_id, admin_id=current_user.id, admin_name=current_user.username
        )
        flash(f"已經收起禮物「{reward.name}」。", "success")
    except AppError as exc:
        flash(exc.message, "error")

    return redirect(url_for("admin.rewards"))


# --------------------------------------------------------------------------
# 兌換管理
# --------------------------------------------------------------------------


@admin_bp.route("/redemptions")
def redemptions():  # noqa: ANN201
    pending = redemption_service.list_pending_redemptions()
    balances = point_service.get_balances_for_children([r.child_id for r in pending])
    return render_template(
        "admin/redemptions.html",
        pending=pending,
        balances=balances,
        history=redemption_service.list_all_redemptions(limit=100),
        form=ConfirmForm(),
        reject_form=RejectForm(),
    )


@admin_bp.route("/redemptions/<int:redemption_id>/approve", methods=["POST"])
def approve_redemption(redemption_id: int):  # noqa: ANN201
    form = ConfirmForm()
    if not form.validate_on_submit():
        flash("操作沒有成功，請再試一次。", "error")
        return redirect(url_for("admin.redemptions"))

    try:
        redemption = redemption_service.approve_redemption(
            redemption_id, current_user.id, current_user.username
        )
        flash(
            f"🎁 已確認兌換「{redemption.reward_name_snapshot}」"
            f"-{redemption.points} ⭐",
            "success",
        )
    except AppError as exc:
        flash(exc.message, "error")

    return redirect(url_for("admin.redemptions"))


@admin_bp.route("/redemptions/<int:redemption_id>/reject", methods=["POST"])
def reject_redemption(redemption_id: int):  # noqa: ANN201
    form = RejectForm()
    if not form.validate_on_submit():
        flash("操作沒有成功，請再試一次。", "error")
        return redirect(url_for("admin.redemptions"))

    try:
        redemption_service.reject_redemption(
            redemption_id,
            current_user.id,
            form.reason.data or "",
            current_user.username,
        )
        flash("已經婉拒這次兌換，點數沒有被扣掉。", "success")
    except AppError as exc:
        flash(exc.message, "error")

    return redirect(url_for("admin.redemptions"))


@admin_bp.route("/redemptions/<int:redemption_id>/complete", methods=["POST"])
def complete_redemption(redemption_id: int):  # noqa: ANN201
    form = ConfirmForm()
    if not form.validate_on_submit():
        flash("操作沒有成功，請再試一次。", "error")
        return redirect(url_for("admin.redemptions"))

    try:
        redemption_service.complete_redemption(
            redemption_id, current_user.id, current_user.username
        )
        flash("已經標記為送達囉！", "success")
    except AppError as exc:
        flash(exc.message, "error")

    return redirect(url_for("admin.redemptions"))


# --------------------------------------------------------------------------
# 點數
# --------------------------------------------------------------------------


@admin_bp.route("/points", methods=["GET", "POST"])
def points():  # noqa: ANN201
    children = child_service.list_children(only_active=True)
    form = PointAdjustmentForm()
    form.child_id.choices = [
        (child.id, f"{child.avatar} {child.name}") for child in children
    ]

    if form.validate_on_submit():
        try:
            point_service.adjust_points(
                child_id=int(form.child_id.data),
                points=int(form.points.data or 0),
                reason=form.reason.data or "",
                admin_id=current_user.id,
                admin_name=current_user.username,
                allow_negative_balance=_settings().reward.allow_negative_balance,
            )
            flash("點數已經調整完成，並留下紀錄囉。", "success")
            return redirect(url_for("admin.points"))
        except AppError as exc:
            flash(exc.message, "error")

    balances = point_service.get_balances_for_children([c.id for c in children])
    # 讀一次就好，不要在迴圈裡重複查（比照 get_balances_for_children 的做法）。
    points_per_card = settings_service.get_points_per_card()
    summary = [
        {
            "child": child,
            "balance": balances.get(child.id, 0),
            "lifetime": point_service.get_lifetime_earned(child.id),
            "card": point_service.get_card_progress(child.id, points_per_card),
        }
        for child in children
    ]

    selected_id = request.args.get("child_id", type=int)
    transactions = (
        point_service.list_transactions(selected_id, limit=100) if selected_id else []
    )

    return render_template(
        "admin/points.html",
        form=form,
        summary=summary,
        children=children,
        selected_id=selected_id,
        transactions=transactions,
    )


# --------------------------------------------------------------------------
# 歷史紀錄
# --------------------------------------------------------------------------


@admin_bp.route("/history")
def history():  # noqa: ANN201
    return render_template("admin/history.html", logs=audit_service.list_recent(200))


# --------------------------------------------------------------------------
# 設定
# --------------------------------------------------------------------------


@admin_bp.route("/settings", methods=["GET", "POST"])
def settings_page():  # noqa: ANN201
    settings = _settings()

    # 這一頁有兩個表單（改帳號、改密碼）。用隱藏的 action 欄位區分，
    # 否則送出其中一個時，另一個會因為欄位空白而跳出誤導的錯誤訊息。
    action = request.form.get("action", "")

    username_form = ChangeUsernameForm()
    password_form = ChangePasswordForm()
    points_card_form = PointsPerCardForm()

    if action == "change_points_per_card" and points_card_form.validate_on_submit():
        try:
            new_value = int(points_card_form.points_per_card.data or 0)
            # 先算好影響，才能在成功訊息裡告訴家長實際結果。
            previews = settings_service.preview_points_per_card_change(new_value)
            settings_service.set_points_per_card(
                new_value,
                admin_id=current_user.id,
                admin_name=current_user.username,
            )
            effect = "、".join(
                f"{p.child_name} 完成 {p.after_cards} 張" for p in previews
            )
            flash(
                f"已改成 {new_value} 點一張集點卡。" + (effect if effect else ""),
                "success",
            )
            return redirect(url_for("admin.settings_page"))
        except AppError as exc:
            flash(exc.message, "error")

    if action == "change_username" and username_form.validate_on_submit():
        try:
            admin_service.change_username(
                current_user,
                username_form.new_username.data or "",
                username_form.current_password.data or "",
            )
            flash("帳號已經修改成功！下次請用新帳號登入 🔐", "success")
            return redirect(url_for("admin.settings_page"))
        except AppError as exc:
            flash(exc.message, "error")

    if action == "change_password" and password_form.validate_on_submit():
        try:
            admin_service.change_password(
                current_user,
                password_form.current_password.data or "",
                password_form.new_password.data or "",
                password_form.confirm_password.data or "",
            )
            flash("密碼已經修改成功！請記得牢記新密碼 🔐", "success")
            return redirect(url_for("admin.settings_page"))
        except AppError as exc:
            flash(exc.message, "error")

    backups = backup_service.list_backups(settings.backup.directory)

    current_points_per_card = settings_service.get_points_per_card()

    # GET（或其他表單送出失敗重新渲染）時預填目前的值；
    # 若是這個表單本身驗證失敗，保留家長剛才輸入的內容，錯誤訊息才對得上。
    if not points_card_form.is_submitted():
        points_card_form.points_per_card.data = current_points_per_card

    # 「改了會怎樣」的現狀資料。伺服器先算好，沒有 JS 也看得到。
    card_previews = settings_service.preview_points_per_card_change(
        current_points_per_card
    )

    return render_template(
        "admin/settings.html",
        username_form=username_form,
        password_form=password_form,
        points_card_form=points_card_form,
        current_points_per_card=current_points_per_card,
        card_previews=card_previews,
        points_per_card_min=settings_service.MIN_POINTS_PER_CARD,
        points_per_card_max=settings_service.MAX_POINTS_PER_CARD,
        confirm_form=ConfirmForm(),
        backups=backups[:20],
        settings=settings,
        cloudflare_hostname=settings.cloudflare.hostname,
        current_username=current_user.username,
    )


@admin_bp.route("/backup", methods=["POST"])
def create_backup():  # noqa: ANN201
    """立即備份資料庫（使用 SQLite Backup API）。"""
    form = ConfirmForm()
    if not form.validate_on_submit():
        flash("操作沒有成功，請再試一次。", "error")
        return redirect(url_for("admin.dashboard"))

    settings = _settings()
    try:
        target = backup_service.create_backup(
            settings.database.path,
            settings.backup.directory,
            tz_name=settings.app.timezone,
        )
        audit_service.record(
            AuditAction.BACKUP_DATABASE,
            actor_type=ActorType.ADMIN,
            actor_id=current_user.id,
            actor_name=current_user.username,
            entity_type="DATABASE",
            description=f"手動備份資料庫：{target.name}",
        )
        from ..extensions import db

        db.session.commit()
        flash(f"備份完成囉！檔案：{target.name}", "success")
    except (OSError, RuntimeError) as exc:
        logger.exception("Backup failed: %s", exc)
        flash("備份沒有成功，請查看 logs\\family-reward.log。", "error")

    return redirect(request.referrer or url_for("admin.dashboard"))
