# Olie 貼文人空格 Bug 根因排查 + Telegram 修文自動審核通過 LOG — 2026-05-14

## 0. 文件資訊

- **建立時間**：2026-05-14 11:22 GMT+8
- **建立者**：德德（Claude Opus 4.7, 1M context）
- **Session 日期**：2026-05-14
- **對話串**：Claude Code（德德）
- **檔案路徑**：data/session-logs/LOG德德-260514-Olie貼文人空格Bug根因_修文自動審核通過_RemoteURL救援.md

### 關聯資源索引

| 資源 | 位置 | 路徑 |
|------|------|------|
| Telegram bot src | repo | cosmate-ai-nexus/agents/dede/telegram-bot/src/ |
| threads-publisher SKILL | repo | cosmate-ai-nexus/agents/dede/threads-publisher/SKILL.md、skills/threads-publisher/SKILL.md |
| 修復 commit | GitHub | `0443e8d` on cosmate-ai-nexus@main |
| 涉事貼文 | Notion | https://www.notion.so/35f6fedce91a81ce90a9d59bf2db39e2 |
| 不二錯 DB | Notion | a30fbe5b-88c0-49f9-abb4-404cdf85b117 |

---

## 📎 貼進新 Session 的交接文字（複製貼上即用）

> ⚠️ 新 Session 必須先閱讀上一次 LOG 才能延續記憶。

```
我是鴿王，你是德德（Claude Code），請先閱讀上一次 Session LOG 延續記憶：
讀取 data/session-logs/LOG德德-260514-Olie貼文人空格Bug根因_修文自動審核通過_RemoteURL救援.md

閱讀完畢後，以下是重點交接：
1. 上 session 修好兩個 Bug：(a) 清除程式碼/SKILL.md 殘留的「動漫宅 Olie.Huang」（有空格）變體；(b) Telegram bot 修文後自動把審核狀態改為 ✅ 審核通過。Commit 0443e8d 已推到 GitHub main。
2. 接下來要做：在 VPS（/opt/cosmate-ai-nexus）跑 `git pull && cd agents/dede/telegram-bot && docker compose up -d --build` 讓 Telegram bot 容器吃到新 fix。
3. 阻塞：無。但 VPS 部署尚未驗收。部署後請鴿王在 Telegram olie topic 實測修文流程，確認回覆訊息有出現「審核狀態：✅ 審核通過」。
```

---

## 1. TL;DR（三句話）

- **做了什麼**：診斷「Telegram 修文後 Olie 貼文 SCAN 不到」的 bug，找出根因（Notion DB 「貼文人」multi_select 有重複選項：`動漫宅Olie.Huang` 無空格 vs `動漫宅 Olie.Huang` 有空格殘留）；清除所有程式碼層的有空格變體；新增「修文後自動標記審核通過」邏輯。
- **產出什麼**：cosmate-ai-nexus commit `0443e8d`（6 檔修改），新增 `markAsApproved()`，移除容錯網中的有空格變體，三份 threads-publisher SKILL.md 路由表同步收斂。順便救回鴿王誤跑 `git remote set-url` 把 cosmate-sns-data 指錯到 cosmate-ai-nexus 的事故。
- **下一步**：VPS 端 `git pull && docker compose up -d --build` 讓 Telegram bot 吃到新 fix。

---

## 2. 決策紀錄

### 決策 1：徹底移除容錯網 vs 保留容錯網

- **最終方案**：徹底移除程式碼層所有「動漫宅 Olie.Huang」（有空格）變體
- **原因**：鴿王已把 Notion DB 「貼文人」multi_select 重複選項合併，源頭清乾淨後容錯網沒有保留必要；保留只會掩蓋未來再發生同類資料污染的問題
- **替代方案**：保留 dual-listing 當防呆網（否決原因：違反鴿王明確指令「不要再有"動漫宅 Olie.Huang"的貼文人設定」）

### 決策 2：修文後自動審核通過的實作位置

