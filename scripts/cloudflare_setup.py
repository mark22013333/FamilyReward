"""Cloudflare Tunnel 設定小幫手。

由 cloudflare-setup.bat 執行。

這支程式「只做檢查與說明」，不會替你改任何 Cloudflare 上的設定，
因為路由設定屬於對外公開的變更，應該由你在儀表板上親自確認。

它會告訴你：
    1. cloudflared 裝在哪、版本多少
    2. 是否已經登入（cert.pem）
    3. 有哪些 tunnel、跑在哪台機器
    4. Windows 服務的狀態與它用的設定方式
    5. 你的網站現在有沒有在跑、port 是多少
    6. 接下來該在儀表板做什麼（逐步說明）
    7. 設定完成後，幫你驗證對外網址是否真的通了
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from family_reward.config import ConfigError, load_settings  # noqa: E402

CLOUDFLARED_CANDIDATES = (
    Path(r"C:\Program Files (x86)\cloudflared\cloudflared.exe"),
    Path(r"C:\Program Files\cloudflared\cloudflared.exe"),
    PROJECT_ROOT / "cloudflare" / "cloudflared.exe",
)

LINE = "=" * 62
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _print_header(title: str) -> None:
    print()
    print(LINE)
    print(f"  {title}")
    print(LINE)
    print()


def _run(args: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=NO_WINDOW,
        )
        return result.returncode, (result.stdout or "") + (result.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def find_cloudflared() -> Path | None:
    for path in CLOUDFLARED_CANDIDATES:
        if path.exists():
            return path
    # 最後試 PATH
    code, out = _run(["where", "cloudflared"])
    if code == 0:
        first = out.strip().splitlines()
        if first:
            candidate = Path(first[0].strip())
            if candidate.exists():
                return candidate
    return None


def check_login() -> Path | None:
    cert = Path(os.environ.get("USERPROFILE", "")) / ".cloudflared" / "cert.pem"
    return cert if cert.exists() else None


def list_tunnels(cloudflared: Path) -> list[dict]:
    code, out = _run([str(cloudflared), "tunnel", "list", "--output", "json"])
    if code != 0:
        return []
    try:
        return json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return []


def service_info() -> tuple[str, str]:
    """回傳 (狀態, 啟動指令)。"""
    code, out = _run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "$s=Get-Service Cloudflared -ErrorAction SilentlyContinue;"
            "$c=(Get-CimInstance Win32_Service -Filter \"Name='Cloudflared'\").PathName;"
            "if($s){Write-Output \"$($s.Status)|$c\"}else{Write-Output 'NONE|'}",
        ],
        timeout=60,
    )
    if code != 0 or "|" not in out:
        return ("未知", "")
    status, _, path = out.strip().partition("|")
    return (status.strip(), path.strip())


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.5)
        return sock.connect_ex((host, port)) == 0


def check_public_url(hostname: str) -> tuple[bool, str]:
    """檢查對外網址的 /health 是否回應正常。"""
    url = f"https://{hostname}/health"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=15) as response:
            body = response.read().decode("utf-8", errors="replace").strip()
            if response.status == 200 and '"UP"' in body:
                return True, body
            return False, f"HTTP {response.status}：{body[:120]}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}（{exc.reason}）"
    except urllib.error.URLError as exc:
        return False, f"連線失敗：{exc.reason}"
    except (TimeoutError, OSError) as exc:
        return False, f"連線失敗：{exc}"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    _print_header("Cloudflare Tunnel 設定小幫手")

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"設定檔有問題：{exc}")
        return 1

    host = settings.server.host
    port = settings.server.port
    configured_hostname = settings.cloudflare.hostname

    # --- 1. cloudflared ---
    print("【1】cloudflared")
    cloudflared = find_cloudflared()
    if cloudflared is None:
        print("    ✗ 找不到 cloudflared.exe")
        print()
        print("    請先安裝：")
        print("        winget install --id Cloudflare.cloudflared")
        print()
        print("    或從官方下載後放到 cloudflare\\cloudflared.exe")
        print()
        return 1
    code, version = _run([str(cloudflared), "--version"])
    print(f"    ✓ {cloudflared}")
    print(f"      {version.strip()}")
    print()

    # --- 2. 登入狀態 ---
    print("【2】登入狀態")
    cert = check_login()
    if cert is None:
        print("    ✗ 尚未登入（找不到 cert.pem）")
        print()
        print("    請執行：")
        print(f'        "{cloudflared}" tunnel login')
        print()
        print("    瀏覽器會開啟，選擇 longhopick.com 這個網域授權即可。")
        print()
        return 1
    print(f"    ✓ 已登入（{cert}）")
    print()

    # --- 3. 現有 tunnel ---
    print("【3】現有的 Tunnel")
    tunnels = list_tunnels(cloudflared)
    if not tunnels:
        print("    （沒有找到任何 tunnel，或無法讀取清單）")
    for tunnel in tunnels:
        name = tunnel.get("name", "?")
        tid = tunnel.get("id", "?")
        conns = tunnel.get("connections") or []
        state = f"連線中（{len(conns)} 條）" if conns else "未連線"
        print(f"    • {name:<16} {state}")
        print(f"      id: {tid}")
    print()

    # --- 4. Windows 服務 ---
    print("【4】Windows 服務")
    status, path = service_info()
    if status == "NONE":
        print("    ✗ 沒有安裝 Cloudflared 服務（tunnel 不會開機自動啟動）")
    else:
        print(f"    ✓ 狀態：{status}")
        if "--token-file" in path or "--token" in path:
            print("      類型：儀表板管理（remotely-managed）")
            print("      → 路由設定在 Cloudflare 儀表板，不是本機的 config.yml")
        elif path:
            print("      類型：本機設定檔（locally-managed）")
    print()

    # --- 5. 本機網站 ---
    print("【5】本機網站")
    if port_in_use(host, port):
        print(f"    ✓ 有在執行：http://{host}:{port}")
    else:
        print(f"    ✗ 沒有在執行（http://{host}:{port} 沒有回應）")
        print("      請先執行 start.bat，Tunnel 才有東西可以轉發。")
    print()

    # --- 6. 接下來要做什麼 ---
    _print_header("接下來：在 Cloudflare 儀表板新增一條路由")

    target_hostname = configured_hostname or "familyreward.longhopick.com"

    print("因為你的 tunnel 是「儀表板管理」型，路由要在網頁上設定：")
    print()
    print("  1. 開啟 https://one.dash.cloudflare.com/")
    print("  2. 左邊選單：Networks → Tunnels")
    print("  3. 點選你正在跑的那個 tunnel（就是上面【3】顯示連線中的那個）")
    print("  4. 按 Configure → Public Hostname → Add a public hostname")
    print("  5. 填入：")
    print()
    print(f"         Subdomain : {target_hostname.split('.')[0]}")
    print(f"         Domain    : {'.'.join(target_hostname.split('.')[1:])}")
    print("         Path      : （留空）")
    print()
    print("         Type      : HTTP")
    print(f"         URL       : {host}:{port}")
    print()
    print("  6. 按 Save hostname")
    print()
    print("DNS 記錄 Cloudflare 會自動幫你建立，不需要手動加。")
    print()
    print("※ Type 要選 HTTP（不是 HTTPS）—— 本機服務跑的是 http，")
    print("   對外的 https 由 Cloudflare 負責。")
    print()

    # --- 7. 驗證 ---
    _print_header("驗證")

    if not configured_hostname:
        print("config\\config.yaml 目前還沒有填 cloudflare.hostname。")
        print()
        print("建議填上，後台設定頁才會顯示你的公開網址：")
        print()
        print("    cloudflare:")
        print("      enabled: false          # 儀表板管理型請保持 false")
        print(f'      hostname: "{target_hostname}"')
        print()
        print("（enabled 保持 false 是正確的 —— tunnel 由 Windows 服務負責，")
        print("  不需要 start.bat 再啟動一個 cloudflared。）")
        print()
        print(f"設定好路由之後，可以用瀏覽器開 https://{target_hostname} 測試。")
        print()
        return 0

    print(f"正在測試 https://{configured_hostname}/health ...")
    print()
    ok, detail = check_public_url(configured_hostname)
    if ok:
        print(f"    ✓ 成功！對外網址已經可以使用：{detail}")
        print()
        print(f"    家人現在可以用這個網址：https://{configured_hostname}")
    else:
        print(f"    ✗ 還不通：{detail}")
        print()
        print("    可能的原因：")
        print("      • 儀表板的 Public Hostname 還沒設定（見上面步驟）")
        print("      • DNS 還在生效中，等 1 ~ 2 分鐘再試")
        print("      • 本機網站沒有啟動（先跑 start.bat）")
        print(f"      • 儀表板填的 URL 不是 {host}:{port}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
