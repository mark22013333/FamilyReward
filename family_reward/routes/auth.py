"""登入 / 登出。

Admin 走 Flask-Login，Child 走獨立的 session key，兩者完全分離。
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
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..forms import AdminLoginForm, ChildPinForm
from ..models import ActorType, AuditAction, Child
from ..security.auth import login_child, logout_child
from ..security.rate_limit import login_throttle
from ..services import admin_service, audit_service

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


def _safe_next(target: str | None) -> str | None:
    """只允許站內相對路徑，避免 open redirect。"""
    if not target:
        return None
    if target.startswith("/") and not target.startswith("//"):
        return target
    return None


@auth_bp.route("/login/child/<int:child_id>", methods=["GET", "POST"])
def child_login(child_id: int):  # noqa: ANN201
    """小孩以 4 位 PIN 登入。"""
    child = db.session.get(Child, child_id)
    if child is None or not child.active:
        flash("找不到這位小朋友耶 🐰", "error")
        return redirect(url_for("public.index"))

    settings = current_app.settings  # type: ignore[attr-defined]
    form = ChildPinForm()
    throttle_key = f"child:{child.id}"

    if login_throttle.is_locked(throttle_key):
        seconds = login_throttle.seconds_remaining(throttle_key)
        flash(f"密碼試太多次囉，休息 {seconds} 秒再試一次 😴", "error")
        return render_template(
            "auth/child_login.html", child=child, form=form, locked=True
        )

    if form.validate_on_submit():
        pin = form.pin.data or ""
        expected_length = settings.security.child_pin_length

        if len(pin) != expected_length:
            flash(f"請輸入 {expected_length} 個數字喔！", "error")
        elif child.verify_pin(pin):
            login_throttle.record_success(throttle_key)
            login_child(child)
            audit_service.record(
                AuditAction.LOGIN_SUCCESS,
                actor_type=ActorType.CHILD,
                actor_id=child.id,
                actor_name=child.name,
                entity_type="CHILD",
                entity_id=child.id,
                description=f"{child.name} 登入成功",
            )
            db.session.commit()
            destination = _safe_next(request.args.get("next"))
            return redirect(destination or url_for("child.dashboard"))
        else:
            locked = login_throttle.record_failure(throttle_key)
            # 注意：絕不記錄嘗試的 PIN 內容。
            audit_service.record(
                AuditAction.LOGIN_FAILURE,
                actor_type=ActorType.CHILD,
                actor_id=child.id,
                actor_name=child.name,
                entity_type="CHILD",
                entity_id=child.id,
                description=f"{child.name} PIN 輸入錯誤",
            )
            db.session.commit()
            logger.warning("Child login failure: child_id=%s", child.id)
            if locked:
                flash("密碼試太多次囉，休息一下再試試看 😴", "error")
            else:
                flash("數字好像不太對喔，再試一次！", "error")

    return render_template("auth/child_login.html", child=child, form=form, locked=False)


@auth_bp.route("/logout/child", methods=["POST"])
def child_logout():  # noqa: ANN201
    logout_child()
    flash("掰掰！明天見 👋", "success")
    return redirect(url_for("public.index"))


@auth_bp.route("/login/admin", methods=["GET", "POST"])
def admin_login():  # noqa: ANN201
    """家長後台登入。"""
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    form = AdminLoginForm()

    if form.validate_on_submit():
        username = (form.username.data or "").strip()
        throttle_key = f"admin:{username.lower()}"

        if login_throttle.is_locked(throttle_key):
            seconds = login_throttle.seconds_remaining(throttle_key)
            flash(f"登入失敗次數過多，請等待 {seconds} 秒後再試。", "error")
            return render_template("auth/admin_login.html", form=form)

        admin = admin_service.get_by_username(username)
        if admin and admin.active and admin.verify_password(form.password.data or ""):
            login_throttle.record_success(throttle_key)
            login_user(admin, remember=False)
            admin_service.record_login(admin)
            destination = _safe_next(request.args.get("next"))
            return redirect(destination or url_for("admin.dashboard"))

        login_throttle.record_failure(throttle_key)
        admin_service.record_login_failure(username)
        logger.warning("Admin login failure for username=%s", username)
        # 刻意不區分「帳號不存在」與「密碼錯誤」，避免帳號列舉。
        flash("帳號或密碼不正確。", "error")

    return render_template("auth/admin_login.html", form=form)


@auth_bp.route("/logout/admin", methods=["POST"])
@login_required
def admin_logout():  # noqa: ANN201
    audit_service.record(
        AuditAction.LOGOUT,
        actor_type=ActorType.ADMIN,
        actor_id=current_user.id,
        actor_name=current_user.username,
        entity_type="ADMIN_USER",
        entity_id=current_user.id,
        description=f"管理者「{current_user.username}」登出",
    )
    db.session.commit()
    logout_user()
    flash("已經登出囉。", "success")
    return redirect(url_for("public.index"))