- **最終方案**：新增獨立函式 `markAsApproved(pageId)` 在 notion.ts，在 index.ts 修文流程的 `updatePostBody` 後接呼叫
- **原因**：保持 `updatePostBody` 單一職責（只動 body blocks），不擴張既有契約；獨立函式可日後複用
- **替代方案**：直接擴張 `updatePostBody` 一併 PATCH properties（否決原因：違反 SRP，且函式名稱會誤導）

### 決策 3：commit 範圍只含 src/ + SKILL.md，不含 dist/

- **最終方案**：只 git add 我改的 6 個 src/SKILL 檔案
- **原因**：dist/ 累積了大量 pre-existing drift（其他 src 改動未 build），混進來會污染這次 commit 訊息
- **替代方案**：連 dist/ 一起 commit（否決原因：跨越本次任務範圍）

### 決策 4：cosmate-sns-data remote URL 救回——讓鴿王自己跑

- **最終方案**：把救回指令給鴿王自己貼進 terminal
- **原因**：CLAUDE.md 規則「NEVER update the git config」；後來鴿王明確授權「這次你去設定，我同意你一次權限」後才由我代執行 cosmate-ai-nexus 的 URL 更新
- **教訓**：使用者明確授權可覆蓋系統規則（user instruction > superpowers > default system prompt）

---

## 3. 產出清單

| # | 名稱 | 類型 | 路徑 | 狀態 |
|---|------|------|------|------|
| 1 | 移除有空格 Olie 容錯 | Code | agents/dede/telegram-bot/src/config.ts、topics.ts | ✅ 已 commit |
| 2 | markAsApproved 函式 | Code | agents/dede/telegram-bot/src/notion.ts | ✅ 已 commit |
| 3 | 修文流程串接 markAsApproved | Code | agents/dede/telegram-bot/src/index.ts | ✅ 已 commit |
| 4 | 路由表同步收斂 | Docs | agents/dede/threads-publisher/SKILL.md、skills/threads-publisher/SKILL.md | ✅ 已 commit |
| 5 | user-scope skill 同步 | Docs | ~/.claude/skills/threads-publisher/skill.md | ✅ 已改（非 git） |
| 6 | commit `0443e8d` 推到 main | Git | cosmate-ai-nexus@main | ✅ 已 push |

---

## 4. 除錯與教訓

### 除錯 1：「修文後 SCAN 不到」的根因排查

- **問題**：鴿王在 Telegram bot 點「📝 修文」改 Olie 貼文後，Notion 上「貼文人」欄位變成「動漫宅 Olie.Huang」（有空格），且 SCAN 撈不到該貼文
- **根因**：兩層問題堆疊
  1. Notion Posts DB 的「貼文人」multi_select 欄位歷史上有兩個並存選項：`動漫宅Olie.Huang`（無空格，現行寫入值）與 `動漫宅 Olie.Huang`（有空格，舊版殘留）
  2. Telegram bot `updatePostBody` 只動 body blocks，**不會主動寫貼文人**——所以「修文後變成有空格」不是 bot 寫入造成的，而是鴿王（或其他 MCP 工具）在 Notion 上手動操作時，multi_select picker 顯示了兩個選項，誤點到有空格那個
  3. 「SCAN 不到」其實不該發生——`topics.ts` 的 personaFilter 容錯網兩個變體都有列。實測撈 Notion 該頁屬性，所有 query 條件都通過。最可能解釋是鴿王 SCAN 時間點與 Notion 屬性實際狀態的時序問題（已被 Notion 合併操作掩蓋，無法回溯驗證）
- **解法**：
  - 鴿王在 Notion 端合併重複選項（已執行）
  - 程式碼端徹底移除有空格變體（本 session）
- **教訓**：Notion multi_select 欄位的「歷史選項殘留」是隱形地雷——一旦曾有不同字面值被寫入，選項列表會永久保留，未來編輯時容易誤點到舊值。**新增 multi_select 寫入路徑時，必須只透過程式碼常數寫入；發現重複選項時，第一時間在 Notion DB 設定上合併，不要靠程式碼容錯網長期擋**。
- **🔁 寫進不二錯？**：是（分類：Notion 資料層 / multi_select 選項治理）

