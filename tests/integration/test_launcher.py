"""啟動器的行為測試。

這裡不真的啟動 Waitress（E2E 才會），只驗證那些「壞掉會很麻煩」
但單靠讀程式碼不容易確認的邏輯：Port 檢查、PID 管理、停止旗標、
設定錯誤的處理。
"""

from __future__ import annotations

import socket

import pytest

import launcher
from family_reward.config import ConfigError


@pytest.fixture()
def isolated_run_dir(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    """把 launcher 的 run 目錄指到暫存位置，不動到真正的 run\\。"""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    monkeypatch.setattr(launcher, "RUN_DIR", run_dir)
    monkeypatch.setattr(launcher, "WEB_PID_FILE", run_dir / "web.pid")
    monkeypatch.setattr(launcher, "CLOUDFLARED_PID_FILE", run_dir / "cloudflared.pid")
    monkeypatch.setattr(launcher, "SHUTDOWN_FLAG_FILE", run_dir / "shutdown.request")
    return run_dir


# --------------------------------------------------------------------------
# 停止旗標（Windows 沒有 SIGTERM 的替代方案）
# --------------------------------------------------------------------------


def test_shutdown_flag_roundtrip(isolated_run_dir):
    assert not launcher.SHUTDOWN_FLAG_FILE.exists()

    launcher.request_shutdown()
    assert launcher.SHUTDOWN_FLAG_FILE.exists()

    launcher.clear_shutdown_request()
    assert not launcher.SHUTDOWN_FLAG_FILE.exists()


def test_clear_shutdown_request_is_idempotent(isolated_run_dir):
    """檔案不存在時清除也不能拋出例外。"""
    launcher.clear_shutdown_request()
    launcher.clear_shutdown_request()


def test_watch_shutdown_flag_closes_server(isolated_run_dir):
    """旗標一出現就要關掉 server，並把旗標清掉。"""

    class FakeServer:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    server = FakeServer()
    launcher.request_shutdown()
    # interval 設 0 讓它立刻檢查一次就回傳。
    launcher._watch_shutdown_flag(server, interval=0)

    assert server.closed is True
    assert not launcher.SHUTDOWN_FLAG_FILE.exists(), "旗標必須清掉，否則下次啟動會被誤關"


def test_stop_clears_stale_flag(isolated_run_dir, capsys):
    """stop 之後一定要清掉旗標，否則下一次 start 剛啟動就被關掉。"""
    launcher.request_shutdown()

    launcher.stop()

    assert not launcher.SHUTDOWN_FLAG_FILE.exists()


# --------------------------------------------------------------------------
# PID 管理
# --------------------------------------------------------------------------


def test_pid_roundtrip(isolated_run_dir):
    launcher.write_pid(launcher.WEB_PID_FILE, 12345)

    assert launcher.read_pid(launcher.WEB_PID_FILE) == 12345


def test_read_pid_handles_garbage(isolated_run_dir):
    launcher.WEB_PID_FILE.write_text("這不是數字", encoding="utf-8")

    assert launcher.read_pid(launcher.WEB_PID_FILE) is None


def test_read_pid_missing_file(isolated_run_dir):
    assert launcher.read_pid(launcher.WEB_PID_FILE) is None


def test_current_process_is_alive():
    import os

    assert launcher.process_alive(os.getpid()) is True


def test_bogus_pid_is_not_alive():
    assert launcher.process_alive(0) is False
    assert launcher.process_alive(-1) is False


def test_stop_cleans_stale_pid_file(isolated_run_dir, capsys):
    """PID 檔留著但行程已經不在時，要清掉而不是報錯。"""
    # 用一個幾乎不可能存在的 PID。
    launcher.write_pid(launcher.WEB_PID_FILE, 999_999)

    result = launcher.stop()

    assert result == 0
    assert not launcher.WEB_PID_FILE.exists()
    assert "沒有在執行" in capsys.readouterr().out


def test_stop_with_nothing_running(isolated_run_dir, capsys):
    result = launcher.stop()

    assert result == 0
    assert "目前沒有正在執行的服務" in capsys.readouterr().out


# --------------------------------------------------------------------------
# 啟動前檢查
# --------------------------------------------------------------------------


def test_port_in_use_detection():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]

        assert launcher.is_port_in_use("127.0.0.1", port) is True

    # socket 關掉之後就不該再被視為占用
    assert launcher.is_port_in_use("127.0.0.1", port) is False


