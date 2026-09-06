# 專案名稱

家庭任務集點樂園  
Family Reward / Kids Chore Reward System

---

# 0. 開發任務總指令

你是一位資深 Python Full Stack 軟體架構師、Flask 工程師、UI/UX 設計師、資料庫工程師與 Web 資安工程師。

我要你從零開始，完整設計並實作一套：

「兒童家庭任務集點與獎勵系統」

這不是單純的 Prototype，也不是只要展示畫面的 Demo。

這套系統完成後，我會真的放在家裡的 Windows 電腦執行，讓家長與小孩每天使用。

請直接進行實作，不要只告訴我「可以怎麼做」。

如果你有目前專案工作目錄的檔案操作權限，請直接：

```text
建立檔案
→
撰寫程式
→
建立資料庫
→
啟動程式
→
執行測試
→
發現錯誤
→
修正
→
重新測試
```

直到專案可以實際執行。

除非遇到會重大影響產品方向的決策，否則不要一直詢問我。

對於：

- 檔名
- Python package 名稱
- CSS 結構
- Service 如何拆分
- Repository 如何設計
- DTO / Form 命名
- 小型 UI 細節

請自行採用合理且容易維護的設計。

---

# 1. 產品核心概念

我要做一個家庭使用的任務集點網站。

家長可以替小孩安排每天要完成的事情。

例如：

```text
🪥 自己刷牙       +1 ⭐
📚 寫完功課       +2 ⭐
🧸 整理玩具       +2 ⭐
🗑️ 幫忙倒垃圾     +2 ⭐
🛏️ 整理房間       +3 ⭐
🚿 自己去洗澡      +1 ⭐
```

小孩完成後，可以按：

```text
我完成了！
```

但是不可以馬上取得點數。

流程必須是：

```text
小孩完成任務
↓
送出完成申請
↓
家長確認
↓
任務正式完成
↓
取得點數
```

點數累積之後，可以用來兌換：

```text
🍦 吃冰淇淋
🎮 多玩 30 分鐘遊戲
🍿 決定今天看的電影
🧸 小玩具
🍕 選星期六晚餐
🎡 去遊樂園
```

預設以：

```text
10 點
```

作為一個重要集點里程碑。

但是「歷史集滿幾張卡」以及「目前可以消費的點數餘額」必須分開處理。

---

# 2. 技術架構

固定採用以下技術。

## Backend

```text
Python 3.12+
Flask
SQLAlchemy
Flask-SQLAlchemy
Flask-Login
Flask-WTF
WTForms
Flask-Migrate / Alembic
```

## Database

```text
SQLite
```

## Template

```text
Jinja2
```

## Frontend

```text
HTML5
CSS3
Bootstrap 5
Vanilla JavaScript
```

可以使用：

```text
FullCalendar
```

來處理月曆。

若需要 Confetti 動畫，可以使用輕量 JavaScript 套件或自行實作。

禁止要求：

```text
React
Vue
Angular
Node.js
npm
Webpack
Vite
Docker
```

這是一個小型家庭 Web App，不需要前後端分離。

---

# 3. Web Server

開發環境可以使用：

```text
Flask development server
```

正式 Windows 執行時：

禁止直接使用 Flask Development Server。

正式環境請使用：

```text
Waitress
```

例如：

```text
waitress-serve
```

或 Python API 啟動 Waitress。

架構：

```text
Browser
↓
Cloudflare
↓
Cloudflare Tunnel
↓
Waitress
↓
Flask
↓
SQLite
```

---

# 4. 專案主要目標

系統必須做到：

1. 家長建立小孩資料
2. 家長建立任務
3. 指派任務給小孩
4. 設定任務日期與週期
5. 小孩查看今日任務
6. 小孩送出完成申請
7. 家長審核
8. 審核通過才增加點數
9. 可以查看歷史點數
10. 可以顯示集點卡
11. 每 10 點產生一個視覺里程碑
12. 家長可以建立禮物
13. 小孩可以申請兌換禮物
14. 家長批准後扣除點數
15. 有行事曆
16. 有動畫
17. 有友善文案
18. 支援手機、平板、桌機
19. Windows 可以一鍵啟動
20. SQLite 資料關閉程式後仍然存在
21. 可以經由 Cloudflare 網域安全公開

---

# 5. 整體設計原則

這是一個家庭系統，不是企業 ERP。

請遵守：

```text
簡單
穩定
容易維護
容易備份
容易搬家
容易啟動
資料不能亂
權限不能亂
不 Over Engineering
```

禁止引入：

```text
Redis
RabbitMQ
Kafka
Elasticsearch
Celery
Kubernetes
Microservices
API Gateway
Message Queue
MongoDB
PostgreSQL
MySQL
```

除非未來有非常明確的必要。

目前採：

```text
Modular Monolith
```

---

# 6. Python Package 管理

使用：

```text
requirements.txt
```

至少包含需要的套件，例如：

```text
Flask
Flask-SQLAlchemy
Flask-Login
Flask-WTF
WTForms
Flask-Migrate
SQLAlchemy
Alembic
waitress
PyYAML
python-dotenv
pytest
pytest-flask
```

實際版本請選擇彼此相容且穩定的版本。

不要隨意依賴大量第三方 package。

能用 Python 標準函式庫處理的簡單工作就使用標準函式庫。

---

# 7. Python 虛擬環境

Windows 專案使用：

```text
.venv
```

第一次執行：

```text
start.bat
```

如果：

```text
.venv
```

不存在：

自動執行：

```text
python -m venv .venv
```

接著安裝：

```text
requirements.txt
```

以後啟動不要每次重新安裝所有套件。

可以使用：

```text
requirements.lock
```

或 hash / marker 機制判斷 dependencies 是否改變。

但第一版保持簡單即可。

---

# 8. Windows 最終使用方式

理想情況：

```text
C:\family-reward\
```

使用者只需要：

```text
雙擊 start.bat
```

即可啟動。

不需要：

```text
flask run
pip install
python app.py
alembic upgrade head
```

這些事情應該由啟動流程處理。

---

# 9. 最終目錄結構

希望接近：

```text
family-reward/
│
├─ start.bat
├─ stop.bat
├─ backup.bat
├─ restore.bat
├─ requirements.txt
├─ app.py
│
├─ config/
│  └─ config.yaml
│
├─ family_reward/
│  ├─ __init__.py
│  ├─ config.py
│  ├─ extensions.py
│  │
│  ├─ models/
│  │  ├─ __init__.py
│  │  ├─ admin_user.py
│  │  ├─ child.py
│  │  ├─ task.py
│  │  ├─ task_assignment.py
│  │  ├─ point_transaction.py
│  │  ├─ reward.py
│  │  ├─ reward_redemption.py
│  │  └─ audit_log.py
│  │
│  ├─ routes/
│  │  ├─ auth.py
│  │  ├─ public.py
│  │  ├─ child.py
│  │  ├─ admin.py
│  │  └─ api.py
│  │
│  ├─ services/
│  │  ├─ child_service.py
│  │  ├─ task_service.py
│  │  ├─ assignment_service.py
│  │  ├─ point_service.py
│  │  ├─ reward_service.py
│  │  ├─ redemption_service.py
│  │  ├─ calendar_service.py
│  │  └─ audit_service.py
│  │
│  ├─ forms/
│  ├─ security/
│  ├─ utils/
│  └─ exceptions/
│
├─ templates/
│  ├─ base.html
│  ├─ public/
│  ├─ child/
│  ├─ admin/
│  ├─ auth/
│  ├─ error/
│  └─ components/
│
├─ static/
│  ├─ css/
│  ├─ js/
│  ├─ icons/
│  └─ img/
│
├─ migrations/
│
├─ tests/
│
├─ data/
│  └─ family-reward.db
│
├─ logs/
│  └─ family-reward.log
│
├─ backup/
│
├─ run/
│
└─ cloudflare/
   ├─ cloudflared.exe
   └─ config.yml
```