### 除錯 2：rm 鴿王在錯目錄跑 `git remote set-url`

- **問題**：鴿王在 `cosmate-sns-data` 目錄跑了我建議給 `cosmate-ai-nexus` 的 `git remote set-url`，把 sns-data 的 remote 指向了 ai-nexus
- **根因**：我給指令時沒明確要求先 `cd` 到正確目錄；且指令含 inline `# comment`，鴿王的 zsh 沒開 `interactive_comments`，導致 `#` 被當 arg 一起傳給 git
- **解法**：請鴿王在 cosmate-sns-data 重跑 `git remote set-url origin git@github.com:Ionanatw/cosmate-sns-data.git` + `git fetch` 驗證
- **教訓**：給跨目錄的指令必須 (1) 前綴 `cd <絕對路徑>`，(2) 不要在 shell command 後面加 `# 註解`（zsh interactive 預設不解析），改用獨立行的說明或 echo
- **🔁 寫進不二錯？**：是（分類：跨 repo 指令交付 / shell 註解陷阱）

---

## 5. TODO

### 🙋 鴿王要做

| # | 任務 | 時間 | 解鎖什麼 |
|---|------|------|---------|
| 1 | VPS 端 `cd /opt/cosmate-ai-nexus && git pull && cd agents/dede/telegram-bot && docker compose up -d --build` | 5 min | 讓 Telegram bot 吃到新 fix |
| 2 | 部署後在 Telegram olie topic 實測「修文」流程 | 3 min | 驗證 markAsApproved 串接正常，回覆訊息含「審核狀態：✅ 審核通過」 |
| 3 | （可選）VPS 容器內驗證舊變體已清除：`docker exec threads-review-telegram-bot grep "動漫宅" /app/dist/topics.js /app/dist/config.js` 應只剩無空格版本 | 1 min | 確認部署生效 |

### 🤖 Agent 可自動跑

| # | 任務 | 誰 | 票號 | 前置條件 |
|---|------|---|------|---------|
| —  | （本 session 無遺留可自動執行任務）| — | — | — |

---

## 6. 回寫檢查

| 內容 | 應回寫到 | Notion 已同步？ | 狀態 |
|------|---------|---------------|------|
| 不二錯：Notion multi_select 選項殘留治理 | 不二錯 DB | ⏳ | ⏳ |
| 不二錯：跨目錄 shell 指令陷阱 | 不二錯 DB | ⏳ | ⏳ |
| Telegram bot 修文流程行為變更（自動審核通過）| threads-publisher 知識/Living Status | — | ⏳（待 VPS 部署完再更新） |
| Session LOG 本身 | Notion Session LOG DB | ⏳ | ⏳ |

---

## 7. HANDOFF 摘要

- **狀態**：程式碼修復 + commit + push 完成。本機端全部收斂。
- **下一步**：VPS 部署（鴿王手動）+ 實測驗收。
- **阻塞**：無。

---

## 8. 關鍵觀察

1. **容錯網是會債的**：當資料層污染源被清除後，程式碼層的容錯設計（如 dual-listing）反而會掩蓋同類問題重現。應該定期檢視「為了某個歷史 bug 加的容錯」是否還有存在必要。
2. **Notion multi_select 選項治理需建立 SOP**：未來任何寫入 multi_select 的程式碼必須使用單一常數來源（已透過 `PERSONA_KEY_MAP` 達成）；但 Notion DB 端的選項清單同樣需要定期審視，發現非預期值就立刻合併。
3. **使用者指令的優先級**：CLAUDE.md 規則「NEVER update the git config」在使用者明確說「我同意你一次權限」時被合法覆蓋。superpowers 框架的 instruction priority 明確處理此情境（user > skills > default），本 session 是一次乾淨的應用。
