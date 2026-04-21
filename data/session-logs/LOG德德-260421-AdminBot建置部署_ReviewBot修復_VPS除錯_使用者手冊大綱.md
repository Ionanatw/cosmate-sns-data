# Admin Bot 建置部署 LOG — 2026-04-21

## 0. 文件資訊

- **建立時間**：2026-04-21 14:13 GMT+8
- **建立者**：德德（claude-sonnet-4-6）
- **Session 日期**：2026-04-21
- **對話串**：德德（Claude Code CLI）
- **檔案路徑**：data/session-logs/LOG德德-260421-AdminBot建置部署_ReviewBot修復_VPS除錯_使用者手冊大綱.md

### 關聯資源索引

| 資源 | 位置 | 路徑 |
|------|------|------|
| admin-bot 原始碼 | cosmate-ai-nexus repo | `agents/dede/admin-bot/` |
| telegram-bot 原始碼 | cosmate-ai-nexus repo | `agents/dede/telegram-bot/` |
| VPS | Hostinger | IP: 187.77.149.175 |
| admin-bot .env | VPS | `/opt/admin-bot/.env` |
| review-bot .env | VPS | `/opt/telegram-review-bot/.env` |

---

## 📎 貼進新 Session 的交接文字（複製貼上即用）

> ⚠️ 新 Session 必須先閱讀上一次 LOG 才能延續記憶。

我是鴿王，你是德德，請先閱讀上一次 Session LOG 延續記憶：
讀取 data/session-logs/LOG德德-260421-AdminBot建置部署_ReviewBot修復_VPS除錯_使用者手冊大綱.md

閱讀完畢後，以下是重點交接：
1. cosmate-admin-bot 已建置並成功部署到 VPS，/topics 正常回應
2. 使用者手冊大綱已完成（plan mode），尚未輸出正式文件
3. 待辦：rotate 外洩憑證（Anthropic API key + admin bot token）、Infisical 整合

---

## 1. TL;DR（三句話）

- 從零建立 cosmate-admin-bot（TypeScript + grammY），部署到 VPS Docker，成功運作
- 過程中修復多個阻塞問題：VPS IP 錯誤、錯誤 token 互搶、review bot crash、`$sk` shell 展開踩坑
- 完成使用者手冊大綱（plan mode），Stage 2 簡報格式待下一個 session

---

## 2. 決策紀錄

### 決策 1：Admin Bot 建為獨立服務，不整合進現有 review bot
- **最終方案**：獨立 TypeScript 專案（`agents/dede/admin-bot/`），獨立 Docker container
- **原因**：review bot 已有功能，混在一起風險高；Admin bot 有 Docker socket 掛載需求，隔離更安全
- **替代方案**：在 review bot 加 admin 指令（否決：耦合太高，crash 會互相影響）

### 決策 2：Admin group 獨立於 review group
- **最終方案**：鴿王建一個私有群組「CosMate中控台」，僅限 Admin Bot + 鴿王
- **原因**：未來引入人類同事時，review group 的 topic 結構不應暴露
- **替代方案**：在 review group 直接操作（否決：同事可見，安全邊界不清）

### 決策 3：`docker compose up -d` 而非 `docker restart`
- **最終方案**：更新 .env 後一律用 `docker compose up -d`
- **原因**：`docker restart` 不重新讀取 .env，導致設定不生效
- **替代方案**：`docker restart`（否決：無法讀取 .env 變更）

---

## 3. 產出清單

| # | 名稱 | 類型 | 路徑 | 狀態 |
|---|------|------|------|------|
| 1 | cosmate-admin-bot 完整原始碼 | TypeScript 專案 | `agents/dede/admin-bot/src/` | ✅ 已部署 |
| 2 | admin-bot Dockerfile | 容器設定 | `agents/dede/admin-bot/Dockerfile` | ✅ |
| 3 | admin-bot docker-compose.yml | 容器設定 | `agents/dede/admin-bot/docker-compose.yml` | ✅ |
| 4 | admin-bot .env.example | 範本 | `agents/dede/admin-bot/.env.example` | ✅ |
| 5 | telegram-bot Route A + QA topic | 功能更新 | `agents/dede/telegram-bot/src/` | ✅ 已部署（commit 5f20f31） |
| 6 | 使用者手冊大綱 | plan 文件 | `/Users/ionachen/.claude/plans/parallel-wandering-stearns.md` | ⏳ Stage 2 待輸出 |

---

## 4. 除錯與教訓

### 除錯 1：VPS IP 記錯（69.230.250.167 vs 187.77.149.175）
- **問題**：所有 SSH/rsync 命令 timeout
- **根因**：記錯 IP，應從 Hostinger hPanel 截圖確認
- **解法**：鴿王截圖 hPanel，確認正確 IP 為 187.77.149.175
- **教訓**：VPS IP 不應靠記憶，每次確認從 Hostinger hPanel 取
- **🔁 寫進不二錯？**：否（已記入 memory）