如果實際開發時有更合理的結構，可以調整，但不要變得過度複雜。

---

# 10. 設定檔

所有會依環境改變的參數，禁止寫死在 Python 程式。

使用：

```text
config/config.yaml
```

例如：

```yaml
server:
  host: "127.0.0.1"
  port: 8080
  threads: 8

app:
  name: "家庭任務集點樂園"
  timezone: "Asia/Taipei"
  debug: false

database:
  path: "./data/family-reward.db"

reward:
  points_per_card: 10

security:
  session_timeout_hours: 12
  child_pin_length: 4

admin:
  initial_username: "admin"

cloudflare:
  enabled: false
  executable: "./cloudflare/cloudflared.exe"
  config: "./cloudflare/config.yml"

logging:
  path: "./logs/family-reward.log"
  level: "INFO"

backup:
  directory: "./backup"
  reminder_days: 7
```

敏感資訊不要直接寫 config.yaml。

例如：

```text
Admin Initial Password
Secret Key
Cloudflare Token
```

可以使用：

```text
.env
```

並提供：

```text
.env.example
```

---

# 11. Secret

至少：

```text
FLASK_SECRET_KEY
ADMIN_INITIAL_PASSWORD
```

從：

```text
.env
```

讀取。

`.env` 必須加入：

```text
.gitignore
```

禁止提交 Git。

---

# 12. 時區

固定預設：

```text
Asia/Taipei
```

所有顯示日期與任務判斷必須使用台灣時間。

Python 優先使用：

```python
zoneinfo.ZoneInfo("Asia/Taipei")
```

不要額外安裝 pytz，除非真的有必要。

---

# 13. 小孩資料

Child 至少包含：

```text
id
name
nickname
avatar
birthday
theme
pin_hash
active
created_at
updated_at
```

其中：

```text
birthday
```

允許 NULL。

不要蒐集：

```text
身分證
學校
地址
電話
真實照片
```

---

# 14. 小孩 Avatar

第一版不提供任意圖片上傳。

提供 Emoji 選擇：

```text
🐶
🐱
🐰
🦊
🐼
🦁
🐯
🐸
🐨
🦄
🐙
🐧
🐻
🐹
```

這樣可以避免：

```text
File Upload Security
Storage 管理
圖片壓縮
MIME 驗證
```

---

# 15. Theme

每個小孩可以選 Theme：

```text
SUNNY
OCEAN
FOREST
CANDY
SPACE
```

Theme 必須由系統提供。

禁止允許使用者輸入任意 CSS。

---

# 16. 小孩登入

不要要求小孩記：

```text
帳號 + 密碼
```

採用：

```text
Profile Selection
+
4 位 PIN
```

首頁：

```text
今天是誰要開始冒險呢？ 🌈

🐼 小明

🦄 小美
```

選擇：

```text
🐼 小明
```

再輸入：

```text
● ● ● ●
```

PIN 不可以明碼儲存。

必須 Hash。

可以使用：

```python
werkzeug.security.generate_password_hash
werkzeug.security.check_password_hash
```

---

# 17. Admin 登入

家長後台：

```text
/admin
```

必須要求登入。

AdminUser：

```text
id
username
password_hash
active
last_login_at
created_at
updated_at
```

密碼禁止明碼。

使用：

```python
werkzeug.security.generate_password_hash
```

或等效安全方案。

---

# 18. 初始 Admin

第一次啟動時，如果沒有 Admin：

讀取：

```text
ADMIN_INITIAL_PASSWORD
```

以及：

```yaml
admin:
  initial_username: admin
```

建立管理者。

第一次登入後，介面必須提醒：

```text
⚠️ 請修改預設管理員密碼。
```

---

# 19. Flask Login

使用：

```text
Flask-Login
```

管理登入 Session。

但是 Admin 與 Child 權限不能混亂。

要有明確角色判斷。

例如：

```text
ADMIN
CHILD
```

可以：

- 使用不同 Session Key
- 或建立統一 Principal
- 或建立自己的 decorator

只要安全且容易維護即可。

---

# 20. CSRF

使用：

```text
Flask-WTF
CSRFProtect
```

所有會改資料的 POST：

```text
完成任務
批准
退回
兌換
新增
修改
停用
調整點數
```

都必須有 CSRF Protection。

禁止為了方便直接全域關閉 CSRF。

---

# 21. Task

Task 至少：

```text
id
title
description
icon
category
points
repeat_type
start_date
end_date
active
created_at
updated_at
```

---

# 22. 任務分類

TaskCategory：

```text
HOUSEWORK
HOMEWORK
HYGIENE
HABIT
BEHAVIOR
OTHER
```

UI 顯示：

```text
🧹 家事
📚 功課
🪥 生活習慣
🌱 習慣養成
❤️ 好行為
⭐ 其他
```

---

# 23. Repeat Type

至少：

```text
ONCE
DAILY
WEEKLY
CUSTOM
```

CUSTOM 可以選：

```text
MON
TUE
WED
THU
FRI
SAT
SUN
```

如果需要額外 table 儲存 Schedule，請自行設計合理結構。

---

# 24. 任務排程

請避免每天真的複製大量 Task。

可以設計：

```text
Task
+
TaskSchedule
+
TaskAssignment
```

Task 表示：

```text
任務範本
```

TaskAssignment 表示：

```text
某一天實際發生的任務
```

例如：

```text
Task:
刷牙

Schedule:
DAILY

2026/09/06
TaskAssignment #123

2026/09/07
TaskAssignment #124
```

需要避免同一天重複產生同一任務。

可使用 Unique Constraint。

---

# 25. TaskAssignment

至少：

```text
id
task_id
child_id
assignment_date
status
submitted_at
completed_at
approved_at
approved_by
earned_points
rejection_reason
created_at
updated_at
```

status：

```text
TODO
WAITING_APPROVAL
APPROVED
REJECTED
```

---

# 26. 任務完成流程

流程固定：

```text
TODO
↓
小孩按「我完成了！」
↓
WAITING_APPROVAL
↓
家長審核
↓
APPROVED / REJECTED
```

APPROVED：

```text
新增 PointTransaction
```

REJECTED：

```text
不增加任何點數
```

---

# 27. 小孩完成任務 UI

按：

```text
我完成了！
```

成功後：

```text
太棒了！🎉

已經把任務送給爸爸媽媽確認囉！

確認完成後，星星就會跑進你的集點卡 ⭐
```

送出後：

Button Disable。

避免重複提交。

---

# 28. 家長待審核

Admin：

```text
/admin/approvals
```

顯示：

```text
👦 小明

🧸 整理玩具

完成時間：
19:35

可以獲得：
+2 ⭐

[完成 👍]

[還要再努力一下]
```

---

# 29. 退回任務

家長退回時可以輸入：

```text
玩具還有一些在地上喔～
再整理一下就完成啦！ 💪
```

狀態：

```text
REJECTED
```

小孩可以在畫面看到友善提醒。

也可以允許：

```text
重新完成
```

將狀態恢復為：

```text
TODO
```

或允許 REJECTED 再送出。

請選擇一致且容易理解的流程。

---

# 30. 點數資料模型

禁止只建立：

