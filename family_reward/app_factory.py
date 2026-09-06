"""Flask App Factory。

所有初始化都集中在這裡，app.py 保持很薄。
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import PROJECT_ROOT, Settings, load_settings
from .database import enable_wal, register_sqlite_pragmas, verify_database_writable
from .extensions import csrf, db, login_manager, migrate
from .security.headers import register_security_headers
from .security.rate_limit import login_throttle
from .utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def create_app(
    config_path: str | Path | None = None,
    settings: Settings | None = None,
    *,
    setup_log: bool = True,
) -> Flask:
    """建立並設定 Flask 應用程式。

    Args:
        config_path: config.yaml 的路徑；None 代表使用預設位置。
        settings: 直接注入設定（測試用），會略過 config.yaml。
        setup_log: 是否設定檔案 log；測試時可關閉。
    """
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
        static_folder=str(PROJECT_ROOT / "static"),
    )

    settings = settings or load_settings(config_path)
    app.settings = settings  # type: ignore[attr-defined]

    if setup_log:
        setup_logging(
            settings.logging.path,
            level=settings.logging.level,
            max_bytes=settings.logging.max_bytes,
            backup_count=settings.logging.backup_count,
        )

    _configure_flask(app, settings)
    _configure_database(app, settings)
    _configure_extensions(app)
    _configure_jinja(app, settings)
    _register_blueprints(app)
    _register_error_handlers(app)
    register_security_headers(app)

    login_throttle.max_attempts = settings.security.max_login_attempts
    login_throttle.lockout_minutes = settings.security.lockout_minutes

    @app.route("/health")
    def health():  # noqa: ANN202
        """健康檢查。刻意不回傳資料庫路徑、Python 版本等內部資訊。"""
        return jsonify({"status": "UP"})

    logger.info(
        "Application initialized successfully (env=%s, db=%s)",
        settings.app.env,
        settings.database.path.name,
    )
    return app


def _configure_flask(app: Flask, settings: Settings) -> None:
    secret_key = settings.secret_key
    if not secret_key:
        # 開發 / 測試環境允許臨時金鑰；正式環境已在 validate_settings 擋下。
        secret_key = secrets.token_urlsafe(32)
        logger.warning("未設定 FLASK_SECRET_KEY，本次啟動使用臨時金鑰（重啟後 session 會失效）。")

    app.config.update(
        SECRET_KEY=secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # 本機以 http://127.0.0.1 使用，因此只有正式環境才要求 Secure，
        # 由 Cloudflare Tunnel 提供 HTTPS。
        SESSION_COOKIE_SECURE=settings.is_production and settings.cloudflare.enabled,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=settings.security.session_timeout_hours),
        WTF_CSRF_TIME_LIMIT=None,
        JSON_AS_ASCII=False,
        APP_NAME=settings.app.name,
        TIMEZONE=settings.app.timezone,
        POINTS_PER_CARD=settings.reward.points_per_card,
        DEBUG=settings.app.debug and not settings.is_production,
        SEND_FILE_MAX_AGE_DEFAULT=(
            timedelta(days=7) if settings.is_production else timedelta(seconds=0)
        ),
    )

    # Cloudflare Tunnel 會經過一層 Proxy，需要正確解析 X-Forwarded-*，
    # 但只信任 1 hop，不盲目相信任意 Proxy Header。
    if settings.cloudflare.enabled:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=0)


def _configure_database(app: Flask, settings: Settings) -> None:
    register_sqlite_pragmas()

    is_memory = str(settings.database.path) == ":memory:"
    if is_memory:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    else:
        verify_database_writable(settings.database.path)
        enable_wal(settings.database.path)
        app.config["SQLALCHEMY_DATABASE_URI"] = settings.sqlalchemy_uri

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}


def _configure_extensions(app: Flask) -> None:
    from . import models  # noqa: F401  確保 Alembic 能偵測到所有 Model

    db.init_app(app)
    # SQLite 不支援大部分的 ALTER TABLE，render_as_batch 讓 Alembic
    # 以「建新表 → 搬資料 → 換名」的方式處理欄位變更。
    migrate.init_app(
        app,
        db,
        directory=str(PROJECT_ROOT / "migrations"),
        render_as_batch=True,
    )
    csrf.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.admin_login"
    login_manager.login_message = "請先使用家長帳號登入 🔐"
    login_manager.login_message_category = "info"
    login_manager.session_protection = "strong"

    from .models import AdminUser

    @login_manager.user_loader
    def load_admin(user_id: str):  # noqa: ANN202
        admin = db.session.get(AdminUser, int(user_id))
        return admin if admin and admin.active else None


def _configure_jinja(app: Flask, settings: Settings) -> None:
    """註冊模板中會用到的過濾器與全域變數。"""
    from .models import (
        ASSIGNMENT_STATUS_LABELS,
        REDEMPTION_STATUS_LABELS,
        REPEAT_TYPE_LABELS,
        TASK_CATEGORY_LABELS,
        THEME_LABELS,
    )
    from .security.auth import get_current_child, is_admin_logged_in
    from .utils.timezone import (
        format_date_friendly,
        format_local_datetime,
        format_local_time,
        today_local,
    )

    tz = settings.app.timezone

    app.jinja_env.filters["local_time"] = lambda value: format_local_time(value, tz)
    app.jinja_env.filters["local_datetime"] = lambda value: format_local_datetime(value, tz)
    app.jinja_env.filters["friendly_date"] = format_date_friendly

    @app.context_processor
    def inject_globals():  # noqa: ANN202
        return {
            "app_name": settings.app.name,
            "points_per_card": settings.reward.points_per_card,
            "today": today_local(tz),
            "current_child": get_current_child(),
            "admin_logged_in": is_admin_logged_in(),
            "category_labels": TASK_CATEGORY_LABELS,
            "status_labels": ASSIGNMENT_STATUS_LABELS,
            "redemption_status_labels": REDEMPTION_STATUS_LABELS,
            "repeat_labels": REPEAT_TYPE_LABELS,
            "theme_labels": THEME_LABELS,
            "sound_enabled": settings.ui.sound_enabled,
        }


def _register_blueprints(app: Flask) -> None:
    from .routes.admin import admin_bp
    from .routes.api import api_bp
    from .routes.auth import auth_bp
    from .routes.child import child_bp
    from .routes.public import public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(child_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)


def _register_error_handlers(app: Flask) -> None:
    from .exceptions import AppError

    @app.errorhandler(403)
    def forbidden(error):  # noqa: ANN202
        return render_template("error/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):  # noqa: ANN202
        return render_template("error/404.html"), 404

    @app.errorhandler(500)
    @app.errorhandler(Exception)
    def internal_error(error):  # noqa: ANN202
        # HTTPException（例如 405）維持原本行為。
        from werkzeug.exceptions import HTTPException

        if isinstance(error, HTTPException):
            return error

        # 商業邏輯例外不算系統錯誤，仍以友善頁面呈現。
        if isinstance(error, AppError):
            logger.warning("Business rule rejected: %s", error.message)
            return render_template("error/500.html", message=error.message), 400

        # 技術細節只寫進 Log，畫面上絕不顯示 Traceback / SQL / 路徑。
        logger.exception("Unhandled exception: %s", error)
        db.session.rollback()
        return render_template("error/500.html"), 500
