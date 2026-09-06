"""E2E 測試用的伺服器 fixture。

刻意用「真的 Waitress + 真的瀏覽器」跑，
才能抓到只有在正式執行環境才會出現的問題
（例如 HTTP header 編碼、CSP 擋掉靜態檔、JavaScript 錯誤等）。

測試使用獨立的資料庫與 port，不會動到 data/family-reward.db。
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
E2E_TMP = PROJECT_ROOT / ".e2e-tmp"

ADMIN_USERNAME = "e2eadmin"
ADMIN_PASSWORD = "e2ePassword123"


#: Chrome 會直接拒絕連線的 port（ERR_UNSAFE_PORT）。
#: 隨機取 port 時如果剛好抽到這些，整組 E2E 都會失敗。
#: 參考 Chromium 的 kRestrictedPorts 清單，這裡列出常見的高位 port。
CHROME_UNSAFE_PORTS = frozenset(
    {
        1719, 1720, 1723, 2049, 3659, 4045, 5060, 5061, 6000,
        6566, 6665, 6666, 6667, 6668, 6669, 6697, 10080,
    }
)


def _free_port(max_attempts: int = 50) -> int:
    """取一個沒被占用、而且 Chrome 願意連的 port。"""
    for _ in range(max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        if port not in CHROME_UNSAFE_PORTS:
            return port
    raise RuntimeError("找不到可用的 port")


def _wait_for_server(url: str, timeout: float = 45.0) -> None:
    """等待伺服器可以回應 /health。"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.time() + timeout
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            with opener.open(f"{url}/health", timeout=3) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last_error = exc
        time.sleep(0.5)

    raise RuntimeError(f"伺服器在 {timeout} 秒內沒有啟動：{last_error}")


@pytest.fixture(scope="session")
def live_server():  # noqa: ANN201
    """啟動一個真的 Waitress 伺服器（獨立 DB / port）供 E2E 使用。"""
    E2E_TMP.mkdir(parents=True, exist_ok=True)
    port = _free_port()

    config_path = E2E_TMP / "config.yaml"
    db_path = E2E_TMP / "e2e.db"
    log_path = E2E_TMP / "e2e.log"
    backup_dir = E2E_TMP / "backup"

    # 每次都從乾淨的資料庫開始。
    for leftover in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        leftover.unlink(missing_ok=True)

    config_path.write_text(
        f"""
server:
  host: "127.0.0.1"
  port: {port}
  threads: 4

app:
  name: "家庭任務集點樂園"
  timezone: "Asia/Taipei"
  debug: false
  env: "production"

database:
  path: "{db_path.as_posix()}"

reward:
  points_per_card: 10
  allow_negative_balance: false

security:
  session_timeout_hours: 12
  child_pin_length: 4
  max_login_attempts: 50
  lockout_minutes: 1

admin:
  initial_username: "{ADMIN_USERNAME}"

cloudflare:
  enabled: false

logging:
  path: "{log_path.as_posix()}"
  level: "INFO"

backup:
  directory: "{backup_dir.as_posix()}"
  reminder_days: 7
""".strip(),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["FAMILY_REWARD_CONFIG"] = str(config_path)
    env["FLASK_SECRET_KEY"] = "e2e-secret-key-for-testing-only"
    env["ADMIN_INITIAL_PASSWORD"] = ADMIN_PASSWORD
    env["APP_ENV"] = "production"
    env["PYTHONIOENCODING"] = "utf-8"

    process = subprocess.Popen(
        [sys.executable, "-m", "tests.e2e.server_runner"],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_server(base_url)
    except RuntimeError:
        process.terminate()
        output = ""
        try:
            output = process.communicate(timeout=10)[0] or ""
        except subprocess.TimeoutExpired:
            process.kill()
        raise RuntimeError(f"E2E 伺服器啟動失敗：\n{output}")

    yield base_url

    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):  # noqa: ANN201
    """統一使用手機尺寸，因為小孩最可能用手機/平板。"""
    return {
        **browser_context_args,
        "viewport": {"width": 414, "height": 896},
        "locale": "zh-TW",
        "timezone_id": "Asia/Taipei",
    }


@pytest.fixture()
def page_errors(page):  # noqa: ANN201
    """收集頁面上的 JavaScript 錯誤與 CSP 違規，測試結束時斷言為空。"""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))

    def _on_console(message):  # noqa: ANN001, ANN202
        if message.type == "error":
            errors.append(f"console: {message.text}")

    page.on("console", _on_console)
    return errors