```text
child.points
```

然後直接：

```python
child.points += 2
```

這種設計。

一定使用 Ledger：

```text
PointTransaction
```

---

# 31. PointTransaction

至少：

```text
id
child_id
transaction_type
points
source_type
source_id
description
created_at
```

transaction_type：

```text
EARN
DEDUCT
REDEEM
ADJUST
BONUS
```

points 可以：

```text
正數
負數
```

例如：

```text
+2 完成「整理玩具」

+1 完成「刷牙」

+5 今天主動幫忙

-10 兌換「吃冰淇淋」
```

---

# 32. 點數餘額

目前點數：

```text
SUM(PointTransaction.points)
```

禁止只相信 Cache 欄位。

如果未來為效能增加 Cache Balance：

Ledger 仍然必須是 Source of Truth。

---

# 33. 防止重複加點

這是非常重要的資料一致性規則。

如果家長：

快速按兩次 Approved。

不可以：

```text
+2
+2
```

一定只能：

```text
+2
```

請在資料庫層與程式層雙重保護。

例如建立 Unique Constraint：

```text
source_type
source_id
transaction_type
```

對完成任務：

```text
source_type = TASK_ASSIGNMENT
source_id = assignment_id
transaction_type = EARN
```

不得存在兩筆。

---

# 34. Database Transaction

所有：

```text
Approve Task
Redeem Reward
Manual Adjustment
Cancel Redemption
```

涉及多筆資料修改的流程：

必須在同一個 SQLAlchemy Transaction 中完成。

例如：

```python
try:
    ...
    db.session.commit()
except Exception:
    db.session.rollback()
    raise
```

不得：

```text
先修改 Task
commit

再新增 Points
commit
```

避免一半成功一半失敗。

---

# 35. Reward

Reward：

```text
id
name
description
icon
points_required
quantity
active
created_at
updated_at
```

例如：

```text
🍦 吃冰淇淋
10 ⭐

🎮 玩遊戲 30 分鐘
10 ⭐

🍿 選今晚看的電影
10 ⭐

🧸 小玩具
20 ⭐

🍕 選星期六晚餐
25 ⭐

🎡 去遊樂園
50 ⭐
```

---

# 36. Reward Quantity

quantity：

允許：

```text
NULL
```

代表：

```text
無限
```

如果：

```text
quantity = 2
```

則最多可使用兩次。

數量減少也必須使用 Transaction。

避免併發兌換超賣。

---

# 37. 禮物頁面

小孩：

```text
🎁 我的禮物

目前：
13 ⭐

--------------------

🍦 吃冰淇淋

需要：
10 ⭐

[我要這個！]

--------------------

🧸 小玩具

需要：
20 ⭐

🔒 還差 7 ⭐
```

---

# 38. Reward Redemption

至少：

```text
id
child_id
reward_id
points
status
requested_at
approved_at
completed_at
cancelled_at
```

status：

```text
REQUESTED
APPROVED
COMPLETED
CANCELLED
REJECTED
```

---

# 39. 禮物兌換流程

固定：

```text
小孩提出申請
↓
REQUESTED
↓
家長確認
↓
檢查目前點數
↓
確認 Reward 有庫存
↓
新增 -points PointTransaction
↓
APPROVED
```

不要讓小孩按一次就直接扣點。

---

# 40. 點數不足

如果：

```text
目前只有 7 點
```

要兌換：

```text
10 點
```

不得成功。

後端一定要重新檢查。

不能只依靠前端 Disabled Button。

顯示：

```text
再收集 3 顆星星就可以換這個禮物囉！💪
```

---

# 41. 集點卡

這是整個 UI 最重要的元件之一。

預設：

```text
10 點一張
```

例如：

```text
🌟 我的集點卡

⭐ ⭐ ⭐ ⭐ ⭐
⭐ ⭐ ○ ○ ○

7 / 10

再 3 顆星星就完成一張啦！
```

---

# 42. 集點里程碑

設定：

```yaml
reward:
  points_per_card: 10
```

例如：

歷史累積 Earned Points：

```text
23
```

表示：

```text
已經完成 2 張集點卡
目前第 3 張 3 / 10
```

注意：

這個里程碑最好使用：

```text
Lifetime Earned Points
```

而不是：

```text
Current Balance
```

因為小孩兌換禮物後，不應該讓「歷史完成過的集點卡」倒退。

---

# 43. 點數分成兩個概念

一定要明確區分：

## Current Balance

目前可以花的點數：

```text
SUM(All PointTransactions)
```

例如：

```text
13
```

## Lifetime Earned

歷史總共賺到的正向點數：

```text
EARN
BONUS
```

例如：

```text
73
```

兩者用途不同。

不要混用。

---

# 44. Dashboard

小孩 Dashboard：

```text
嗨，小明 👋

今天是 9 月 6 日 星期日

今天也一起完成任務吧！🌟

---------------------

⭐ 我的星星

目前：

17 ⭐

---------------------

🎯 集點卡

⭐ ⭐ ⭐ ⭐ ⭐
⭐ ⭐ ○ ○ ○

7 / 10

再 3 顆星星就完成一張啦！

---------------------

📋 今天的任務

🪥 刷牙

+1 ⭐

[我完成了！]


📚 寫功課

+2 ⭐

[我完成了！]


🧸 整理玩具

+2 ⭐

[我完成了！]

---------------------

🎁 下一個禮物

🍦 吃冰淇淋

需要：
10 ⭐

你現在已經可以兌換囉！
```

---

# 45. 行事曆

一定要有：

```text
📅 行事曆
```

支援月視圖。

可以使用：

```text
FullCalendar
```

但不要加入 Node build。

使用：

```text
CDN
```

或下載靜態資源到專案。

---

# 46. Calendar 顯示

例如：

```text
2026 年 9 月

9/6

✅ 4 / 5

⭐ +7
```

點進某一天：

```text
2026/09/06

✅ 刷牙          +1
✅ 寫功課        +2
✅ 整理玩具      +2
❌ 洗澡
✅ 倒垃圾        +2

今日：
+7 ⭐
```

---

# 47. Calendar API

例如：

```text
GET /api/calendar
```

參數：

```text
year
month
```

Child ID 不要完全相信 Query String。

Child 使用自己的登入 Session。

Admin 才允許指定：

```text
child_id
```

Response：

```json
[
  {
    "date": "2026-09-06",
    "totalTasks": 5,
    "approvedTasks": 4,
    "earnedPoints": 7
  }
]
```

---

# 48. Navigation

小孩：

```text
🏠 今天
📅 行事曆
🎁 禮物
⭐ 我的紀錄
```

手機版可以 Bottom Navigation。

---

# 49. Admin Navigation

```text
📊 首頁

👧 小孩

📋 任務

✅ 待確認

🎁 禮物

⭐ 點數

📜 歷史紀錄

⚙️ 設定
```

---

# 50. Admin Dashboard

顯示：

```text
今天

👧 小美

完成：
4 / 5

今天取得：
+7 ⭐


👦 小明

完成：
3 / 4

今天取得：
+5 ⭐

-----------------

待確認：

3 件

-----------------

待確認禮物：

1 件
```

---

# 51. 小孩管理

Admin：

```text
/admin/children
```

可以：

```text
新增
修改
停用
修改 PIN
更換 Avatar
更換 Theme
```

重要資料不要直接 Physical Delete。

使用：

```text
active = false
```

---

# 52. 任務管理

Admin：

```text
/admin/tasks
```

可以：

```text
新增任務
修改任務
停用任務
指定小孩
設定點數
設定開始日期
設定結束日期
設定週期
設定星期
設定分類
```

