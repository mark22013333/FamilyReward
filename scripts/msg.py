"""BAT 檔的中文訊息輸出。

為什麼需要這個檔案：

Windows 的 `cmd.exe` 會用「系統 ANSI 代碼頁」讀取 .bat 檔本身
（在台灣通常是 CP950 / Big5）。如果 .bat 檔內含 UTF-8 中文，
即使開頭寫了 `chcp 65001`，檔案前段的位元組也已經被誤判，
輕則顯示亂碼，重則讓指令解析錯亂而直接閃退。

因此 .bat 一律保持純 ASCII，所有中文訊息改由這支 Python 輸出。
"""

from __future__ import annotations

import sys

MESSAGES: dict[str, str] = {
    "start_failed": (
        "啟動沒有成功。詳細資訊請查看：\n"
        "\n"
        "    logs\\family-reward.log"
    ),
    "stop_header": (
        "============================================================\n"
        "\n"
        "     家庭任務集點樂園 - 停止服務\n"
        "\n"
        "============================================================"
    ),
    "backup_header": (
        "============================================================\n"
        "\n"
        "     家庭任務集點樂園 - 備份資料庫\n"
        "\n"
        "============================================================"
    ),
    "no_python": (
        "[錯誤] 找不到 Python 環境。\n"
        "\n"
        "請先執行一次 start.bat 完成安裝。"
    ),
}


def main() -> int:
    if len(sys.argv) < 2:
        return 1

    text = MESSAGES.get(sys.argv[1])
    if text is None:
        return 1

    # 確保以 UTF-8 輸出；BAT 已經先 chcp 65001。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
