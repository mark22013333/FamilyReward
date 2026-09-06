"""公開頁面：選擇小孩。"""

from __future__ import annotations

from flask import Blueprint, render_template

from ..services import child_service

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():  # noqa: ANN201
    """首頁：今天是誰要開始冒險呢？"""
    children = child_service.list_children(only_active=True)
    return render_template("public/index.html", children=children)