---

# 53. 禮物管理

Admin：

```text
/admin/rewards
```

可以：

```text
新增
修改
停用
調整需要點數
調整數量
```

---

# 54. 手動調整點數

Admin 可以：

```text
+5
```

理由：

```text
今天主動幫忙整理客廳
```

或者：

```text
-2
```

理由：

```text
修正昨天錯誤加點
```

但是禁止：

```python
child.points = 20
```

必須新增：

```text
PointTransaction
```

---

# 55. 點數歷史

小孩與家長可以查看：

```text
⭐ 點數紀錄

今天

+2
整理玩具

+1
自己刷牙


昨天

+5
主動幫忙

-10
兌換冰淇淋
```

---

# 56. Audit Log

另外建立：

```text
AuditLog
```

至少：

```text
id
actor_type
actor_id
action
entity_type
entity_id
description
created_at
```

例如：

```text
ADMIN

APPROVE_TASK

TASK_ASSIGNMENT

123

批准小明完成「整理玩具」
```

---

# 57. Audit 項目

至少記錄：

```text
LOGIN_FAILURE

CREATE_CHILD
UPDATE_CHILD

CREATE_TASK
UPDATE_TASK

SUBMIT_TASK

APPROVE_TASK
REJECT_TASK

MANUAL_POINT_ADJUSTMENT

CREATE_REWARD
UPDATE_REWARD

REQUEST_REWARD
APPROVE_REWARD
REJECT_REWARD

CHANGE_PASSWORD
```

---

# 58. Log

Application Log：

```text
logs/family-reward.log
```

要有：

```text
Application startup
Application shutdown
Warning
Exception
Login failure
Database error
Cloudflare 啟動錯誤
```

禁止記錄：

```text
Password
PIN
Session ID
CSRF Token
Secret
Cloudflare Token
```

---

# 59. SQLite

Database：

```text
data/family-reward.db
```

禁止放在：

```text
static/
templates/
```

否則可能被 Web 存取。

---

# 60. SQLite PRAGMA

每個 SQLite Connection 都必須合理設定：

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
```

也可以合理加入：

```sql
PRAGMA synchronous = NORMAL;
```

確保家庭同時幾人操作時不容易發生：

```text
database is locked
```

---

# 61. SQLite Connection Handling

使用 SQLAlchemy Event Listener。

例如：

```python
@event.listens_for(engine, "connect")
```

設定：

```text
foreign_keys
busy_timeout
```

WAL 可在初始化時設定。

不要每個 Request 用字串自己開 sqlite3 Connection。

---

# 62. Migration

必須有資料庫版本管理。

使用：

```text
Flask-Migrate
+
Alembic
```

不要在正式環境使用：

```text
db.create_all()
```

當作長期 Migration 方案。

第一次初始化可以透過：

```text
flask db upgrade
```

自動執行 Migration。

但是：

使用者不應該手動輸入。

由：

```text
start.bat
```

自動處理。

---

# 63. Migration 安全

啟動時：

```text
Migration success
→
啟動 Web Server
```

如果：

```text
Migration failure
```

不得繼續啟動 Application。

BAT 顯示：

```text
資料庫更新失敗。

請查看：

logs\family-reward.log
```

---

# 64. Backup

提供：

```text
backup.bat
```

不要直接在 SQLite 高寫入狀態下粗暴 Copy DB。

請採安全方式。

優先：

```text
SQLite Backup API
```

Python 標準函式庫：

```python
sqlite3.Connection.backup()
```

備份到：

```text
backup/
```

名稱：

```text
family-reward-20260906-213000.db
```

---

# 65. Admin Backup

Admin Dashboard：

顯示：

```text
最近備份：

2026/09/06 21:30

[立即備份]
```

如果超過：

```text
7 天
```

顯示：

```text
⚠️ 已經 8 天沒有備份囉
```

---

# 66. Restore

提供：

```text
restore.bat
```

Restore 前：

必須要求 Application 已停止。

不要直接覆蓋正在使用的 DB。

可以讓使用者選備份檔，或提供簡單明確的操作流程。

Restore 前先把目前 DB 再備份一次：

```text
pre-restore
```

---

# 67. Flask App Factory

專案使用：

```python
create_app()
```

App Factory Pattern。

例如：

```python
def create_app(config_path=None):
    app = Flask(__name__)

    ...

    return app
```

不要把所有初始化都塞在：

```text
app.py
```

---

# 68. extensions.py

例如：

```text
db
login_manager
csrf
migrate
```

統一初始化。

避免 Circular Import。

---

# 69. Blueprint

Routes 使用 Blueprint。

例如：

```text
public_bp
auth_bp
child_bp
admin_bp
api_bp
```

不要全部寫在：

```text
app.py
```

---

# 70. Service Layer

Route / Controller 不要塞大量 Business Logic。

至少：

```text
ChildService

TaskService

AssignmentService

PointService

RewardService

RedemptionService

CalendarService

AuditService

BackupService
```

---

# 71. Repository

SQLAlchemy 本身已經有 ORM。

不用為了模仿 Java 而建立一大堆毫無意義的 Repository Class。

如果查詢邏輯複雜：

可以建立：

```text
repositories/
```

否則 Service 直接使用 Model Query / SQLAlchemy Select。

保持 Pythonic。

---

# 72. Form

使用：

```text
Flask-WTF
WTForms
```

處理：

```text
ChildForm
TaskForm
RewardForm
AdminLoginForm
ChildPinForm
PointAdjustmentForm
```

---

# 73. Validation

例如：

```text
name:
1 ~ 50

task title:
1 ~ 100

points:
1 ~ 100

reward points:
1 ~ 10000

PIN:
4 位數
```

所有驗證：

前端做 UX。

後端做真正安全檢查。

不能只依賴 JavaScript。

---

# 74. DB Constraint

必要欄位必須在資料庫也有：

```text
NOT NULL
CHECK
UNIQUE
FOREIGN KEY
INDEX
```

不要只相信 WTForms。

---

# 75. Index

至少考慮：

```text
task_assignment(child_id, assignment_date)

task_assignment(status)

point_transaction(child_id, created_at)

reward_redemption(child_id, requested_at)

audit_log(created_at)
```

---

# 76. N+1 Query

Dashboard 不要：

```text
取得 Child
↓
每一個任務再 Query
↓
每一筆 Points 再 Query
↓
每一個 Reward 再 Query
```

必要時使用：

```text
joinedload
selectinload
aggregate query
```

避免 N+1。

---

# 77. Security Headers

至少設定：

```text
X-Content-Type-Options: nosniff

Referrer-Policy

Content-Security-Policy

Frame protection
```

可以自行實作 Flask after_request。

不要引入太重的套件只為了 Header。

---

# 78. XSS

Jinja 預設 Auto Escape 要保持啟用。

所有 User Input：

```text
Child Name
Task Name
Reward
Description
```

直接正常：

```jinja2
{{ value }}
```

禁止隨意：

```jinja2
|safe
```

---

# 79. Session Cookie

Production：

至少：

```text
HttpOnly
SameSite=Lax
```

因為 Cloudflare 對外是 HTTPS：

可以在正式模式設定：

```text
Secure=True
```

但本機：

```text
http://localhost
```

仍需能正常使用。

請依 Proxy / Production Mode 正確處理。

---

# 80. Reverse Proxy

Cloudflare Tunnel 會經 Proxy。

Flask / Waitress 要正確理解：

```text
X-Forwarded-Proto
X-Forwarded-For
```

使用：

```python
werkzeug.middleware.proxy_fix.ProxyFix
```

但不要完全信任任意 Proxy Header。

設定合理 hop 數量。

---

# 81. Cloudflare Tunnel

使用：

```text
Cloudflare Tunnel
```

架構：

```text
Internet

