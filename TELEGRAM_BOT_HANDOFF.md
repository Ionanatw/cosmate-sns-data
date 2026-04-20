# Threads Review Telegram Bot — 交接接續

## 進度狀態（2026-04-16）

✅ **已完成**：
- 程式碼全部寫完（`agents/dede/telegram-bot/`）
- Type-check 0 錯誤
- npm install 完成
- @BotFather 創建 bot：`@cosmatepost_bot`
- Bot Token：`8328350375:AAHhb89u2lGkkArX8dxrQgCtRWyGjWCNp9M`

⏳ **剩下要做**：
1. 鴿王手動：建 Telegram group + Topics + bot 設 admin + 取得 IDs（5 分鐘）
2. 德德自動：把 IDs 寫進 VPS .env + docker deploy（5 分鐘）

---

## 鴿王下一步（手機操作）

### 1. 建群組 + Topics
- Telegram 新建 group「AI 鴿舍 Threads 審核」
- Settings → Edit → 開啟 **Topics**（會升級成 supergroup）
- 建 4 個 Topics（順序固定）：
  - 📋 總覽
  - 🎭 宅人Dadana
  - 🎮 動漫宅Olie
  - 💼 CosMate小編

### 2. 加 bot
- Add Members → 搜尋 `@cosmatepost_bot` → 加入
- 點 bot → Promote to Admin
- 勾選：✅ Manage Topics ✅ Send Messages

### 3. 取得 IDs

**Group ID**：
- 群組內 forward 任一訊息給 **@userinfobot**
- 它會回 `Forwarded from chat -100xxxxx`，這就是 Group ID

**Topic IDs**（×4）：
- 在每個 topic 內發一則訊息
- 長按訊息 → Copy Link
- URL 中間那串數字 = thread_id
  - 例：`https://t.me/c/2156789012/3/45` → thread_id = `3`

### 4. 把 IDs 整理好

複製這個格式填好（直接貼回給 Claude）：
```
TELEGRAM_GROUP_ID=-100xxxxx
TOPIC_OVERVIEW_ID=x
TOPIC_DADANA_ID=x
TOPIC_OLIE_ID=x
TOPIC_COSMATE_ID=x
```

---

## 接續方式（三選一）

### 方式 A：回家後繼續這個 Claude Code session（最省事）
直接打開 VSCode → Claude Code 視窗，這個 session 還在，貼上 IDs 就繼續。

### 方式 B：用 @NexusInbox_bot 把 IDs 寫進 Notion Inbox
- 你已經有的 inbox bot 可以用
- 在 Telegram 給 @NexusInbox_bot 私訊 IDs（標題寫「Telegram bot IDs」）
- 之後 Claude 從 Notion Inbox DB 撈出來

### 方式 C：開新 Claude.ai 對話接手
- 上 claude.ai
- 上傳這個檔案 `TELEGRAM_BOT_HANDOFF.md`
- 加上一句：「按照這個 handoff 繼續部署，我已經有 IDs：[貼 IDs]」

---

## 部署細節（給接手的 AI 看）

### 本機路徑
```
/Users/ionachen/Documents/Claude/cosmate-ai-nexus/agents/dede/telegram-bot/
├── src/                # 8 個 .ts 檔案，全部寫完
├── package.json        # grammy + dotenv
├── Dockerfile          # 從 discord-bot 複製
├── docker-compose.yml  # container: threads-review-telegram-bot
└── .env.example        # 範本
```

### 部署步驟（鴿王給 IDs 後）

1. 建立本機 `.env`（從 `.env.example` 複製，填入鴿王給的 IDs + 既有的 Notion/Threads tokens）
2. SCP 到 VPS：
   ```
   scp -i ~/.ssh/id_ed25519_vps -r src package.json package-lock.json tsconfig.json Dockerfile docker-compose.yml root@187.77.149.175:/opt/telegram-review-bot/
   ```
3. VPS 上建 `.env`（同步驟 1 的內容）
4. `cd /opt/telegram-review-bot && docker compose up -d`
5. `docker compose logs -f` 確認「Bot 已上線」
6. 鴿王在「總覽」topic 打「掃描」測試

### 環境變數來源
- Telegram bot token: `8328350375:AAHhb89u2lGkkArX8dxrQgCtRWyGjWCNp9M`
- Notion API key: 從 `/Users/ionachen/Documents/Claude/project/.env.threads` 撈 `NOTION_TOKEN`
- Threads tokens: 從同檔案撈 `THREADS_TOKEN_COSMATE` / `THREADS_TOKEN_DADANA` / `THREADS_TOKEN_OLIE`

### 後續文件更新
- 更新 `/Users/ionachen/.claude/skills/threads-publisher/skill.md`
- 更新 `agents/dede/threads-publisher/SKILL.md`
- 開新 Notion ticket 紀錄（Ticket DB: `5e99829e45014ce6916f1d781d2d8044`）
- Git commit + push to `Ionanatw/cosmate-ai-nexus`

### Discord bot 處置
**保留不關**（鴿王指定）。`/opt/threads-review-bot/` 繼續跑作為冷備援。