### 除錯 2：兩個 bot 搶同一個 token
- **問題**：admin bot 完全沒回應，只有啟動 log
- **根因**：鴿王把 review bot（cosmatepost_bot）的 token 填進 admin bot .env，兩個 bot 競爭同一 token，admin bot 拿不到 update
- **解法**：從 BotFather 申請新的 cosmateadmin_bot token，填入 admin bot .env
- **教訓**：每個 bot 必須有自己獨立的 token，絕不共用
- **🔁 寫進不二錯？**：是（分類：Telegram Bot 設定）

### 除錯 3：Privacy Mode 踢掉重加才生效
- **問題**：關閉 Privacy Mode 後 bot 仍然收不到群組訊息
- **根因**：BotFather 的 Privacy Mode 設定不會即時套用，必須把 bot 踢出群組後重新加入才生效
- **解法**：把 bot 踢掉 → 重新加入群組
- **教訓**：有前後關聯的步驟必須一次說完，這個踩坑浪費了多次來回
- **🔁 寫進不二錯？**：是（已記入 memory feedback_complete_steps）

### 除錯 4：`$sk` shell 變數展開
- **問題**：`NEW_KEY=$sk-ant-api03-...` → shell 把 `$sk` 展開為空字串，key 變成 `-ant-api03-...`，API 回傳 401
- **根因**：shell 變數賦值中 `$` 後接字母被解讀為變數引用
- **解法**：用 `|` 分隔符避開 `$`：`sed -i 's|^ANTHROPIC_API_KEY=-ant|ANTHROPIC_API_KEY=sk-ant|'`
- **教訓**：在 sed/shell 中含 `$` 的字串必須用單引號或跳脫
- **🔁 寫進不二錯？**：是（分類：VPS / Shell）

### 除錯 5：`docker restart` 不重讀 .env
- **問題**：更新 .env 後用 `docker restart`，設定沒有生效
- **根因**：`docker restart` 只重啟 process，不重新載入 compose 設定與 .env
- **解法**：改用 `docker compose up -d`（從 compose 目錄執行）
- **教訓**：更新 .env 後一律用 `docker compose up -d`，絕不用 `docker restart`
- **🔁 寫進不二錯？**：是（分類：Docker / VPS）

### 除錯 6：Anthropic key 重複行
- **問題**：review bot .env 出現兩條 `ANTHROPIC_API_KEY=`
- **根因**：多次 sed 追加導致重複
- **解法**：`awk '!seen[$0]++ || !/^ANTHROPIC_API_KEY=/'` 去重複
- **🔁 寫進不二錯？**：否

---

## 5. TODO

### 🙋 鴿王要做

| # | 任務 | 優先度 | 解鎖什麼 |
|---|------|--------|---------|
| 1 | Rotate Anthropic API key（sk-ant-api03-PnU23IEQ... 已外洩） | 🔴 緊急 | 防止濫用 |
| 2 | Rotate admin bot token（AAFRjh4... 已外洩） | 🔴 緊急 | 防止 bot 被接管 |
| 3 | 把 admin bot 加入 review group 並設為管理員 | 中 | /newtopic、/invite 指令才能運作 |
| 4 | 輸出使用者手冊正式文件（Stage 2 簡報格式） | 低 | 同事自行導入 |

### 🤖 Agent 可自動跑

| # | 任務 | 誰 | 前置條件 |
|---|------|---|---------|
| 1 | Infisical 整合（取代 plaintext .env） | 德德 | 鴿王確認要做 |
| 2 | 更新 VPS IP 記憶（187.77.149.175） | 德德 | 無，已在 memory |

---

## 6. 回寫檢查

| 內容 | 應回寫到 | Notion 已同步？ | 狀態 |
|------|---------|---------------|------|
| docker restart vs compose up -d 規則 | 不二錯 DB | ⏳ | ⏳ |
| $sk shell 展開踩坑 | 不二錯 DB | ⏳ | ⏳ |
| Privacy Mode 踢掉重加 | 不二錯 DB（已在 memory） | ⏳ | ⏳ |
| VPS IP 正確值 187.77.149.175 | memory（已更新） | — | ✅ |
| 前後關聯步驟一次說完 | memory（已記錄） | — | ✅ |
| Session LOG 本身 | Notion Session LOG DB | ⏳ | ⏳ |

---

## 7. HANDOFF 摘要

**狀態**：Admin Bot 部署完成，基本功能正常（/topics、Q&A）；使用者手冊大綱在 plan mode 已完成

**下一步**：
1. 🔴 立即 rotate 外洩的 Anthropic key + admin bot token
2. 把 admin bot 加入 review group 設為管理員
3. 輸出使用者手冊正式 Markdown 文件（Stage 2 再轉簡報格式）
4. （選做）Infisical 整合 plaintext .env

**阻塞**：憑證 rotate 需要鴿王手動操作（BotFather + Anthropic Console）

---

## 8. 關鍵觀察

- Admin Bot 的核心價值是「用自然語言操作 review bot 的管理功能」，這條路徑可以延伸：未來 Claude 可以根據群組對話自動建議開新 topic、自動 permit 用戶，而不需要鴿王手動下指令。
- 這次最多時間浪費在「一次沒說清楚的步驟」（Privacy Mode、docker restart）。這是一個系統性問題：每次給操作建議前，必須先問自己「這個做完還需要做什麼才能生效」。
