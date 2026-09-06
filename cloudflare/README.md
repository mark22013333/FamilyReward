# Cloudflare Tunnel

讓家人在外面也能用自己的網域連進來，例如 `https://familyreward.longhopick.com`。

```
Internet → https://你的網域 → Cloudflare
        → Cloudflare Tunnel → 127.0.0.1:8080 → Waitress → Flask
```

**不需要**在路由器開 Port Forwarding，也**不需要**對外開放 Windows 的 8080。

---

## 先執行這個

```
cloudflare-setup.bat
```

它會檢查你目前的狀態（有沒有裝 cloudflared、有沒有登入、有哪些 tunnel、
Windows 服務跑不跑、本機網站在不在），然後**依照你的情況**告訴你接下來該做什麼。

它只做檢查與說明，**不會**替你改 Cloudflare 上的任何設定 —— 對外公開網址
是需要你自己確認的變更。

---

## 兩種設定方式

Cloudflare Tunnel 有兩種管理方式，設定位置完全不同。搞混是最常見的卡關原因。

### A. 儀表板管理（remotely-managed）★ 多數人是這種

特徵：cloudflared 用 `--token` 或 `--token-file` 啟動，通常已註冊成 Windows 服務。

- **路由設定在網頁上**，不是本機的 `config.yml`
- 一個 tunnel 可以掛很多個網域，彼此互不影響
- 開機自動啟動（服務）

**新增一個網域的步驟：**

1. 開啟 <https://one.dash.cloudflare.com/>
2. 左邊選單：**Networks → Tunnels**
3. 點選正在連線中的那個 tunnel
4. **Configure → Public Hostname → Add a public hostname**
5. 填入：

   | 欄位 | 值 |
   |---|---|
   | Subdomain | `familyreward` |
   | Domain | `longhopick.com` |
   | Path | （留空） |
   | Type | **HTTP**（不是 HTTPS） |
   | URL | `127.0.0.1:8080` |

6. **Save hostname**

DNS 記錄 Cloudflare 會自動建立，不用手動加。

> **Type 為什麼是 HTTP？**
> 這裡填的是「tunnel 要怎麼連到你的本機服務」。本機跑的是 http，
> 對外的 https 由 Cloudflare 負責。填成 HTTPS 反而會連不上。

然後在 `config\config.yaml` 填上網域（讓後台顯示公開網址）：

```yaml
cloudflare:
  enabled: false     # 保持 false！tunnel 由 Windows 服務負責
  hostname: "familyreward.longhopick.com"
```

> **`enabled` 要保持 `false`**
> 它的意思是「要不要由 start.bat 再啟動一個 cloudflared」。
> 你的 tunnel 已經是 Windows 服務了，設成 true 會多跑一個重複的行程。
>
> 即使 `enabled: false`，只要有填 `hostname`，系統仍然知道自己在 proxy
> 後面，會正確啟用 Secure cookie 並解析 `X-Forwarded-Proto`。

### B. 本機設定檔（locally-managed）

特徵：用 `--config config.yml` 啟動，由 `start.bat` 一起帶起來。

```
cloudflare/
├─ cloudflared.exe        自行下載
├─ config.yml             由 config.yml.example 複製後修改
└─ <TUNNEL_ID>.json       cloudflared 產生的憑證
```

步驟：

```bat
cloudflare\cloudflared.exe tunnel login
cloudflare\cloudflared.exe tunnel create family-reward
cloudflare\cloudflared.exe tunnel route dns family-reward familyreward.longhopick.com
```

複製 `config.yml.example` 成 `config.yml` 填入 Tunnel ID 與網域，然後：

```yaml
cloudflare:
  enabled: true
  hostname: "familyreward.longhopick.com"
```

---

## 已經有其他網域在跑怎麼辦

**可以共用同一個 tunnel。** 一個 tunnel 掛多個網域是正常用法：

```
filmax tunnel
  ├─ video.longhopick.com         → 127.0.0.1:<某個 port>
  └─ familyreward.longhopick.com  → 127.0.0.1:8080
```

只要兩個服務的 port 不同即可。新增路由**不會中斷**既有的網域。

---

## 安全性

- `config.yml` 與 `*.json` 憑證檔含有機密資訊，**已加入 `.gitignore`，禁止提交 Git**
- Waitress 只綁 `127.0.0.1`，外界只能經由 tunnel 連入
- 設定了對外網域之後，系統會自動啟用 Secure cookie 並只信任 1 hop 的 Proxy Header