↓

https://kids.example.com

↓

Cloudflare

↓

Cloudflare Tunnel

↓

127.0.0.1:8080

↓

Waitress

↓

Flask
```

禁止要求：

```text
Router Port Forwarding
開放 Windows 8080
```

---

# 82. Host Binding

Waitress：

預設只綁：

```text
127.0.0.1
```

不要：

```text
0.0.0.0
```

除非設定檔明確允許。

因為 Cloudflare Tunnel 在同一台機器，只需要連：

```text
localhost
```

---

# 83. Cloudflare 設定

例如：

```yaml
tunnel: YOUR_TUNNEL_ID

credentials-file: C:/family-reward/cloudflare/YOUR_TUNNEL_ID.json

ingress:
  - hostname: kids.example.com
    service: http://127.0.0.1:8080

  - service: http_status:404
```

不要把：

```text
Tunnel Token
credentials json
```

提交 Git。

---

# 84. start.bat

最終最重要的檔案之一：

```text
start.bat
```

使用者只需要雙擊。

---

# 85. start.bat 流程

至少：

```text
1. 切換到 BAT 自己所在目錄

2. 設定 UTF-8

3. 建立：
   data
   logs
   backup
   run

4. 檢查：
   config\config.yaml

5. 找 Python

6. 如果 .venv 不存在：
   建立 venv

7. 安裝 / 更新必要套件

8. 執行 Alembic Migration

9. 啟動 Waitress

10. 記錄 Process

11. 如果 Cloudflare Enabled：
    啟動 cloudflared

12. 顯示：
    本機網址
    公開網址
    DB
    Log
```

---

# 86. BAT 顯示

例如：

```text
============================================

     家庭任務集點樂園 ⭐

============================================

正在啟動服務...

本機網址：

http://127.0.0.1:8080

SQLite：

data\family-reward.db

Log：

logs\family-reward.log

Cloudflare：

已啟動

公開網址：

https://kids.example.com

============================================
```

---

# 87. Python Detection

start.bat：

優先：

```text
.venv\Scripts\python.exe
```

如果 .venv 不存在：

檢查：

```text
py -3.12
```

再檢查：

```text
python
```

如果找不到：

清楚顯示：

```text
找不到 Python。

請先安裝 Python 3.12 或更新版本。

安裝時請勾選：

Add Python to PATH
```

不要讓 BAT 一閃就關掉。

---

# 88. Portable Python

第一版不一定要做。

但是架構要預留未來可以：

```text
runtime\python.exe
```

如果存在：

start.bat 優先使用 portable runtime。

順序：

```text
runtime\python.exe

↓

.venv

↓

py

↓

python
```

如此未來可以製作完全免安裝 Python 的版本。

---

# 89. stop.bat

提供：

```text
stop.bat
```

不能：

```bat
taskkill /F /IM python.exe
```

因為可能殺掉使用者其他 Python 程式。

---

# 90. PID 管理

啟動時記錄：

```text
run\web.pid
run\cloudflared.pid
```

停止時：

只關閉對應 PID。

也要驗證 PID 確實是這個 Application。

如果 BAT PID 管理很麻煩：

可以建立：

```text
scripts/process_manager.py
```

專門處理 Process 啟動 / 停止。

使用 Python 比純 BAT 更可靠。

但使用者介面仍然只有：

```text
start.bat
stop.bat
```

---

# 91. Application Launcher

建議建立：

```text
launcher.py
```

由：

```text
start.bat
```

執行。

launcher.py 負責：

```text
讀設定
Migration
啟動 Waitress
啟動 Cloudflare
PID
Signal
Graceful Shutdown
```

這樣比在 BAT 塞 200 行 Process Management 更容易維護。

BAT 保持很薄。

---

# 92. Graceful Shutdown

停止時：

```text
Waitress
Flask
SQLite
cloudflared
```

都要正確結束。

不要使用暴力 Kill 當作第一選擇。

超時之後才 Force Kill。

---

# 93. Health Check

提供：

```text
GET /health
```

回傳：

```json
{
  "status": "UP"
}
```

不要回：

```text
Database Path
Python Version
Operating System
Secret
Environment Variable
```

---

# 94. Error Handling

建立：

```text
404
403
500
```

頁面。

---

# 95. 404 文案

例如：

```text
咦？這個頁面好像跑去玩了 🐰

[回首頁]
```

---

# 96. 403

例如：

```text
這裡是爸爸媽媽的秘密基地 🔐

請使用家長帳號登入。
```

---

# 97. 500

不要顯示：

```text
Traceback
SQL
Path
Secret
```

顯示：

```text
系統剛剛跌了一跤 😵

資料應該還好好的，

請再試一次看看。
```

Exception 詳細資訊只寫 Application Log。

---

# 98. UI 風格

整體：

```text
可愛
柔和
明亮
有遊戲感
溫暖
不幼稚
```

避免：

```text
企業後台風
灰黑報表風
密密麻麻 Table
```

---

# 99. Color Palette

可以使用：

```text
#FFF8E7
#FFD166
#06D6A0
#118AB2
#EF476F
```

但使用：

```css
:root {
    --color-primary: ...;
    --color-secondary: ...;
    --color-success: ...;
}
```

不要散落大量 hard-coded Color。

---

# 100. Mobile First

小孩很可能使用：

```text
手機
平板
```

所以優先：

```text
Mobile First
```

按鈕：

至少：

```text
48px
```

高度。

主要操作按鈕要大。

---

# 101. Animation

需要動畫，但不要太吵。

可以加入：

```text
⭐ 星星飛進集點卡
🎉 Confetti
✅ Check 動畫
🎁 Reward 解鎖
Progress 動畫
卡片輕微 Hover
```

動畫大約：

```text
300ms ~ 1000ms
```

---

# 102. Reduced Motion

一定支援：

```css
@media (prefers-reduced-motion: reduce)
```

關閉或減少：

```text
Confetti
Flying Star
Transform
```

---

# 103. 音效

第一版不要預設播放音效。

設定：

```yaml
ui:
  sound_enabled: false
```

未來可以再做。

---

# 104. 小孩友善文案

禁止：

```text
Task successfully completed.
```

改成：

```text
太棒了！今天又完成一件事情囉！🌟
```

---

禁止：

```text
Insufficient points.
```

改：

```text
再收集 3 顆星星就可以換這個禮物囉！💪
```

---

禁止：

```text
Request submitted.
```

改：

```text
收到啦！🎉

等爸爸媽媽確認完成後，
星星就會跑進你的集點卡！
```

---

# 105. Empty State

今日無任務：

```text
🎉 今天的事情都完成啦！

現在可以好好休息一下囉～
```

沒有禮物：

```text
🎁 禮物櫃目前還是空的

請爸爸媽媽放一些驚喜進來吧！
```

---

# 106. Toast

操作成功：

```text
🌟 任務已經送出啦！
```

Admin：

```text
✅ 已確認小明完成「整理玩具」
```

操作錯誤：

```text
哎呀，好像卡住了一下 😵

再試一次看看吧！
```

---

# 107. Confetti 規則

當家長批准任務後：

小孩下一次進入 Dashboard：

可以顯示：

```text
🎉 太棒了！

「整理玩具」通過確認！

