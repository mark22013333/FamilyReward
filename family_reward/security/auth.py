"""登入與權限控制。

Admin 與 Child 的身分刻意分開處理，避免權限混淆：

* Admin 使用 Flask-Login（`current_user`），session key 由 Flask-Login 管理。
* Child 使用獨立的 session key `child_id`，不進 Flask-Login。

因此小孩永遠不可能因為 session 混用而取得 Admin 權限。
"""

from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar

from flask import abort, flash, g, redirect, request, session, url_for
from flask_login import current_user

from ..extensions import db, login_manager
from ..models import Child

CHILD_SESSION_KEY = "child_id"
F = TypeVar("F", bound=Callable[..., object])


def login_child(child: Child) -> None:
    """建立小孩的登入 session。

    這裡刻意也寫入 Flask-Login 的 `_id`（session identifier）。
    原因：Admin 與 Child 共用同一個 cookie，若只有 child_id 而沒有 `_id`，
    Flask-Login 的 session protection 會在每個 request 判定「識別碼不符」，
    把 session 標記為 non-fresh 甚至清空，導致小孩剛登入就被登出。
    """
    # 換人使用時清掉前一個身分的殘留，但保留 CSRF token，
    # 否則接下來的表單會因為 token 不見而全部失效。
    csrf_token = session.get("csrf_token")
    session.clear()
    if csrf_token:
        session["csrf_token"] = csrf_token

    session[CHILD_SESSION_KEY] = child.id
    session["_id"] = login_manager._session_identifier_generator()
    session["_fresh"] = True
    session.permanent = True
    g.pop("current_child", None)


def logout_child() -> None:
    session.pop(CHILD_SESSION_KEY, None)
    g.pop("current_child", None)


def get_current_child() -> Child | None:
    """取得目前登入的小孩；已停用的小孩會自動登出。"""
    if "current_child" in g:
        return g.current_child

    child_id = session.get(CHILD_SESSION_KEY)
    child: Child | None = None
    if child_id is not None:
        child = db.session.get(Child, child_id)
        if child is not None and not child.active:
            child = None
            session.pop(CHILD_SESSION_KEY, None)

    g.current_child = child
    return child


def is_admin_logged_in() -> bool:
    return bool(current_user.is_authenticated)


def child_required(view: F) -> F:
    """小孩頁面專用：沒登入就導回選擇小孩的首頁。"""

    @wraps(view)
    def wrapper(*args, **kwargs):
        child = get_current_child()
        if child is None:
            flash("先選一下今天是誰要開始冒險吧！🌈", "info")
            return redirect(url_for("public.index", next=request.path))
        return view(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def admin_required(view: F) -> F:
    """Admin 頁面專用。

    小孩即使手動輸入 /admin 也只會被導向管理者登入頁，
    絕不會因為畫面上沒有按鈕就以為安全。
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_admin_logged_in():
            return redirect(url_for("auth.admin_login", next=request.path))
        return view(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def ensure_child_owns(child_id: int) -> None:
    """物件層級授權：確認資料屬於目前登入的小孩。

    小孩手動改 URL 想看別人的資料時，這裡會直接回 403。
    """
    child = get_current_child()
    if child is None or child.id != child_id:
        abort(403)
