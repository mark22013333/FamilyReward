"""BAT 檔的格式測試。

背景（實際踩過的坑）：

Windows 的 `cmd.exe` 是用「系統 ANSI 代碼頁」讀取 .bat 檔本身，
在台灣通常是 CP950 / Big5。如果 .bat 內含 UTF-8 中文，即使開頭寫了
`chcp 65001` 也來不及 —— 檔案前段的位元組已經被當成 Big5 誤判，
結果是畫面亂碼、指令解析錯亂，`start.bat` 直接閃退。

再加上 .bat 若使用 LF 換行，在某些情況下 `cmd.exe` 也會把整行讀壞。

所以規則是：**BAT 一律純 ASCII + CRLF**，中文訊息交給 scripts/msg.py 輸出。
這幾個測試就是釘住這條規則。
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BAT_FILES = ["start.bat", "stop.bat", "backup.bat", "restore.bat"]


@pytest.fixture(params=BAT_FILES)
def bat_path(request) -> Path:  # noqa: ANN001
    path = PROJECT_ROOT / request.param
    if not path.exists():
        pytest.skip(f"{request.param} 不存在")
    return path


def test_bat_is_pure_ascii(bat_path: Path):
    """BAT 內容必須是純 ASCII，中文交給 scripts/msg.py 輸出。"""
    data = bat_path.read_bytes()

    try:
        data.decode("ascii")
    except UnicodeDecodeError as exc:
        offending = data[exc.start : exc.start + 20]
        line = data[: exc.start].count(b"\n") + 1
        pytest.fail(
            f"{bat_path.name} 第 {line} 行含有非 ASCII 位元組：{offending!r}\n"
            "在 CP950 系統上 cmd.exe 會把它讀成亂碼並可能導致閃退。\n"
            "請把中文訊息移到 scripts/msg.py。"
        )


def test_bat_uses_crlf(bat_path: Path):
    """BAT 必須使用 CRLF；單獨的 LF 可能讓 cmd.exe 讀壞整行。"""
    data = bat_path.read_bytes()

    crlf_count = data.count(b"\r\n")
    lone_lf = data.count(b"\n") - crlf_count

    assert lone_lf == 0, (
        f"{bat_path.name} 有 {lone_lf} 個單獨的 LF 換行，必須全部是 CRLF。"
    )
    assert crlf_count > 0, f"{bat_path.name} 看起來沒有任何換行。"


def test_bat_sets_utf8_codepage(bat_path: Path):
    """每個 BAT 都要先切到 UTF-8 代碼頁，之後 Python 輸出的中文才不會亂碼。"""
    content = bat_path.read_text(encoding="ascii")

    assert "chcp 65001" in content, f"{bat_path.name} 缺少 chcp 65001"


def _executable_lines(path: Path) -> list[str]:
    """只取實際會執行的指令，略過 REM 註解。"""
    lines = []
    for raw in path.read_text(encoding="ascii").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.lower().startswith("rem"):
            continue
        lines.append(stripped)
    return lines


def test_bat_does_not_kill_all_python(bat_path: Path):
    """需求書第 89 節：禁止用 taskkill /F /IM python.exe 誤殺其他程式。

    只檢查實際會執行的行；註解裡說明「我們不這樣做」是允許的。
    """
    for line in _executable_lines(bat_path):
        assert "/im python.exe" not in line.lower(), (
            f"{bat_path.name} 不可以用 image name 砍掉所有 python.exe，"
            f"只能關閉本系統自己記錄的 PID。問題行：{line}"
        )


def test_bat_pauses_on_error(bat_path: Path):
    """需求書第 87 節：不要讓 BAT 一閃就關掉，錯誤時要 pause 讓使用者看得到。"""
    content = bat_path.read_text(encoding="ascii")

    assert "pause" in content, f"{bat_path.name} 缺少 pause，出錯時視窗會直接消失"


# --------------------------------------------------------------------------
# 中文訊息輸出（scripts/msg.py）
# --------------------------------------------------------------------------


def test_msg_script_exists():
    assert (PROJECT_ROOT / "scripts" / "msg.py").exists()


def test_msg_keys_used_by_bat_all_exist():
    """BAT 呼叫的每個訊息 key 都必須真的存在，否則畫面會少一段文字。"""
    import re
    import sys

    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    import msg  # noqa: PLC0415

    used: set[str] = set()
    for name in BAT_FILES:
        path = PROJECT_ROOT / name
        if not path.exists():
            continue
        for line in _executable_lines(path):
            # 只比對真的有呼叫 msg.py 的指令行。
            used.update(re.findall(r'msg\.py"\s+(\w+)', line))

    missing = used - set(msg.MESSAGES)
    assert not missing, f"BAT 用到但 msg.py 沒有定義的 key：{missing}"


def test_msg_outputs_utf8(tmp_path):
    """msg.py 要能正確輸出 UTF-8 中文。"""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "msg.py"), "stop_header"],
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "家庭任務集點樂園".encode() in result.stdout


def test_msg_unknown_key_returns_error():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "msg.py"), "no_such_key"],
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 1


def test_gitattributes_forces_crlf_for_bat():
    """.gitattributes 要確保 clone 出來的 .bat 仍然是 CRLF。"""
    path = PROJECT_ROOT / ".gitattributes"
    assert path.exists(), "缺少 .gitattributes"

    content = path.read_text(encoding="utf-8")
    assert "*.bat" in content and "crlf" in content.lower(), (
        ".gitattributes 必須把 *.bat 標記為 eol=crlf，"
        "否則在其他機器 clone 之後 BAT 又會變成 LF。"
    )