+2 ⭐
```

播放一次 Confetti。

但是不能每次重新整理都播放。

可以建立：

```text
Notification
```

或：

```text
unread flag
```

避免重複。

---

# 108. Notification

如果實作：

```text
Notification
```

包含：

```text
id
child_id
type
title
message
read_at
created_at
```

例如：

```text
TASK_APPROVED
REWARD_APPROVED
ACHIEVEMENT_UNLOCKED
```

這是推薦功能。

---

# 109. Achievement

可以加入基本成就。

例如：

```text
🌱 第一步
完成第一個任務

⭐ 小小努力家
總共賺到 10 點

🔥 連續達人
連續 7 天完成全部必做任務

🏆 百點高手
歷史累積取得 100 點
```

如果第一版時間有限：

先設計 Interface / Table。

不一定要全部完成。

---

# 110. Streak

可以顯示：

```text
🔥 已經連續 5 天完成所有任務！
```

規則：

```text
當天所有 Required Task 都 APPROVED
```

才算一天。

---

# 111. Required Task

Task 可以加入：

```text
required
```

例如：

```text
刷牙
required=true

整理玩具
required=false
```

Streak 只檢查 required。

---

# 112. Progress

Dashboard：

```text
今日進度

████████░░

4 / 5

80%
```

WAITING_APPROVAL：

應與 APPROVED 視覺區分。

例如：

```text
⏳ 等爸爸媽媽確認
```

---

# 113. Page List

至少：

```text
/
```

選擇小孩。

```text
/login/admin
```

Admin Login。

```text
/child/dashboard
```

小孩首頁。

```text
/child/calendar
```

行事曆。

```text
/child/rewards
```

禮物。

```text
/child/history
```

歷史。

```text
/admin
```

Admin Dashboard。

```text
/admin/children
/admin/tasks
/admin/approvals
/admin/rewards
/admin/redemptions
/admin/points
/admin/history
/admin/settings
```

---

# 114. API Route

不需要為了 RESTful 而強迫所有頁面做 JSON API。

一般 HTML Form：

可以直接 POST。

例如：

```text
POST /child/tasks/<id>/submit

POST /child/rewards/<id>/request

POST /admin/assignments/<id>/approve

POST /admin/assignments/<id>/reject

POST /admin/redemptions/<id>/approve
```

---

# 115. Idempotency

POST：

```text
Approve
Redeem
```

必須在後端確認目前狀態。

例如：

只有：

```text
WAITING_APPROVAL
```

才允許：

```text
APPROVED
```

如果已經：

```text
APPROVED
```

再次呼叫：

不得增加第二次點數。

---

# 116. PRG Pattern

所有 HTML Form POST：

成功後使用：

```text
POST
↓
Redirect
↓
GET
```

也就是：

```text
Post/Redirect/Get
```

避免 Browser Refresh 重新 POST。

---

# 117. SQL Injection

全部使用：

```text
SQLAlchemy ORM
parameterized query
```

禁止：

```python
f"SELECT * FROM child WHERE name='{name}'"
```

---

# 118. Password Security

密碼與 PIN：

Hash。

禁止：

```text
SHA256(password)
MD5
明碼
```

直接使用 Werkzeug 安全 Password Hash。

---

# 119. Brute Force 基本防護

Admin Login / Child PIN：

加入簡單 Rate Limit 或 Session Level 防護。

例如：

```text
連續 5 次失敗
等待一段時間
```

可以自行實作簡單版本。

不要因此導入 Redis。

家庭系統不需要分散式 Rate Limiter。

---

# 120. 資料刪除

重要資料：

不 Physical Delete。

Child：

```text
active=false
```

Task：

```text
active=false
```

Reward：

```text
active=false
```

PointTransaction：

禁止 Delete。

AuditLog：

禁止 Delete。

---

# 121. 軟刪除歷史完整性

即使：

```text
Reward inactive
```

歷史 Redemption 仍要顯示當時 Reward 名稱。

如果有需要：

RewardRedemption 可以保存 snapshot：

```text
reward_name_snapshot
points_snapshot
```

TaskAssignment 也可以保存：

```text
task_title_snapshot
points_snapshot
```

避免 Task 後來改名後歷史全部跟著變。

---

# 122. Snapshot

推薦：

TaskAssignment：

```text
task_title
task_icon
points
```

作為當次 Snapshot。

即使 Task Template：

```text
整理玩具
```

之後改成：

```text
整理房間
```

昨天的歷史還是：

```text
整理玩具
```

這很重要。

---

# 123. Database Model 至少包含

```text
AdminUser

Child

Task

TaskSchedule

TaskAssignment

PointTransaction

Reward

RewardRedemption

AuditLog
```

推薦：

```text
Notification

Achievement

ChildAchievement
```

---

# 124. Seed Data

Development Environment 可以建立：

Child：

```text
🐼 小明
```

Task：

```text
🪥 刷牙       1
📚 寫功課     2
🧸 整理玩具   2
🚿 洗澡       1
```

Reward：

```text
🍦 吃冰淇淋          10
🎮 玩遊戲 30 分鐘    10
🍿 選今晚電影        15
```

Production：

不要建立 Demo Child。

---

# 125. Environment

可以支援：

```text
development
production
testing
```

設定來源：

```text
FLASK_ENV
```

或自己的：

```text
APP_ENV
```

---

# 126. Production Debug

正式環境：

```text
debug = false
```

禁止把：

```text
Werkzeug Debugger
```

暴露到 Internet。

---

# 127. Testing

使用：

```text
pytest
```

至少建立：

```text
tests/unit/

tests/integration/
```

---

# 128. Unit Test

至少：

```text
test_point_service.py

test_assignment_service.py

test_reward_service.py
```

---

# 129. Integration Test

至少：

```text
test_task_approval_flow.py

test_reward_redemption_flow.py

test_auth.py
```

---

# 130. Test Case 1

任務：

```text
+2
```

批准後：

```text
Balance = 2
```

---

# 131. Test Case 2

同一 TaskAssignment：

Approve 兩次。

結果：

```text
PointTransaction
```

只能有一筆：

```text
+2
```

Balance：

```text
2
```

不得：

```text
4
```

---

# 132. Test Case 3

目前：

```text
13
```

Approve Reward：

```text
10
```

結果：

```text
3
```

---

# 133. Test Case 4

目前：

```text
3
```

申請：

```text
10
```

家長批准時：

拒絕操作。

不得變：

```text
-7
```

---

# 134. Test Case 5

Rejected Task：

不得新增：

```text
PointTransaction
```

---

# 135. Test Case 6

Task 被送出兩次：

不得產生：

```text
Duplicate Approval
Duplicate Points
```

---

# 136. Test Case 7

Reward 庫存：

```text
1
```

成功批准一次後：

```text
0
```

第二次不得成功。

---

# 137. Test Case 8

Child A：

不能操作 Child B 的：

```text
Task
Reward Request
History
```

---

# 138. Test Database

Testing：

不要使用正式：

```text
data/family-reward.db
```

使用：

```text
Temporary SQLite
```

每個測試可以建立獨立 DB。

---

# 139. README

README 必須用：

```text
繁體中文
台灣用語
```

完整說明：

```text
專案介紹

系統需求

第一次安裝

啟動方式

停止方式

設定檔

建立 Admin

SQLite

Migration

Backup

Restore

Cloudflare Tunnel

測試

目錄結構

Troubleshooting

安全性
```

---

# 140. Troubleshooting

README 至少處理：

```text
找不到 Python

Port 8080 被占用

SQLite database is locked

Migration 失敗

Cloudflare 無法連線

忘記 Admin Password

Cloudflare.exe 找不到

