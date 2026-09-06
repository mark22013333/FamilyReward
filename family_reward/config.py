"""設定載入與驗證。

所有會依環境改變的參數都放在 config/config.yaml，
敏感資訊（SECRET_KEY / 初始密碼）放在 .env。

路徑一律以「專案根目錄」為基準展開，不依賴目前的命令列工作目錄，
確保從桌面捷徑、BAT 或其他目錄啟動都能找到正確檔案。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


class ConfigError(Exception):
    """設定檔內容不合法時拋出，啟動流程應直接中止。"""


def _resolve(path_value: str) -> Path:
    """把設定檔中的相對路徑轉成以專案根目錄為基準的絕對路徑。"""
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    threads: int = 8


@dataclass
class AppConfig:
    name: str = "家庭任務集點樂園"
    timezone: str = "Asia/Taipei"
    debug: bool = False
    env: str = "production"


@dataclass
class DatabaseConfig:
    path: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "family-reward.db")


@dataclass
class RewardConfig:
    points_per_card: int = 10
    allow_negative_balance: bool = False


@dataclass
class SecurityConfig:
    session_timeout_hours: int = 12
    child_pin_length: int = 4
    max_login_attempts: int = 5
    lockout_minutes: int = 5


@dataclass
class AdminConfig:
    initial_username: str = "admin"


@dataclass
class CloudflareConfig:
    enabled: bool = False
    executable: Path = field(default_factory=lambda: PROJECT_ROOT / "cloudflare" / "cloudflared.exe")
    config: Path = field(default_factory=lambda: PROJECT_ROOT / "cloudflare" / "config.yml")
    hostname: str = ""


@dataclass
class LoggingConfig:
    path: Path = field(default_factory=lambda: PROJECT_ROOT / "logs" / "family-reward.log")
    level: str = "INFO"
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 5


@dataclass
class BackupConfig:
    directory: Path = field(default_factory=lambda: PROJECT_ROOT / "backup")
    reminder_days: int = 7


@dataclass
class UiConfig:
    sound_enabled: bool = False


@dataclass
class Settings:
    """整份應用程式設定。"""

    server: ServerConfig = field(default_factory=ServerConfig)
    app: AppConfig = field(default_factory=AppConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    reward: RewardConfig = field(default_factory=RewardConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    admin: AdminConfig = field(default_factory=AdminConfig)
    cloudflare: CloudflareConfig = field(default_factory=CloudflareConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    backup: BackupConfig = field(default_factory=BackupConfig)
    ui: UiConfig = field(default_factory=UiConfig)

    secret_key: str = ""
    admin_initial_password: str = ""
    source_path: Path | None = None

    @property
    def is_production(self) -> bool:
        return self.app.env.lower() == "production"

    @property
    def behind_proxy(self) -> bool:
        """這個服務是否會經由 Cloudflare Tunnel 對外提供。

        注意：不能只看 `cloudflare.enabled` —— 那個旗標的意思是
        「要不要由 start.bat 自己啟動 cloudflared」。如果使用者把 tunnel
        註冊成 Windows 服務（儀表板管理型），enabled 會是 false，
        但流量「仍然」經過 Cloudflare 的 proxy。

        因此只要設定了對外網域，就視為在 proxy 後面，
        才能正確處理 X-Forwarded-Proto 並啟用 Secure cookie。
        """
        return self.cloudflare.enabled or bool(self.cloudflare.hostname.strip())

    @property
    def sqlalchemy_uri(self) -> str:
        return "sqlite:///" + str(self.database.path).replace("\\", "/")


def _section(raw: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = raw.get(key) or {}
    if not isinstance(value, dict):
        raise ConfigError(f"config.yaml 的 `{key}` 區段格式錯誤，應為對應表（key: value）。")
    return value


def load_settings(config_path: str | Path | None = None) -> Settings:
    """讀取 config.yaml + .env，回傳驗證過的 Settings。"""
    load_dotenv(PROJECT_ROOT / ".env", override=False)

    # 優先順序：呼叫時指定 > 環境變數 > 預設路徑。
    # 環境變數讓測試可以指向獨立的設定檔，不會動到正式設定。
    if config_path:
        path = Path(config_path)
    elif os.environ.get("FAMILY_REWARD_CONFIG"):
        path = Path(os.environ["FAMILY_REWARD_CONFIG"])
    else:
        path = DEFAULT_CONFIG_PATH
    raw: Dict[str, Any] = {}
    if path.exists():
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"config.yaml 格式錯誤，無法解析：{exc}") from exc
        if not isinstance(raw, dict):
            raise ConfigError("config.yaml 最外層必須是對應表（key: value）。")

    server_raw = _section(raw, "server")
    app_raw = _section(raw, "app")
    db_raw = _section(raw, "database")
    reward_raw = _section(raw, "reward")
    security_raw = _section(raw, "security")
    admin_raw = _section(raw, "admin")
    cf_raw = _section(raw, "cloudflare")
    log_raw = _section(raw, "logging")
    backup_raw = _section(raw, "backup")
    ui_raw = _section(raw, "ui")

    settings = Settings(
        server=ServerConfig(
            host=str(server_raw.get("host", "127.0.0.1")),
            port=int(server_raw.get("port", 8080)),
            threads=int(server_raw.get("threads", 8)),
        ),
        app=AppConfig(
            name=str(app_raw.get("name", "家庭任務集點樂園")),
            timezone=str(app_raw.get("timezone", "Asia/Taipei")),
            debug=bool(app_raw.get("debug", False)),
            env=str(os.environ.get("APP_ENV") or app_raw.get("env", "production")),
        ),
        database=DatabaseConfig(
            path=_resolve(str(db_raw.get("path", "./data/family-reward.db"))),
        ),
        reward=RewardConfig(
            points_per_card=int(reward_raw.get("points_per_card", 10)),
            allow_negative_balance=bool(reward_raw.get("allow_negative_balance", False)),
        ),
        security=SecurityConfig(
            session_timeout_hours=int(security_raw.get("session_timeout_hours", 12)),
            child_pin_length=int(security_raw.get("child_pin_length", 4)),
            max_login_attempts=int(security_raw.get("max_login_attempts", 5)),
            lockout_minutes=int(security_raw.get("lockout_minutes", 5)),
        ),
        admin=AdminConfig(
            initial_username=str(admin_raw.get("initial_username", "admin")).strip(),
        ),
        cloudflare=CloudflareConfig(
            enabled=bool(cf_raw.get("enabled", False)),
            executable=_resolve(str(cf_raw.get("executable", "./cloudflare/cloudflared.exe"))),
            config=_resolve(str(cf_raw.get("config", "./cloudflare/config.yml"))),
            hostname=str(cf_raw.get("hostname", "") or ""),
        ),
        logging=LoggingConfig(
            path=_resolve(str(log_raw.get("path", "./logs/family-reward.log"))),
            level=str(log_raw.get("level", "INFO")).upper(),
            max_bytes=int(log_raw.get("max_bytes", 10 * 1024 * 1024)),
            backup_count=int(log_raw.get("backup_count", 5)),
        ),
        backup=BackupConfig(
            directory=_resolve(str(backup_raw.get("directory", "./backup"))),
            reminder_days=int(backup_raw.get("reminder_days", 7)),
        ),
        ui=UiConfig(
            sound_enabled=bool(ui_raw.get("sound_enabled", False)),
        ),
        secret_key=os.environ.get("FLASK_SECRET_KEY", "").strip(),
        admin_initial_password=os.environ.get("ADMIN_INITIAL_PASSWORD", "").strip(),
        source_path=path if path.exists() else None,
    )

    validate_settings(settings)
    return settings


def validate_settings(settings: Settings) -> None:
    """啟動前的設定檢查，任何一項不合法就拒絕啟動。"""
    errors: list[str] = []

    if not (1 <= settings.server.port <= 65535):
        errors.append(f"server.port 必須介於 1 ~ 65535，目前是 {settings.server.port}。")
    if settings.server.threads < 1:
        errors.append(f"server.threads 必須大於 0，目前是 {settings.server.threads}。")
    if settings.reward.points_per_card <= 0:
        errors.append(f"reward.points_per_card 必須大於 0，目前是 {settings.reward.points_per_card}。")
    if settings.security.session_timeout_hours <= 0:
        errors.append("security.session_timeout_hours 必須大於 0。")
    if not (3 <= settings.security.child_pin_length <= 8):
        errors.append("security.child_pin_length 必須介於 3 ~ 8。")
    if not settings.admin.initial_username:
        errors.append("admin.initial_username 不可為空白。")
    if settings.backup.reminder_days <= 0:
        errors.append("backup.reminder_days 必須大於 0。")

    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(settings.app.timezone)
    except Exception:
        errors.append(f"app.timezone 不是有效時區：{settings.app.timezone}")

    db_parent = settings.database.path.parent
    if db_parent.exists() and not os.access(db_parent, os.W_OK):
        errors.append(
            f"無法寫入資料庫目錄 {db_parent}。請確認目前使用者有寫入權限。"
        )

    if settings.is_production and not settings.secret_key:
        errors.append(
            "正式環境必須在 .env 設定 FLASK_SECRET_KEY。請參考 .env.example。"
        )

    if errors:
        raise ConfigError("設定檔有問題，無法啟動：\n- " + "\n- ".join(errors))
