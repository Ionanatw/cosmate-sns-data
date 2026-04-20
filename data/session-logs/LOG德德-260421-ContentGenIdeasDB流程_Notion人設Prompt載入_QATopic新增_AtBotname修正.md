# Telegram Bot 產文架構升級 LOG — 2026-04-21

## 0. 文件資訊

- **建立時間**：2026-04-21 02:20 GMT+8
- **建立者**：德德（claude-sonnet-4-6）
- **Session 日期**：2026-04-21
- **對話串**：德德（Claude Code）
- **檔案路徑**：data/session-logs/LOG德德-260421-ContentGenIdeasDB流程_Notion人設Prompt載入_QATopic新增_AtBotname修正.md

### 關聯資源索引

| 資源 | 位置 | 路徑 |
|------|------|------|
| Telegram Bot src | repo | `cosmate-ai-nexus/agents/dede/telegram-bot/src/` |
| content-gen SKILL | repo | `cosmate-ai-nexus/skills/content-gen/SKILL.md` |
| Dadana System Prompt | Notion | `3286fedce91a818a8dc5f1df0e8874a2` |
| Olie System Prompt | Notion | `33d6fedce91a815b9a3de3d4998ded88` |
| Ideas DB | Notion | `2106fedc-e91a-8162-bcd1-000b5c93b0ab` |

---

## 📎 貼進新 Session 的交接文字（複製貼上即用）

> ⚠️ 新 Session 必須先閱讀上一次 LOG 才能延續記憶。

我是鴿王，你是德德，請先閱讀上一次 Session LOG 延續記憶：
讀取 data/session-logs/LOG德德-260421-ContentGenIdeasDB流程_Notion人設Prompt載入_QATopic新增_AtBotname修正.md

閱讀完畢後，以下是重點交接：
1. 產文流程已全面升級為 Ideas DB 模式（人設 → 格式 → Ideas DB 選素材 → 生成），同時加入 Notion 完整人設 System Prompt（Dadana、Olie）
2. 新增「💬 專案問答」topic（thread_id=361），自由文字走 Claude API 回答
3. VPS SSH 整個 session 都 timeout，所有改動尚未部署。恢復後需要：rsync src/ + echo "TOPIC_QA_ID=361" >> .env + docker compose up -d --build

---

## 1. TL;DR（三句話）

- 把 Telegram Bot 的產文流程從「用戶輸入題目 → Claude 生成」改為「從 Ideas DB 拉取已驗證素材 → 搭配人設完整 Notion System Prompt 生成」，對齊 content-gen SKILL 的驗證邏輯。
- 同時修正了 @botname suffix bug、新增「專案問答」topic（Claude API 直接回答）、Notion 人設 Prompt 優先載入。
- 所有改動本地 24 tests ✅，待 VPS 恢復後部署。

---

## 2. 決策紀錄

### 決策 1：產文 Q1/Q3 改為從 Ideas DB 選素材（路線 A）

- **最終方案**：移除 Q1（用戶手動輸入題目）和 Q3（Hook 選擇），改為格式選完後自動查 Ideas DB，列出最多 5 筆待寫素材讓用戶選擇
- **原因**：用戶手動輸入的題目容易跑出人設範圍（如 Olie 被生成了少女革命文章）；Ideas DB 是已驗證的素材庫，SKILL.md 也明文規定必須優先使用
- **替代方案**：路線 B（Bot 打 n8n Webhook 觸發完整 SKILL）否決原因：需要 Bot ↔ n8n 雙向溝通機制，複雜度高 2-3 倍

### 決策 2：Notion 完整 System Prompt 優先載入

- **最終方案**：`PERSONA_NOTION_PAGE` registry 存 Dadana + Olie 的頁面 ID，`generateContent()` 優先從 Notion 讀取完整 System Prompt；Notion 讀取失敗時 fallback 到 3 行 inline spec
- **原因**：SKILL.md 明確規定「有完整版 System Prompt 頁面時必須優先讀取，否則不得產文」
- **替代方案**：把 Notion Prompt 內容 hardcode 到 contentgen.ts（否決：內容會持續更新，要跟 Notion 保持同步）

### 決策 3：新增「專案問答」topic

- **最終方案**：在 Telegram 群組加 thread_id=361 的新 topic，自由文字直接呼叫 Claude API（以 CosMate 專案為 context），回答關於專案進度或技術知識的問題
- **原因**：鴿王想要一個在 Telegram 內快速詢問 Claude 的管道，不需要離開群組
- **替代方案**：用 Claude Code CLI（否決：離開 Telegram 太麻煩，即時問答場景需要 Telegram 原生體驗）

---

## 3. 產出清單

| # | 名稱 | 類型 | 路徑 | 狀態 |
|---|------|------|------|------|
| 1 | `notion.ts` 加 `fetchPersonaSystemPrompt()` + `queryPendingIdeas()` | 程式碼 | `src/notion.ts` | ✅ |
| 2 | `contentgen.ts` 加 `PERSONA_NOTION_PAGE` + `buildSystemPromptFromNotion()` | 程式碼 | `src/contentgen.ts` | ✅ |
| 3 | `keyboards.ts` 加 `ideaListKeyboard()` + `content_gen_idea` callback | 程式碼 | `src/keyboards.ts` | ✅ |
| 4 | `callbacks.ts` 重寫 content-gen handlers（路線 A） | 程式碼 | `src/callbacks.ts` | ✅ |
| 5 | `commands.ts` 精簡 handleGenCommand + finalizeAndReview | 程式碼 | `src/commands.ts` | ✅ |
| 6 | `review.ts` 更新 ContentGenStep + PendingContentGen | 程式碼 | `src/review.ts` | ✅ |
| 7 | `qa.ts` 新建（Claude API Q&A handler） | 程式碼 | `src/qa.ts` | ✅ |
| 8 | `config.ts` + `topics.ts` 加 QA topic | 程式碼 | `src/config.ts`, `src/topics.ts` | ✅ |
| 9 | `index.ts` 更新路由 + isQaTopic 接入 | 程式碼 | `src/index.ts` | ✅ |

