# Cloudflare Tunnel

這個目錄放 Cloudflare Tunnel 相關檔案：

```
cloudflare/
├─ cloudflared.exe        ← 自行下載，不含在專案內
├─ config.yml             ← 由 config.yml.example 複製後修改
├─ <TUNNEL_ID>.json       ← cloudflared 產生的憑證
└─ config.yml.example     ← 範本（本檔）
```

`config.yml` 與 `*.json` 已加入 `.gitignore`，**禁止提交 Git**。

架構：

```
Internet → https://kids.example.com → Cloudflare
        → Cloudflare Tunnel → 127.0.0.1:8080 → Waitress → Flask
```

好處：不需要在路由器開 Port Forwarding，也不需要對外開放 Windows 的 8080。
