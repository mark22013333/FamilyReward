"""pytest 共用 fixture。

測試一律使用暫存的 SQLite 檔案，絕不碰正式的 data/family-reward.db。
每個測試都會拿到一個乾淨的資料庫。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from family_reward import create_app
from family_reward.config import (
    AdminConfig,
    AppConfig,
    BackupConfig,
    DatabaseConfig,
    LoggingConfig,
    RewardConfig,
    SecurityConfig,
    ServerConfig,
    Settings,
)
from family_reward.extensions import db as _db
from family_reward.models import (
    Child,
    RepeatType,
    Reward,
    Task,
    TaskAssignee,
    TaskCategory,
)
from family_reward.security.rate_limit import login_throttle
from family_reward.services import achievement_service, admin_service

ADMIN_USERNAME = "testadmin"
ADMIN_PASSWORD = "testpassword123"
CHILD_PIN = "1234"


@pytest.fixture()
def tmp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def settings(tmp_db_path: Path, tmp_path: Path) -> Settings:
    """測試用設定：獨立 DB、獨立 log、獨立 backup 目錄。"""
    return Settings(
        server=ServerConfig(host="127.0.0.1", port=8080, threads=2),
        app=AppConfig(
            name="測試集點樂園", timezone="Asia/Taipei", debug=False, env="testing"
        ),
        database=DatabaseConfig(path=tmp_db_path),
        reward=RewardConfig(points_per_card=10, allow_negative_balance=False),
        security=SecurityConfig(
            session_timeout_hours=12,
            child_pin_length=4,
            max_login_attempts=5,
            lockout_minutes=5,
        ),
        admin=AdminConfig(initial_username=ADMIN_USERNAME),
        logging=LoggingConfig(path=tmp_path / "test.log"),
        backup=BackupConfig(directory=tmp_path / "backup", reminder_days=7),
        secret_key="test-secret-key-not-for-production",
        admin_initial_password=ADMIN_PASSWORD,
    )


@pytest.fixture()
def app(settings: Settings):  # noqa: ANN201
    """建立測試用的 Flask app，並建好所有資料表。"""
    application = create_app(settings=settings, setup_log=False)
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with application.app_context():
        _db.create_all()
        admin_service.ensure_initial_admin(ADMIN_USERNAME, ADMIN_PASSWORD)
        achievement_service.ensure_definitions()

    login_throttle.reset()

    yield application

    with application.app_context():
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app):  # noqa: ANN201
    """在 app context 中提供 db，方便直接操作 Model。"""
    with app.app_context():
        yield _db


@pytest.fixture()
def client(app):  # noqa: ANN201
    return app.test_client()


@pytest.fixture()
def admin_user(db):  # noqa: ANN201
    return admin_service.get_by_username(ADMIN_USERNAME)


@pytest.fixture()
def child(db) -> Child:
    """建立一位測試小孩。"""
    item = Child(name="小明", avatar="🐼", theme="SUNNY", active=True)
    item.set_pin(CHILD_PIN)
    db.session.add(item)
    db.session.commit()
    return item


@pytest.fixture()
def other_child(db) -> Child:
    """第二位小孩，用來驗證跨小孩的權限隔離。"""
    item = Child(name="小美", avatar="🦄", theme="CANDY", active=True)
    item.set_pin("5678")
    db.session.add(item)
    db.session.commit()
    return item


@pytest.fixture()
def task(db, child: Child) -> Task:
    """建立一個每日任務「整理玩具 +2」並指派給 child。"""
    item = Task(
        title="整理玩具",
        icon="🧸",
        points=2,
        category=TaskCategory.HOUSEWORK.value,
        repeat_type=RepeatType.DAILY.value,
        required=True,
        active=True,
    )
    db.session.add(item)
    db.session.flush()
    db.session.add(TaskAssignee(task_id=item.id, child_id=child.id))
    db.session.commit()
    return item


@pytest.fixture()
def reward(db) -> Reward:
    """建立「吃冰淇淋 10 點」（無限量）。"""
    item = Reward(name="吃冰淇淋", icon="🍦", points_required=10, quantity=None, active=True)
    db.session.add(item)
    db.session.commit()
    return item


@pytest.fixture()
def today() -> date:
    from family_reward.utils.timezone import today_local

    return today_local("Asia/Taipei")


# --------------------------------------------------------------------------
# 測試小工具
# --------------------------------------------------------------------------


@pytest.fixture()
def login_admin(client):  # noqa: ANN201
    """以管理者身分登入 test client。"""

    def _login(username: str = ADMIN_USERNAME, password: str = ADMIN_PASSWORD):
        return client.post(
            "/login/admin",
            data={"username": username, "password": password},
            follow_redirects=True,
        )

    return _login


@pytest.fixture()
def login_child(client):  # noqa: ANN201
    """以小孩身分登入 test client。"""

    def _login(child_id: int, pin: str = CHILD_PIN):
        return client.post(
            f"/login/child/{child_id}",
            data={"pin": pin},
            follow_redirects=True,
        )

    return _login


@pytest.fixture()
def make_assignment(db):  # noqa: ANN201
    """快速建立一筆指定狀態的 TaskAssignment。"""
    from family_reward.models import AssignmentStatus, TaskAssignment
    from family_reward.utils.timezone import utcnow

    def _make(
        task: Task,
        child: Child,
        on: date,
        status: str = AssignmentStatus.TODO.value,
    ) -> TaskAssignment:
        assignment = TaskAssignment(
            task_id=task.id,
            child_id=child.id,
            assignment_date=on,
            task_title_snapshot=task.title,
            task_icon_snapshot=task.icon,
            points_snapshot=task.points,
            required_snapshot=task.required,
            status=status,
            submitted_at=utcnow()
            if status
            in (AssignmentStatus.WAITING_APPROVAL.value, AssignmentStatus.APPROVED.value)
            else None,
        )
        db.session.add(assignment)
        db.session.commit()
        return assignment

    return _make