config.yaml 格式錯誤
```

---

# 141. Cloudflare Domain

例如：

```text
kids.example.com
```

不要把這個 Domain 寫死。

設定：

```yaml
cloudflare:
  hostname: "kids.example.com"
```

或讀 Cloudflare config.yml。

---

# 142. Logging Rotation

Application Log 不要無限變大。

使用 Python：

```text
logging.handlers.RotatingFileHandler
```

例如：

```text
10 MB
5 backups
```

都可以設定。

---

# 143. Static Cache

CSS / JS：

可以設定合理 Cache Header。

但開發環境方便重新整理。

Production 可以長一點。

---

# 144. UI CSS

建議：

```text
static/css/

variables.css

layout.css

components.css

child.css

admin.css

animations.css
```

不要把所有 CSS 都塞進 base.html。

---

# 145. JavaScript

建議：

```text
static/js/

app.js

task.js

reward.js

calendar.js

animations.js
```

不要放一個：

```text
3000 行 app.js
```

---

# 146. Jinja Component

可以使用：

```text
templates/components/
```

例如：

```text
task_card.html

reward_card.html

points_card.html

flash_message.html

nav.html
```

避免複製大量 HTML。

---

# 147. Accessibility

至少：

```text
Form 有 Label

Button 有文字或 aria-label

Keyboard 可以操作

Focus State 明顯

Color Contrast 足夠
```

不要只靠：

```text
綠色
紅色
```

表示狀態。

同時要：

```text
✅
❌
⏳
```

---

# 148. Birthday

生日不是必要功能。

可以：

```text
nullable
```

如果有生日：

Dashboard 可以顯示：

```text
🎂 今天是你的生日！
```

但不要做過多個資處理。

---

# 149. 親子設計

這個 App 的核心不是：

```text
監督
懲罰
打卡
績效
```

而是：

```text
鼓勵
習慣
參與
成就感
```

UI 文案避免：

```text
你今天沒有完成
你失敗了
你被扣分
```

改為：

```text
今天還有 2 個小任務等你完成 🌱
```

---

# 150. 負點數規則

預設：

```text
Balance 不允許低於 0
```

如果家長 Manual Adjustment：

要扣超過目前點數：

預設拒絕。

除非未來設定：

```yaml
reward:
  allow_negative_balance: false
```

---

# 151. Reward Milestone

集點卡：

使用：

```text
Lifetime Earned
```

Reward：

使用：

```text
Current Balance
```

這個規則必須寫在：

```text
README
Code Comment
Service
Test
```

避免未來混淆。

---

# 152. Configuration Validation

Application 啟動時：

檢查：

```text
port
database path
points_per_card
session timeout
```

例如：

```text
points_per_card <= 0
```

直接拒絕啟動。

顯示清楚錯誤。

---

# 153. File Path

所有：

```text
data
logs
backup
config
cloudflare
```

不要依賴：

```text
目前 Command Prompt 工作目錄
```

而要使用：

```python
Path(__file__).resolve()
```

或 Project Root。

確保從：

```text
桌面捷徑
BAT
其他目錄
```

啟動都不會找錯檔案。

---

# 154. Python Path

全部使用：

```python
pathlib.Path
```

不要自己：

```python
"C:\\family-reward\\data"
```

讓程式保持可攜。

---

# 155. Dependency

requirements.txt 要 pin Major / Minor 相容版本。

不要每次：

```text
pip install latest everything
```

導致未來突然壞掉。

---

# 156. 首次初始化

第一次啟動：

```text
沒有 data/
↓
建立

沒有 DB
↓
Migration 建立

沒有 Admin
↓
建立 Initial Admin
```

然後 Log：

```text
Application initialized successfully
```

---

# 157. 密碼提醒

如果 Admin 還使用 Initial Password：

Dashboard 顯示固定提醒：

```text
⚠️ 目前仍使用初始管理員密碼。

請立即修改。
```

---

# 158. UI 不暴露 ID

小孩畫面不要顯示：

```text
Child ID: 1
Task ID: 123
```

這些是系統內部資料。

---

# 159. URL Authorization

不能只靠：

```text
畫面沒有按鈕
```

例如 Child 手動輸入：

```text
/admin
```

後端仍必須回：

```text
403
```

或 Redirect Admin Login。

---

# 160. Object Authorization

Child A 手動修改 URL：

```text
/task/Child-B-assignment
```

不得取得資料。

後端一定：

```text
assignment.child_id == current_child.id
```

---

# 161. Race Condition

Approve Reward：

同一 Transaction 內：

```text
重新計算 Balance
重新檢查 Stock
建立 Ledger
更新 Redemption
更新 Stock
```

不能使用一開始頁面顯示的舊 Balance。

---

# 162. Database Error

如果 DB 無法開：

顯示：

```text
無法開啟資料庫。

請確認：

data 目錄存在，而且目前使用者有寫入權限。

詳細資訊請查看：

logs\family-reward.log
```

---

# 163. Cloudflare Failure

如果：

Flask 正常

但 Cloudflare 啟動失敗：

本機服務仍然可以繼續。

顯示：

```text
⚠️ 網站已在本機啟動，但 Cloudflare Tunnel 啟動失敗。

本機：

http://127.0.0.1:8080

請查看 Log。
```

不要把整個 Web Server 一起關掉。

---

# 164. Port Occupied

start.bat / launcher：

啟動前檢查：

```text
127.0.0.1:8080
```

如果被占用：

不要默默失敗。

顯示：

```text
Port 8080 已被其他程式使用。

請修改：

config\config.yaml

server.port
```

---

# 165. Multiple Instance

避免使用者連按：

```text
start.bat
start.bat
```

啟動兩份。

可以：

```text
PID File
Port Check
Process Check
```

如果已啟動：

顯示：

```text
家庭任務集點樂園已經在執行中 ⭐

