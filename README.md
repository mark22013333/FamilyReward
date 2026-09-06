# 家庭任務集點樂園 ⭐

給家裡用的兒童任務集點與獎勵系統。家長安排每天要做的事，小孩完成後送出申請，家長確認後才拿到星星；星星累積起來可以兌換禮物。

不是 Prototype，是可以真的放在家裡 Windows 電腦每天執行的系統。

---

## 目錄

- [專案介紹](#專案介紹)
- [系統需求](#系統需求)
- [第一次安裝](#第一次安裝)
- [啟動方式](#啟動方式)
- [停止方式](#停止方式)
- [設定檔](#設定檔)
- [建立 Admin](#建立-admin)
- [SQLite](#sqlite)
- [Migration](#migration)
- [Backup](#backup)
- [Restore](#restore)
- [Cloudflare Tunnel](#cloudflare-tunnel)
- [測試](#測試)
- [目錄結構](#目錄結構)
- [架構設計](#架構設計)
- [資料庫 Schema](#資料庫-schema)
- [點數計算規則](#點數計算規則)
- [任務審核流程](#任務審核流程)
- [禮物兌換流程](#禮物兌換流程)
- [安全性](#安全性)
- [Troubleshooting](#troubleshooting)
- [已知限制](#已知限制)
- [未來可以擴充的項目](#未來可以擴充的項目)

---

## 專案介紹

### 這個系統想解決什麼

小孩常常不知道「今天到底要做哪些事」，家長也不容易持續給正向回饋。這個系統把每天的任務變成看得見的清單，完成之後有星星、有集點卡、有禮物可以期待。

核心不是監督或懲罰，而是**鼓勵、習慣、參與、成就感**。所以介面上不會出現「你今天沒有完成」「你失敗了」這類文案。

### 主要功能

| 對象 | 功能 |
|---|---|
| 小孩 | 看今天的任務、送出完成申請、集點卡、行事曆、禮物兌換、點數紀錄、成就徽章 |
| 家長 | 建立小孩／任務／禮物、審核任務、審核兌換、手動調整點數、稽核紀錄、備份 |

### 使用流程

```
家長建立任務
      ↓
小孩看到今天的任務 → 按「我完成了！」
      ↓
家長在待確認頁面審核
      ↓
通過 → 星星入帳 → 累積集點卡 → 兌換禮物
```

**重點**：小孩按下完成不會馬上拿到點數，一定要家長確認。

---

## 系統需求

| 項目 | 需求 |
|---|---|
| 作業系統 | Windows 10 / 11 |
| Python | 3.10 或更新版本（建議 3.12+） |
| 磁碟空間 | 約 200 MB（含虛擬環境） |
| 瀏覽器 | Chrome / Edge / Safari（手機、平板、桌機皆可） |

不需要安裝 Node.js、Docker、資料庫伺服器。

> **關於 Python 版本**
> 原始需求書寫的是 Python 3.12+。本專案的程式碼相容 **3.10 以上**（沒有使用 3.11/3.12 才有的語法），在 3.12 上同樣可以正常執行。開發與驗證是在 Python 3.10.11 上完成的。

---

## 第一次安裝

1. 把整個專案解壓縮到一個固定的位置，例如：

   ```
   C:\family-reward\
   ```

2. 設定密碼與金鑰。把 `.env.example` 複製成 `.env`：

   ```bat
   copy .env.example .env
   ```

   打開 `.env`，填入兩個值：

   ```ini
   FLASK_SECRET_KEY=一段夠長的隨機字串
   ADMIN_INITIAL_PASSWORD=你要用的初始管理員密碼
   ```

   `FLASK_SECRET_KEY` 可以這樣產生：

   ```bat
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

3. 雙擊 `start.bat`。

   第一次啟動會自動：建立 `.venv` → 安裝套件 → 建立資料庫 → 建立管理員帳號 → 啟動網站。這一步需要幾分鐘，之後啟動就很快。

4. 打開瀏覽器：<http://127.0.0.1:8080>

> `.env` 含有密碼，**已加入 `.gitignore`，禁止提交 Git**。

---

## 啟動方式

雙擊：

```
start.bat
```

畫面會顯示：

```
============================================================

     家庭任務集點樂園 ⭐

============================================================

本機網址：

    http://127.0.0.1:8080

SQLite：

    C:\family-reward\data\family-reward.db

Log：

    C:\family-reward\logs\family-reward.log

============================================================
```

不需要自己執行 `flask run`、`pip install` 或 `flask db upgrade`，`start.bat` 都會處理。

正式環境使用 **Waitress**（不是 Flask 開發伺服器）。

### 想開機自動啟動

把 `start.bat` 的捷徑放進：

```
shell:startup
```

（在檔案總管網址欄輸入上面那行即可開啟該資料夾。）

---

## 停止方式

雙擊：

```
stop.bat
```

或在啟動的視窗按 `Ctrl+C`。

`stop.bat` 只會關閉本系統自己記錄在 `run\web.pid` 的行程，**不會**用 `taskkill /F /IM python.exe` 誤殺你其他的 Python 程式。

---

## 設定檔

所有會依環境改變的參數都在 `config\config.yaml`，改完要**重新啟動**才生效。

```yaml
server:
  host: "127.0.0.1"     # 不要改成 0.0.0.0，除非你清楚後果
  port: 8080            # 被占用時改這裡
  threads: 8

app:
  name: "家庭任務集點樂園"
  timezone: "Asia/Taipei"
  debug: false          # 正式環境必須是 false
  env: "production"

database:
  path: "./data/family-reward.db"

reward:
  points_per_card: 10          # 幾點算一張集點卡
  allow_negative_balance: false # 是否允許餘額為負

security:
  session_timeout_hours: 12
  child_pin_length: 4     # 小孩 PIN 幾位數
  max_login_attempts: 5   # 連續失敗幾次會暫時鎖定
  lockout_minutes: 5

admin:
  initial_username: "admin"

cloudflare:
  enabled: false
  executable: "./cloudflare/cloudflared.exe"
  config: "./cloudflare/config.yml"
  hostname: "kids.example.com"

logging:
  path: "./logs/family-reward.log"
  level: "INFO"
  max_bytes: 10485760    # 10 MB 後輪替
  backup_count: 5

backup:
  directory: "./backup"
  reminder_days: 7       # 超過幾天沒備份就提醒

ui:
  sound_enabled: false   # 第一版不播音效
```

敏感資訊（`FLASK_SECRET_KEY`、`ADMIN_INITIAL_PASSWORD`、Cloudflare Token）**不要**寫進 `config.yaml`，一律放 `.env`。

啟動時會檢查設定合法性，例如 `points_per_card` 設成 0 會直接拒絕啟動並顯示原因。

---

## 建立 Admin

第一次啟動時，如果資料庫裡還沒有任何管理員，系統會用以下兩個值自動建立：

- 帳號：`config.yaml` 的 `admin.initial_username`（預設 `admin`）
- 密碼：`.env` 的 `ADMIN_INITIAL_PASSWORD`

登入之後，後台會**固定顯示提醒**，直到你修改密碼：

```
⚠️ 目前仍使用初始管理員密碼，請立即修改。
```

修改位置：**後台 → ⚙️ 設定 → 修改管理員密碼**（至少 8 個字元）。

### 小孩登入

小孩不需要記帳號密碼。首頁選自己的頭像，再輸入 4 位數字 PIN 即可。

PIN 由家長在「後台 → 👧 小孩」設定，以 Hash 儲存，系統不會保存明碼，忘記只能由家長重設。

---

## SQLite

資料庫檔案：

```
data\family-reward.db
```

- 刻意**不**放在 `static\` 或 `templates\`，避免經由 HTTP 被下載。
- 每條連線都會套用：

  ```sql
  PRAGMA foreign_keys = ON;     -- 外鍵真的生效
  PRAGMA busy_timeout = 5000;   -- 避免 database is locked
  PRAGMA synchronous = NORMAL;
  ```

- 資料庫本身設定為 **WAL** 模式，家裡幾個人同時操作也不容易卡住。

WAL 模式會多出兩個檔案，屬正常現象：

```
family-reward.db-wal
family-reward.db-shm
```

關閉程式後資料仍然保存，重新啟動即可繼續使用。

---

## Migration

使用 Flask-Migrate（Alembic）管理資料庫版本，`start.bat` 會自動執行，使用者不需要手動輸入指令。

**Migration 失敗時不會啟動網站**，避免用錯誤的 schema 繼續跑。畫面會顯示：

```
資料庫更新失敗。

請查看：logs\family-reward.log
```

開發時如果修改了 Model，要自己產生 migration：

```bat
.venv\Scripts\python.exe -m flask --app app db migrate -m "說明"
.venv\Scripts\python.exe -m flask --app app db upgrade
```

正式環境不使用 `db.create_all()` 當作長期方案。

---

## Backup

### 手動備份

雙擊：

```
backup.bat
```

備份檔會放在 `backup\`，檔名帶時間戳記：

```
backup\family-reward-20260906-213000.db
```

### 從後台備份

**後台 → 📊 首頁**（或 ⚙️ 設定）都有「立即備份」按鈕，並顯示最近備份時間。

超過 `backup.reminder_days`（預設 7 天）沒有備份，後台會顯示：

```
⚠️ 已經 8 天沒有備份囉
```

### 為什麼不直接複製 .db

直接複製正在寫入的 SQLite 檔案可能拿到損壞或不一致的備份。本系統使用 SQLite 官方的 **Backup API**（`sqlite3.Connection.backup()`），即使系統正在使用中也能取得一致的快照。

建議偶爾把 `backup\` 裡的檔案複製到外接硬碟或雲端硬碟。

---

## Restore

雙擊：

```
restore.bat
```

流程：

1. **檢查系統是否已停止** —— 還在執行會直接拒絕，請先執行 `stop.bat`
2. 列出所有可用的備份讓你選
3. 要求輸入 `yes` 二次確認
4. **先把目前的資料庫備份成 `pre-restore-*`**（後悔還救得回來）
5. 才覆蓋資料庫

還原完成後執行 `start.bat` 重新啟動。

---

## Cloudflare Tunnel

想讓家人在外面也能用自己的網域連進來（例如 `https://kids.example.com`），使用 Cloudflare Tunnel。

```
Internet → https://kids.example.com → Cloudflare
        → Cloudflare Tunnel → 127.0.0.1:8080 → Waitress → Flask → SQLite
```

**不需要**在路由器開 Port Forwarding，也**不需要**對外開放 Windows 的 8080。

### 設定步驟

1. 下載 `cloudflared.exe` 放到 `cloudflare\` 目錄
2. 登入並建立 tunnel：

   ```bat
   cloudflare\cloudflared.exe tunnel login
   cloudflare\cloudflared.exe tunnel create family-reward
   cloudflare\cloudflared.exe tunnel route dns family-reward kids.example.com
   ```

3. 把 `cloudflare\config.yml.example` 複製成 `cloudflare\config.yml`，填入你的 Tunnel ID 與網域
4. 在 `config\config.yaml` 設定：

   ```yaml
   cloudflare:
     enabled: true
     hostname: "kids.example.com"
   ```

5. 重新執行 `start.bat`

### Tunnel 啟動失敗會怎樣

**本機服務仍然正常運作**，只會顯示警告：

```
⚠️ 網站已在本機啟動，但 Cloudflare Tunnel 啟動失敗。

本機：http://127.0.0.1:8080

請查看 Log。
```

不會因為 Tunnel 有問題就把整個網站關掉。

`cloudflare\config.yml` 與 `*.json` 憑證檔含有機密資訊，**已加入 `.gitignore`，禁止提交 Git**。

---

## 測試

```bat
REM 全部測試（單元 + 整合 + E2E）
.venv\Scripts\python.exe -m pytest

REM 只跑快的（單元 + 整合）
.venv\Scripts\python.exe -m pytest tests/unit tests/integration

REM 只跑端對端（需要 Playwright 瀏覽器）
.venv\Scripts\python.exe -m pytest tests/e2e
```

E2E 測試第一次執行前要安裝瀏覽器：

```bat
.venv\Scripts\python.exe -m pip install pytest-playwright
.venv\Scripts\python.exe -m playwright install chromium
```

### 測試結果

實際執行結果（Python 3.10.11 / Windows 11）：

```
tests/unit          ...  58 passed    服務層邏輯、點數帳本、設定驗證、DB constraint
tests/integration   ... 112 passed    HTTP 流程、權限、後台操作、啟動器、BAT 格式
tests/e2e           ...  10 passed    真瀏覽器走完整驗收流程
--------------------------------------------------------------
總計                    180 passed    （約 73 秒）
```

測試一律使用暫存資料庫，**不會**動到 `data\family-reward.db`。

### 測試涵蓋的資料一致性規則

| # | 規則 | 測試 |
|---|---|---|
| 1 | 任務 +2，批准後餘額 = 2 | `test_approve_adds_points_once` |
| 2 | 連按兩次批准只能 +2，不得 +4 | `test_approve_twice_does_not_double_points` |
| 3 | 13 點兌換 10 點 → 剩 3 點 | `test_request_then_approve_deducts_points` |
| 4 | 只有 3 點卻要兌換 10 點 → 拒絕，不得變 -7 | `test_approve_rejected_when_points_dropped` |
| 5 | 退回的任務不得產生任何點數 | `test_rejected_task_creates_no_points` |
| 6 | 重複送出不得產生重複審核 | `test_submit_twice_is_rejected` |
| 7 | 庫存 1，第一次成功後第二次失敗 | `test_stock_decrements_and_blocks_second_redeem` |
| 8 | 小孩 A 不能操作小孩 B 的資料 | `test_child_cannot_submit_another_childs_task` 等 |

E2E 測試則以真實瀏覽器完整走過需求書第 174 節的驗收流程（建立小孩 → 建任務 → PIN 登入 → 完成 → 審核 → 集點卡 → 兌換 → 行事曆）。

---

## 目錄結構

```
family-reward/
│
├─ start.bat                  雙擊啟動
├─ stop.bat                   停止
├─ backup.bat                 備份資料庫
├─ restore.bat                還原資料庫
├─ launcher.py                啟動流程（Migration / Waitress / Cloudflare / PID）
├─ app.py                     WSGI 進入點
├─ requirements.txt
├─ pytest.ini
├─ .env                       密碼與金鑰（不進 Git）
├─ .env.example
│
├─ config/
│  └─ config.yaml             所有環境相關設定
│
├─ family_reward/
│  ├─ __init__.py
│  ├─ app_factory.py          create_app()
│  ├─ config.py               YAML + .env 載入與驗證
│  ├─ database.py             SQLite PRAGMA / WAL
│  ├─ extensions.py           db / migrate / csrf / login_manager
│  ├─ seed.py                 初始化與範例資料
│  │
│  ├─ models/                 AdminUser, Child, Task, TaskSchedule,
│  │                          TaskAssignee, TaskAssignment,
│  │                          PointTransaction, Reward, RewardRedemption,
│  │                          AuditLog, Notification, Achievement
│  ├─ routes/                 public / auth / child / admin / api
│  ├─ services/               商業邏輯（見下方架構說明）
│  ├─ forms/                  WTForms 表單與驗證
│  ├─ security/               登入授權、Rate Limit、安全性 Header
│  ├─ utils/                  時區、Logging
│  └─ exceptions/             商業邏輯例外
│
├─ templates/
│  ├─ base.html
│  ├─ public/  child/  admin/  auth/  error/  components/
│
├─ static/
│  ├─ css/    variables / layout / components / child / admin / animations
│  └─ js/     app / task / reward / calendar / animations
│
├─ migrations/                Alembic
├─ scripts/                   backup_db.py / restore_db.py
├─ tests/
│  ├─ unit/  integration/  e2e/
│
├─ data/                      SQLite（不進 Git）
├─ logs/                      應用程式 Log（不進 Git）
├─ backup/                    備份檔（不進 Git）
├─ run/                       PID 檔（不進 Git）
└─ cloudflare/                cloudflared.exe 與設定
```

---

## 架構設計

採 **Modular Monolith**，不做前後端分離、不引入訊息佇列或快取伺服器。這是家庭系統，簡單穩定比技術潮流重要。

```
Browser
   ↓  HTML Form (POST → Redirect → GET)
Routes (Blueprint)          ← 只做參數轉換與畫面選擇
   ↓
Services                    ← 商業邏輯與交易邊界都在這一層
   ↓
Models (SQLAlchemy ORM)
   ↓
SQLite (WAL)
```

### 分層原則

- **Routes** 不放商業邏輯，只負責表單驗證、呼叫 Service、決定要 render 什麼。
- **Services** 是唯一控制 `db.session.commit()` 的地方，一個動作 = 一個交易。
- 沒有為了模仿 Java 而建立一大堆空的 Repository class，SQLAlchemy 本身就是 ORM。

### Service 一覽

| Service | 負責 |
|---|---|
| `child_service` | 小孩 CRUD、PIN、頭像、主題 |
| `task_service` | 任務範本、星期排程、指派對象 |
| `assignment_service` | 當日任務產生、送出、審核、進度、連續天數 |
| `point_service` | **點數帳本**、餘額、歷史累積、集點卡、手動調整 |
| `reward_service` | 禮物 CRUD |
| `redemption_service` | 兌換申請、審核、庫存 |
| `calendar_service` | 行事曆月統計 |
| `audit_service` | 稽核紀錄 |
| `notification_service` | 小孩通知（慶祝畫面只播一次） |
| `achievement_service` | 成就解鎖 |
| `backup_service` | SQLite 安全備份 |
| `admin_service` | 管理員帳號、密碼 |

### Admin 與 Child 權限隔離

兩者刻意用**不同機制**，避免權限混淆：

| | Admin | Child |
|---|---|---|
| 機制 | Flask-Login (`current_user`) | 獨立 session key `child_id` |
| 裝飾器 | `@admin_required` | `@child_required` |

小孩的 session 永遠不會變成 Admin 身分。小孩手動輸入 `/admin` 會被導向管理員登入頁，不是靠「畫面上沒有按鈕」。

---

## 資料庫 Schema

```
AdminUser                    Child
  id                           id
  username (unique)            name, nickname, avatar, birthday
  password_hash                theme, pin_hash
  must_change_password         active
  active, last_login_at        created_at, updated_at
                                 │
Task ────────┬─── TaskSchedule   │
  id         │      task_id      │
  title      │      weekday      │
  icon       │                   │
  category   └─── TaskAssignee ──┤
  points            task_id      │
  required          child_id     │
  repeat_type                    │
  start_date                     │
  end_date         TaskAssignment│
  active             id ─────────┤
                     task_id     │
                     child_id ───┤
                     assignment_date
                     task_title_snapshot   ← 當時的名稱
                     task_icon_snapshot
                     points_snapshot
                     status
                     earned_points
                     rejection_reason
                     UNIQUE(task_id, child_id, assignment_date)
                       │
                       ↓ 批准時產生
                  PointTransaction         ← 唯一的點數事實來源
                     id                    │
                     child_id ─────────────┤
                     transaction_type      │
                     points  (可正可負)     │
                     source_type           │
                     source_id             │
                     description           │
                     UNIQUE(source_type, source_id, transaction_type)
                       ↑
Reward ─── RewardRedemption                │
  id         id                            │
  name       child_id ─────────────────────┤
  icon       reward_id                     │
  points_required                          │
  quantity   reward_name_snapshot  ← 當時的名稱
  active     points
             status
             requested_at / approved_at / completed_at

AuditLog          Notification        Achievement ─── ChildAchievement
  actor_type        child_id            code             child_id
  actor_id          type                name             achievement_id
  action            title, message      threshold        unlocked_at
  entity_type       points
  entity_id         read_at
  description
```

### 重要的資料庫層保護

| Constraint | 防止什麼 |
|---|---|
| `UNIQUE(source_type, source_id, transaction_type)` | **重複加點**。同一個任務不可能有第二筆 EARN |
| `UNIQUE(task_id, child_id, assignment_date)` | 同一天同一任務重複產生 |
| `CHECK(points <> 0)` | 沒有意義的 0 點交易 |
| `CHECK(points BETWEEN 1 AND 100)` | 任務點數超出範圍 |
| `CHECK(status IN (...))` | 不合法的狀態值 |
| `FOREIGN KEY` + `PRAGMA foreign_keys=ON` | 孤兒資料 |

### 索引

```
task_assignment(child_id, assignment_date)
task_assignment(status)
task_assignment(status, assignment_date)
point_transaction(child_id, created_at)
point_transaction(child_id, transaction_type)
reward_redemption(child_id, requested_at)
reward_redemption(status)
audit_log(created_at)
```

### Snapshot：為什麼歷史不會被改掉

`TaskAssignment` 與 `RewardRedemption` 都保存了當次的名稱、圖示與點數。

所以即使任務「整理玩具」後來被改名成「整理房間」，**昨天的歷史紀錄仍然顯示「整理玩具」**。這一點很重要 —— 歷史不該因為範本改動而被改寫。

---

## 點數計算規則

系統有**兩個不同的點數概念，絕對不能混用**。

### Current Balance（目前餘額）

```
Current Balance = SUM(所有 PointTransaction.points)
```

- **用途**：兌換禮物
- 會因為兌換禮物而減少
- 永遠即時由帳本重算，**不信任任何 cache 欄位**
- 預設不允許低於 0（可由 `reward.allow_negative_balance` 調整）

### Lifetime Earned（歷史累積取得）

```
Lifetime Earned = SUM(transaction_type IN ('EARN','BONUS') 的 points)
```

- **用途**：集點卡里程碑
- **不會**因為兌換禮物而減少

### 為什麼集點卡要用 Lifetime Earned

如果集點卡用目前餘額計算，小孩兌換一個 10 點的禮物之後，「我已經完成 3 張集點卡」會瞬間倒退成 2 張 —— 感覺就像努力被拿走了。

用 Lifetime Earned 就不會有這個問題：

```
累積取得 23 點，points_per_card = 10
  → 已完成 2 張集點卡
  → 目前第 3 張 3 / 10

兌換一個 10 點禮物後
  → 目前餘額 13 → 3
  → 已完成的集點卡仍然是 2 張   ✅ 不倒退
  → 累積取得仍然是 23 點        ✅ 不倒退
```

這個規則同時寫在 README、`point_service.py` 的模組註解，以及測試 `test_card_progress_does_not_regress_after_redeem` 裡，避免未來有人改錯。

### 交易類型

| 類型 | 說明 | 計入 Lifetime Earned |
|---|---|---|
| `EARN` | 完成任務取得 | ✅ |
| `BONUS` | 家長額外獎勵 | ✅ |
| `REDEEM` | 兌換禮物（負數） | ❌ |
| `ADJUST` | 家長修正（可負） | ❌ |
| `DEDUCT` | 保留 | ❌ |

### 禁止的寫法

```python
# ❌ 絕對不要這樣做
child.points += 2

# ✅ 一律新增帳本紀錄
point_service.add_transaction(
    child_id=child.id,
    transaction_type=TransactionType.EARN,
    points=2,
    source_type=SourceType.TASK_ASSIGNMENT,
    source_id=assignment.id,
    description="完成「整理玩具」",
)
```

點數雖然不是錢，但一律當成記帳系統設計：**不可重複、不可憑空消失、不可偷偷修改歷史、必須有來源、必須有原因**。

---

## 任務審核流程

```
                    TODO
                      │
        小孩按「我完成了！」
                      ↓
            WAITING_APPROVAL
                      │
            ┌─────────┴─────────┐
       家長批准              家長退回
            ↓                   ↓
        APPROVED            REJECTED
            │                   │
   ┌────────┴────────┐    不產生任何點數
   │ 新增 EARN 交易   │          │
   │ 建立慶祝通知     │    小孩可以再送出一次
   │ 寫入稽核紀錄     │     （回到 WAITING_APPROVAL）
   └─────────────────┘
   全部在同一個 transaction 內
```

### 防止重複加點（雙重保護）

家長手滑連按兩次「完成」時：

1. **程式層**：`approve_assignment()` 先檢查狀態必須是 `WAITING_APPROVAL`，已經是 `APPROVED` 就拋出「這個任務已經確認過囉！」
2. **資料庫層**：即使兩個請求同時通過檢查，第二筆 INSERT 也會撞上 `UNIQUE(source_type, source_id, transaction_type)` 而失敗

結果一定是 **+2，不會是 +4**。兩層保護缺一不可。

### 當日任務怎麼產生

不會每天預先複製大量資料。`TaskAssignment` 採「按需產生」：小孩開啟當日頁面時，才依任務範本產生當天的紀錄。

搭配 `UNIQUE(task_id, child_id, assignment_date)`，即使同時開兩個瀏覽器也不會重複產生。

---

## 禮物兌換流程

```
小孩按「我要這個！」
        │
        │  ← 此時「不」扣點
        ↓
    REQUESTED
        │
    家長確認
        ↓
┌──────────────────────────────────┐
│ 同一個 transaction 內：            │
│                                  │
│  1. 重新計算 Balance              │
│     （不相信畫面上的舊數字）        │
│  2. 重新檢查 Reward 庫存           │
│  3. 新增 -points 的 REDEEM 交易   │
│  4. 扣庫存                        │
│  5. 更新狀態為 APPROVED           │
│  6. 建立通知與稽核紀錄             │
└──────────────────────────────────┘
        ↓
    APPROVED  ──（家長標記交付）──→  COMPLETED
```

### 為什麼要在交易內重新檢查

小孩申請時有 10 點，但家長按確認之前，點數可能已經被扣掉了。如果相信申請時的數字，餘額就會變成負數。

所以 `approve_redemption()` 一定在交易內重新算一次餘額與庫存：

- 點數不足 → 拒絕，並顯示「還差幾點」
- 庫存不足 → 拒絕，餘額不受影響

`quantity = NULL` 代表數量無限；`quantity = 2` 代表最多兌換兩次。

---

## 安全性

### 密碼與 PIN

- 一律使用 `werkzeug.security.generate_password_hash` 儲存
- **不使用** MD5 / 單純 SHA256 / 明碼
- 管理員密碼至少 8 個字元
- 小孩 PIN 預設 4 位數字，忘記只能由家長重設

### CSRF

全站啟用 `Flask-WTF` 的 `CSRFProtect`。所有會改資料的 POST（完成任務、批准、退回、兌換、新增、修改、停用、調整點數、備份）都有 CSRF Token。

**沒有**為了方便而全域關閉 CSRF。

### 授權

| 檢查層級 | 做法 |
|---|---|
| URL 層 | `@admin_required` / `@child_required`，小孩輸入 `/admin` 會被導向登入頁 |
| 物件層 | `assignment.child_id == current_child.id`，改 URL 拿不到別人的資料 |
| API 層 | `/api/calendar` 的 `child_id` **只信任 session**，小孩傳 query string 無效；只有 Admin 才能指定 `child_id` |

### 登入失敗防護

連續失敗 5 次（可設定）會暫時鎖定 5 分鐘。使用行程內記憶體實作，**沒有**為此引入 Redis。

管理員登入刻意不區分「帳號不存在」與「密碼錯誤」，避免帳號列舉。

### XSS

- Jinja2 自動跳脫保持啟用
- 所有使用者輸入（小孩名字、任務名稱、禮物名稱、說明）都用 `{{ value }}` 正常輸出
- 全專案**沒有**任意使用 `|safe`
- 頭像只能從系統提供的 Emoji 清單挑選；主題只能是系統定義的五種，**不接受使用者輸入任意 CSS**

### 安全性 Header

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: same-origin
Content-Security-Policy: default-src 'self'; ...; frame-ancestors 'none'
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

自行用 `after_request` 實作，沒有為了幾個 Header 引入額外套件。

### Session Cookie

```
HttpOnly    ✅ 一律啟用
SameSite    Lax
Secure      正式環境 + Cloudflare 啟用時才開（本機 http://localhost 仍可正常使用）
有效時間     12 小時（可設定）
```

### Reverse Proxy

Cloudflare Tunnel 啟用時使用 `ProxyFix(x_for=1, x_proto=1, x_host=1)`，只信任 **1 hop**，不盲目相信任意 Proxy Header。

### SQL Injection

全部使用 SQLAlchemy ORM 與參數化查詢，沒有任何字串拼接的 SQL。

### 資料刪除

| 資料 | 刪除方式 |
|---|---|
| Child / Task / Reward | 軟刪除（`active = false`） |
| PointTransaction | **禁止刪除** |
| AuditLog | **禁止刪除** |

### 不會記錄的東西

Log 與稽核紀錄中**絕對不會**出現：密碼、PIN、Session ID、CSRF Token、Secret Key、Cloudflare Token。

登入失敗只記錄「誰在什麼時候失敗」，不記錄嘗試的密碼內容。

### 錯誤頁面

500 頁面只顯示友善文案，**不顯示** Traceback、SQL、檔案路徑或任何機密。技術細節只寫進 `logs\family-reward.log`。

`/health` 只回傳 `{"status": "UP"}`，不洩漏資料庫路徑、Python 版本或作業系統資訊。

### 資料庫不可經由 HTTP 下載

`data\family-reward.db` 放在 `data\`，不在 `static\` 或 `templates\` 之下，Flask 不會提供該路徑的靜態檔案服務。

---

## Troubleshooting

### 找不到 Python

```
[錯誤] 找不到 Python。
```

安裝 Python 3.10 或更新版本：<https://www.python.org/downloads/>

安裝時**務必勾選 `Add Python to PATH`**，然後重新執行 `start.bat`。

### Port 8080 被占用

```
Port 8080 已被其他程式使用。
```

先確認是不是本系統已經在跑了 —— 打開 <http://127.0.0.1:8080> 看看。

如果是別的程式占用，改 `config\config.yaml`：

```yaml
server:
  port: 8090
```

查誰占用了 8080：

```bat
netstat -ano | findstr :8080
tasklist | findstr <上面查到的 PID>
```

### 已經在執行中

```
家庭任務集點樂園已經在執行中 ⭐
```

不要重複啟動。要重啟請先執行 `stop.bat`。

如果程式其實已經不在了（例如電腦強制關機），刪掉 `run\web.pid` 再啟動。

### SQLite database is locked

系統已經設定 WAL 與 `busy_timeout = 5000`，正常使用很少遇到。如果發生：

1. 確認沒有其他程式（例如 DB Browser for SQLite）開著 `data\family-reward.db`
2. 確認沒有同時跑兩份系統（`stop.bat` 後只啟動一次）
3. 檢查磁碟是否已滿

### Migration 失敗

```
資料庫更新失敗。
```

查看 `logs\family-reward.log` 的實際錯誤。常見原因：

- `data\` 目錄沒有寫入權限 → 檢查資料夾權限，或不要把專案放在 `C:\Program Files\` 之下
- 資料庫檔案損壞 → 執行 `restore.bat` 從備份還原

### 無法開啟資料庫

```
無法開啟資料庫。

請確認 data 目錄存在，而且目前使用者有寫入權限。
```

把專案移到使用者有完整權限的位置，例如 `C:\family-reward\`，避免放在 `C:\Program Files\` 或唯讀的網路磁碟。

### Cloudflare 無法連線

1. 確認 `cloudflare\cloudflared.exe` 存在
2. 確認 `cloudflare\config.yml` 存在且 Tunnel ID 正確
3. 確認 `config.yml` 的 `service` 指向的 port 與 `config.yaml` 的 `server.port` 一致
4. 手動測試：

   ```bat
   cloudflare\cloudflared.exe tunnel --config cloudflare\config.yml run
   ```

即使 Tunnel 失敗，本機 <http://127.0.0.1:8080> 仍然可以正常使用。

### cloudflared.exe 找不到

```
⚠️ 找不到 cloudflared：...\cloudflare\cloudflared.exe
```

從 Cloudflare 官方下載 Windows 版放進 `cloudflare\`；或在 `config\config.yaml` 把 `cloudflare.enabled` 設為 `false`。

### 忘記 Admin Password

沒有「忘記密碼」信件功能（家庭系統刻意不接 Email）。請用以下方式重設：

1. 執行 `stop.bat`
2. 執行 `backup.bat`（保險）
3. 執行：

   ```bat
   .venv\Scripts\python.exe -c "from family_reward import create_app; from family_reward.extensions import db; from family_reward.models import AdminUser; app=create_app(); ctx=app.app_context(); ctx.push(); a=db.session.execute(db.select(AdminUser)).scalars().first(); a.set_password('新密碼至少8字'); db.session.commit(); print('已重設：', a.username)"
   ```

4. 執行 `start.bat`，用新密碼登入，然後到「⚙️ 設定」改成自己記得的密碼

### config.yaml 格式錯誤

```
config.yaml 格式錯誤，無法解析：...
```

YAML 對縮排很敏感。常見錯誤：

- 用了 Tab 縮排（**必須用空白**）
- 冒號後面沒有空白（要寫 `port: 8080`，不是 `port:8080`）
- 中文字串沒有引號包起來

可以貼到線上 YAML 驗證工具檢查，或從 Git 還原這個檔案。

### 忘記小孩的 PIN

家長登入後台 → 👧 小孩 → 修改 → 填新的 PIN → 儲存。

### 雙擊 start.bat 直接閃退，或 stop.bat 出現亂碼

症狀類似這樣：

```
'??璅?' 不是內部或外部命令、可執行的程式或批次檔。
'exe" set "PYTHON' 不是內部或外部命令、可執行的程式或批次檔。
```

**原因**：`cmd.exe` 是用「系統 ANSI 代碼頁」讀取 .bat 檔本身。台灣的 Windows
通常是 CP950（Big5），如果 .bat 檔裡有 UTF-8 中文，即使開頭寫了 `chcp 65001`
也來不及 —— 檔案前段的位元組早就被當成 Big5 誤判，導致畫面亂碼、指令被拆壞。

**解法**：本專案的 .bat 一律保持**純 ASCII + CRLF 換行**，所有中文訊息改由
`scripts\msg.py` 輸出（那時 `chcp 65001` 已經生效）。

如果你自己修改過 .bat 並加了中文，請把中文移到 `scripts\msg.py`。
可以用這個指令檢查：

```bat
.venv\Scripts\python.exe -m pytest tests/integration/test_bat_files.py
```

另外，如果是從 Git clone 下來的，`.gitattributes` 會確保 .bat 仍然是 CRLF。

### 中文顯示亂碼

所有檔案都是 UTF-8，BAT 開頭有 `chcp 65001`。如果 Windows 主控台仍然亂碼，改用 Windows Terminal，或直接看瀏覽器畫面（瀏覽器不會有這個問題）。

### 畫面沒有樣式 / 動畫怪怪的

強制重新整理清快取：`Ctrl + Shift + R`。

如果是動畫「都不動」，檢查作業系統是否開啟了「減少動態效果」—— 系統會主動尊重 `prefers-reduced-motion` 設定，這是預期行為。

---

## 已知限制

1. **單一家庭、單一管理者角色**
   目前只有一種管理者權限，沒有「爸爸」「媽媽」分開的帳號權限差異，也沒有多家庭隔離。

2. **Cloudflare Tunnel 未經實際憑證驗證**
   Cloudflare 的設定檔範本、啟動流程、失敗處理與 PID 管理都已完成並測試過（包含「找不到執行檔」「設定檔不存在」「啟動後立刻結束」三種失敗情境），但**在沒有實際 Tunnel Credentials 的情況下，無法驗證外部網域真的可以連線**。這部分需要你自己申請 Tunnel 後實測。

3. **Rate Limit 存在記憶體中**
   登入失敗次數記在行程記憶體，重新啟動就歸零。家庭系統夠用，但不是分散式方案。

4. **沒有音效**
   `ui.sound_enabled` 預設 `false`，第一版沒有實作音效播放。

5. **成就只有四個**
   已建立完整的 Achievement / ChildAchievement 資料表與解鎖機制，目前提供四個成就（第一步、小小努力家、連續達人、百點高手）。要新增成就需要在 `achievement_service.py` 補判斷規則。

6. **行事曆是自行實作，非 FullCalendar**
   需求書允許使用 FullCalendar，但這裡只需要「一個月 + 每天幾個數字」，自行實作反而更小更快，也不依賴 CDN 是否連得上。功能上完全滿足月視圖與點日期看明細的需求。

7. **Python 3.10 開發驗證**
   需求書寫 3.12+，本機只有 3.10.11。程式碼相容 3.10 以上並在 3.10.11 完成全部測試；在 3.12 上應可直接執行，但未在 3.12 上實測。

8. **沒有 Portable Python**
   `start.bat` 已經預留 `runtime\python.exe` 的優先偵測邏輯，但沒有實際打包免安裝的 Python runtime。

9. **備份沒有自動排程**
   需要手動執行 `backup.bat` 或從後台按「立即備份」。超過設定天數會在後台提醒，但不會自動備份。若想自動化，可用 Windows 工作排程器定時執行 `backup.bat`。

---

## 未來可以擴充的項目

架構已經預留，但第一版刻意不做（避免增加複雜度）：

- **LINE 通知** —— 任務待審核、兌換申請時通知家長
- **PWA** —— 加到手機主畫面、離線瀏覽
- **多位家長帳號** —— 爸爸／媽媽分開，並記錄是誰批准的（`approved_by` 欄位已存在）
- **多家庭** —— 目前 schema 沒有 family_id，需要調整
- **更多成就與徽章** —— 資料表與機制都已具備
- **季節活動 / 生日主題** —— 生日欄位與主題機制已存在
- **每日挑戰 / 排行榜**
- **照片任務證明** —— 需要先處理檔案上傳的資安問題（第一版刻意避開）
- **AI 任務建議**
- **統計圖表** —— 每週／每月趨勢

第一版的重點是把**任務、審核、點數、禮物、行事曆、Windows 啟動、Cloudflare** 做到非常穩定。

---

## 授權與隱私

這是家庭自用系統。刻意**不蒐集**：身分證、學校、地址、電話、真實照片。

小孩的資料只有名字、暱稱、Emoji 頭像、選填的生日，以及 Hash 過的 PIN。

`data\family-reward.db` 含有家庭資料，**禁止提交 Git 或上傳到公開空間**（已加入 `.gitignore`）。