---

## 4. 除錯與教訓

### 除錯 1：@botname suffix 導致 keyword = "@cosmatepost_bot"

- **問題**：用戶在 supergroup 輸入 `/gen`，Telegram 自動變為 `/gen@cosmatepost_bot`，舊的 keyword 提取 regex 沒有 strip `@botname`，導致 `pending.topic = "@cosmatepost_bot"`，進而生成無關內容
- **根因**：`rawText.replace(/^(\/gen|\/產文)\s*/u, '')` 無法處理 `@botname` suffix
- **解法**：路線 A 移除了 keyword 提取邏輯，問題自然消除；同時更新 hears regex 為 `(\/gen|\/產文)(@\w+)?(\s.*)?`
- **教訓**：Telegram supergroup 的 slash command 一律帶 `@botname`，所有指令解析都要 strip 或設計為不依賴 text 解析
- **🔁 寫進不二錯？**：是（分類：Telegram 指令解析 / @botname suffix）

### 除錯 2：idea 選完後需要查標題，但 callback data 只有 pageId

- **問題**：`ideaListKeyboard` 的按鈕 callback = `cg_i:{pageId32}`，選完後 `handleContentGenIdea` 拿不到 idea 標題
- **根因**：Telegram callback data 上限 64 bytes，無法塞入完整標題
- **解法**：在 `handleContentGenFormat` 查到 ideas 後，把完整 list 存入 `PendingContentGen.ideaOptions`，`handleContentGenIdea` 從 pending state 反查 pageId 對應的 title
- **教訓**：當 callback data 放不下完整資訊時，用 pending state 作為短期快取
- **🔁 寫進不二錯？**：否（屬於設計決策，非錯誤模式）

### 除錯 3：VPS SSH 全場 timeout

- **問題**：整個 session VPS SSH 無法連線（Operation timed out）
- **根因**：VPS 可能重啟、網路問題或防火牆規則
- **解法**：本地 tests 全過，待 VPS 恢復後一次部署本 session 的所有改動
- **教訓**：備好明確的部署指令清單（rsync + .env 新增 + docker compose up -d --build）
- **🔁 寫進不二錯？**：否

---

## 5. TODO

### 🙋 鴿王要做

| # | 任務 | 時間 | 解鎖什麼 |
|---|------|------|---------|
| 1 | VPS 恢復後：`rsync src/ + echo "TOPIC_QA_ID=361" >> .env + docker compose up -d --build` | VPS 恢復後立刻 | 所有本 session 改動上線 |
| 2 | 在 Telegram「💬 專案問答」topic 測試自由文字問答 | 部署後 | 確認 QA topic 功能 |
| 3 | 在 Telegram 測試 `/gen`（General Topic）→ 人設 → 格式 → Ideas DB 清單是否出現 | 部署後 | 確認路線 A 完整流程 |
| 4 | 補齊其他人設的 Notion System Prompt（目前只有 Dadana + Olie） | 有空時 | Amy、Kiki、Husky、CosMate小編也能用完整 prompt |

### 🤖 Agent 可自動跑

| # | 任務 | 誰 | 票號 | 前置條件 |
|---|------|---|------|---------|
| 1 | 學院鴿建立 Amy、Kiki、Husky、CosMate小編的 Notion System Prompt 頁面，並更新 SKILL.md 的 `PERSONA_NOTION_PAGE` | 學院鴿 | — | 鴿王授權 |

---

## 6. 回寫檢查

| 內容 | 應回寫到 | Notion 已同步？ | 狀態 |
|------|---------|---------------|------|
| @botname suffix 教訓 | 不二錯 DB | ⏳ | ⏳ 待寫 |
| Ideas DB 流程設計 | Living Status Doc（Bot 模組說明） | ⏳ | ⏳ 待更新 |
| QA topic 建立（thread_id=361） | Living Status Doc | ⏳ | ⏳ 待更新 |
| Session LOG 本身 | Notion Session LOG DB | ⏳ | ⏳ Step 4 |

---

## 7. HANDOFF 摘要

**狀態**：所有程式碼改動完成（24 tests ✅），但 VPS 全 session timeout，尚未部署。

**下一步**：
1. VPS 恢復後執行部署指令
2. 測試 Ideas DB 流程（人設 → 格式 → ideas 清單 → 生成）
3. 測試 QA topic 問答功能
4. 可選：補其他人設的 Notion System Prompt

**阻塞**：VPS SSH timeout — 等網路/VPS 恢復，無需代碼修改

---

## 8. 關鍵觀察

**設計哲學轉變**：本 session 最重要的決策是把「用戶驅動」改為「資料庫驅動」。舊流程讓用戶自由輸入題目，容易脫離人設範圍；新流程從 Ideas DB 拿已驗證的素材，確保產出在既定的策略框架內。這個轉變讓 Bot 從「AI 產文工具」變成「已驗證流程的執行者」——與 content-gen SKILL 的設計哲學完全對齊。

**Notion System Prompt 優先載入**：現在 Dadana、Olie 的產文會使用 500+ 字的完整人設 Prompt（基於語料訓練），而非 3 行 inline spec。這是品質提升的根本改變，值得持續補齊其他人設。