http://127.0.0.1:8080
```

---

# 166. HTML Metadata

基本加入：

```text
viewport
charset UTF-8
title
description
```

中文不得亂碼。

---

# 167. UTF-8

所有：

```text
Python
HTML
CSS
JS
YAML
BAT
README
```

都注意 UTF-8。

BAT：

```bat
chcp 65001
```

若 Windows Terminal 中文顯示有問題，需要合理處理。

---

# 168. Production Package

最終專案完成後：

可以直接 Zip：

```text
family-reward.zip
```

解壓縮：

```text
C:\family-reward
```

執行：

```text
start.bat
```

---

# 169. Git Ignore

至少：

```text
.venv/
__pycache__/
.pytest_cache/
.env
data/*.db
data/*.db-wal
data/*.db-shm
logs/
backup/
run/
cloudflare/*.json
```

---

# 170. 不要提交個人資料

Production DB：

```text
family-reward.db
```

禁止 Commit Git。

---

# 171. 開發流程

實作時不要一口氣寫完全部才第一次測試。

按照以下階段。

---

## Phase 1

建立：

```text
Python 專案
Flask App Factory
Config
Logging
SQLAlchemy
SQLite
Migration
Base Template
Health Check
```

然後：

```text
pytest
```

與：

```text
啟動 Application
```

確認成功。

---

## Phase 2

建立：

```text
AdminUser
Child
Login
Child PIN
Security
```

測試。

---

## Phase 3

建立：

```text
Task
Schedule
TaskAssignment
今日任務
任務 Submit
```

測試。

---

## Phase 4

建立：

```text
Admin Approval
PointTransaction
防止 Duplicate Points
History
```

測試。

---

## Phase 5

建立：

```text
Reward
Redemption
Current Balance
Lifetime Earned
```

測試。

---

## Phase 6

建立：

```text
Calendar
Animations
Theme
Responsive UI
```

---

## Phase 7

建立：

```text
start.bat
stop.bat
backup.bat
restore.bat
launcher.py
Waitress
Cloudflare
```

---

## Phase 8

建立：

```text
完整測試
README
Security Review
Production Package
```

---

# 172. 每完成 Phase

都必須：

```text
執行 pytest
```

並實際啟動：

```text
Application
```

確認沒有：

```text
SyntaxError
ImportError
SQLAlchemy Error
Migration Error
Template Error
```

---

# 173. 完成前實際驗證

至少：

```text
python -m pytest
```

全部成功。

然後實際執行：

```text
start.bat
```

確認：

```text
GET /
```

正常。

確認：

```text
GET /health
```

回：

```json
{
  "status": "UP"
}
```

---

# 174. 完整驗收流程

完成後請實際驗證：

## 1

執行：

```text
start.bat
```

---

## 2

開：

```text
http://127.0.0.1:8080
```

---

## 3

Admin Login。

---

## 4

建立：

```text
🐼 小明
```

---

## 5

建立：

```text
🧸 整理玩具
+2
```

---

## 6

設定今天指派給：

```text
小明
```

---

## 7

小明使用 PIN 登入。

---

## 8

看到：

```text
🧸 整理玩具

+2 ⭐

[我完成了！]
```

---

## 9

按：

```text
我完成了！
```

---

## 10

Admin：

看到：

```text
待確認
```

---

## 11

Admin Approve。

---

## 12

確認：

```text
PointTransaction

+2
```

只有一筆。

---

## 13

小明重新進入：

看到：

```text
🎉

+2 ⭐
```

---

## 14

累積：

```text
10
```

確認：

```text
集點卡 10 / 10
```

---

## 15

建立 Reward：

```text
🍦 吃冰淇淋
10
```

---

## 16

小明申請。

---

## 17

Admin Approve。

---

## 18

確認：

```text
Current Balance
```

正確扣：

```text
-10
```

---

## 19

確認：

```text
Lifetime Earned
```

沒有因為兌換倒退。

---

## 20

確認：

```text
Calendar
```

正常顯示：

```text
今日任務
完成數
今日賺到點數
```

---

## 21

關閉程式。

重新：

```text
start.bat
```

資料仍然存在。

---

## 22

執行：

```text
backup.bat
```

確認產生 Backup。

---

## 23

Cloudflare 開啟後：

確認：

```text
https://自訂網域
```

可以正常使用。

---

# 175. 最終交付內容

專案完成後，請整理提供：

```text
1. Architecture

2. Project Tree

3. Database Schema

4. Model 關聯

5. Security Design

6. Current Balance 計算規則

7. Lifetime Earned 計算規則

8. Task Approval 流程

9. Reward Redemption 流程

10. Configuration

11. Windows 啟動方式

12. Backup / Restore

13. Cloudflare Tunnel

14. Test Result

15. 已知限制

16. 未來可以擴充的項目
```

---

# 176. 不要假裝完成

如果：

```text
pytest
```

沒有跑：

不要說：

```text
所有測試成功
```

如果：

```text
start.bat
```

沒有實際驗證：

不要說：

```text
Windows 啟動正常
```

如果：

Cloudflare 沒有實際 Credentials：

請說：

```text
Cloudflare 設定檔與啟動流程已完成，但無法在沒有實際 Tunnel Credentials 的情況下驗證外部網域。
```

不要假裝成功。

---

# 177. 程式碼品質

Python：

遵守：

```text
PEP 8
type hints
clear naming
small functions
single responsibility
```

適合時：

```python
@dataclass
Enum
TypedDict
```

但是不要為了 Type System 過度複雜。

---

# 178. Type Hint

主要 Service Function：

加入 Type Hint。

例如：

```python
def approve_assignment(
    assignment_id: int,
    admin_id: int
) -> TaskAssignment:
    ...
```

---

# 179. Enum

Status：

不要到處使用 Magic String。

例如：

```python
class AssignmentStatus(str, Enum):
    TODO = "TODO"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
```

Reward Status 也一樣。

---

# 180. Money-like Logic

雖然這是點數不是錢：

仍然當成 Ledger 系統設計。

重點：

```text
不可重複
不可憑空消失
不可偷偷修改歷史
必須有來源
必須有原因
```

---

# 181. 親子產品核心

這個產品不是要讓父母：

```text
監控小孩
```

而是要讓小孩：

```text
看得懂今天該做什麼

完成後有成就感

清楚知道自己得到多少星星

期待下一個小禮物

每天願意自己打開網站
```

UI/UX 所有決策都應以此為中心。

---

# 182. 第一版不要做

第一版禁止過度擴充：

```text
Push Notification

Email

LINE Bot

AI Recommendation

OCR

Camera

File Upload

Social Login

Realtime WebSocket

Mobile App

PWA Offline Sync
```

先把：

```text
任務
審核
點數
禮物
行事曆
Windows
Cloudflare
```

做到非常穩定。

---

# 183. 未來擴充預留

架構可以讓未來加入：

```text
LINE 通知

PWA

家庭多人管理者

更多家庭

更多孩子

季節活動

Achievement Badge

生日主題

每日挑戰

排行榜

照片任務證明

AI 任務建議
```

但現在不要實作，除非不增加第一版複雜度。

---

# 184. 最重要資料一致性規則

必須永遠成立：

```text
1.

同一個 TaskAssignment
最多只能產生一次 Earn Point Transaction。


2.

Rejected Task
永遠不能產生 Earn Point Transaction。


3.

Reward Approval
不能讓 Balance 變成負數。


4.

Reward Approval
最多只能產生一次 Redeem Transaction。


5.

Current Balance
必須能由 PointTransaction 完整重算。


6.

Lifetime Earned
不能因為兌換 Reward 而降低。


7.

Task / Reward 修改
不能改變既有歷史紀錄。


8.

Child A
不能看到或修改 Child B 私人資料。


9.

Child
永遠不能存取 Admin Function。


10.

SQLite Database
不得從 HTTP 直接下載。
```

---

# 185. 最終開發原則

如果需求有兩種做法：

優先選：

```text
簡單
容易理解
安全
可測試
Pythonic
Windows 好維護
```

而不是：

```text
最潮
最複雜
最多套件
最企業級
```

---

# 186. 現在開始

現在不要再只提供 Architecture 建議。

請直接開始實作。

第一步：

```text
1. 建立完整 Python / Flask Project Structure

2. 建立 requirements.txt

3. 建立 App Factory

4. 建立 YAML Config Loader

5. 建立 SQLAlchemy

6. 建立 SQLite WAL / foreign_keys / busy_timeout

7. 建立 Flask-Migrate

8. 建立 Logging

9. 建立 /health

10. 建立最基本首頁

11. 建立 pytest 基礎環境

12. 執行第一次測試

13. 實際啟動 Flask

14. 修正到可以正常執行

15. 再開始實作 Child / Task / Points
```

如果你擁有工作目錄權限：

請直接操作檔案。

不要把每一份程式碼都丟給我讓我自己複製。

遇到一般技術選擇：

自行做出合理決定並繼續。

只有真正會大幅改變產品方向的問題才需要詢問我。

最終目標：

```text
解壓縮專案
↓
修改 config\config.yaml
↓
雙擊 start.bat
↓
網站啟動
↓
SQLite 自動準備完成
↓
Cloudflare Tunnel 自動啟動
↓
家長與小孩即可使用
```