def test_already_running_is_rejected(isolated_run_dir, settings):
    """需求書第 165 節：不能同時啟動兩份。"""
    import os

    launcher.write_pid(launcher.WEB_PID_FILE, os.getpid())

    with pytest.raises(launcher.LauncherError, match="已經在執行中"):
        launcher.check_already_running(settings)


def test_occupied_port_is_rejected(isolated_run_dir, settings):
    """需求書第 164 節：Port 被占用要清楚說明，不能默默失敗。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        settings.server.port = sock.getsockname()[1]

        with pytest.raises(launcher.LauncherError, match="已被其他程式使用"):
            launcher.check_already_running(settings)


def test_ensure_directories_creates_all(tmp_path, settings):
    settings.database.path = tmp_path / "newdir" / "db.sqlite"
    settings.logging.path = tmp_path / "newlogs" / "app.log"
    settings.backup.directory = tmp_path / "newbackup"

    launcher.ensure_directories(settings)

    assert settings.database.path.parent.is_dir()
    assert settings.logging.path.parent.is_dir()
    assert settings.backup.directory.is_dir()


# --------------------------------------------------------------------------
# Cloudflare 失敗處理（需求書第 163 節）
# --------------------------------------------------------------------------


def test_cloudflare_disabled_returns_none(settings):
    settings.cloudflare.enabled = False

    assert launcher.start_cloudflared(settings) is None


def test_missing_cloudflared_executable_does_not_raise(settings, tmp_path, capsys):
    """找不到 cloudflared 時只警告，不能讓整個網站無法啟動。"""
    settings.cloudflare.enabled = True
    settings.cloudflare.executable = tmp_path / "does-not-exist.exe"
    settings.cloudflare.config = tmp_path / "config.yml"

    result = launcher.start_cloudflared(settings)

    assert result is None
    assert "找不到 cloudflared" in capsys.readouterr().out


def test_missing_cloudflare_config_does_not_raise(settings, tmp_path, capsys):
    settings.cloudflare.enabled = True
    executable = tmp_path / "cloudflared.exe"
    executable.write_text("", encoding="utf-8")
    settings.cloudflare.executable = executable
    settings.cloudflare.config = tmp_path / "missing-config.yml"

    result = launcher.start_cloudflared(settings)

    assert result is None
    assert "找不到 Cloudflare 設定檔" in capsys.readouterr().out


def test_stop_cloudflared_accepts_none():
    """沒有啟動 cloudflared 時呼叫停止也不能出錯。"""
    launcher.stop_cloudflared(None)


# --------------------------------------------------------------------------
# 設定錯誤的處理
# --------------------------------------------------------------------------


def test_main_reports_config_error(monkeypatch, capsys):
    """設定檔有問題時要顯示清楚訊息並回傳非 0。"""

    def broken_load(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise ConfigError("points_per_card 必須大於 0")

    monkeypatch.setattr(launcher, "load_settings", broken_load)
    monkeypatch.setattr("sys.argv", ["launcher.py", "start"])

    result = launcher.main()

    output = capsys.readouterr().out
    assert result == 1
    assert "設定檔有問題" in output
    assert "points_per_card" in output
    assert "config\\config.yaml" in output


def test_banner_does_not_leak_secrets(settings, capsys):
    """啟動畫面不得顯示 SECRET_KEY 或密碼。"""
    settings.secret_key = "super-secret-value-12345"
    settings.admin_initial_password = "my-initial-password"

    launcher.print_banner(settings, cloudflare_running=False)

    output = capsys.readouterr().out
    assert "super-secret-value-12345" not in output
    assert "my-initial-password" not in output
    # 但應該顯示對使用者有用的資訊
    assert str(settings.server.port) in output
