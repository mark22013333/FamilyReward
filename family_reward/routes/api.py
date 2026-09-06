"""JSON API。

只提供前端真正需要非同步取得的資料（目前是行事曆）。
其餘操作都用一般 HTML Form + PRG，不為了 RESTful 而 RESTful。

授權規則：
* Child 只能看自己的資料，child_id 一律取自 session，不信任 query string。
* 只有 Admin 才能指定 child_id 查看任何小孩的資料。
"""

from __future__ import annotations

from flask import Blueprint, abort, current_app, jsonify, request

from ..security.auth import get_current_child, is_admin_logged_in
from ..services import calendar_service
from ..utils.timezone import today_local

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _resolve_child_id() -> int:
    """決定要查詢哪個小孩，並完成授權檢查。"""
    child = get_current_child()
    if child is not None:
        # 小孩登入時完全忽略 query string 的 child_id。
        return child.id

    if is_admin_logged_in():
        raw = request.args.get("child_id")
        if not raw:
            abort(400)
        try:
            return int(raw)
        except (TypeError, ValueError):
            abort(400)

    abort(403)


@api_bp.route("/calendar")
def calendar():  # noqa: ANN201
    """回傳某個月每一天的任務統計。

    GET /api/calendar?year=2026&month=9
    """
    child_id = _resolve_child_id()
    today = today_local(current_app.settings.app.timezone)  # type: ignore[attr-defined]

    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
    except (TypeError, ValueError):
        abort(400)

    if not (1 <= month <= 12) or not (2000 <= year <= 2100):
        abort(400)

    summaries = calendar_service.get_month_summary(child_id, year, month)
    return jsonify([summary.to_dict() for summary in summaries])
