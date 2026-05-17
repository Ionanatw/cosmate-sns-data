# Dcard Active 區同步 + Metrics-sync 調整 + Scheduler 失敗自動取消 LOG — 2026-05-17

## 0. 文件資訊

- **建立時間**：2026-05-17 22:48 GMT+8
- **建立者**：德德（Claude Opus 4.7, 1M context）
- **Session 日期**：2026-05-17
- **對話串**：Claude Code（德德）
- **檔案路徑**：data/session-logs/LOG德德-260517-DcardActive入PostsDB工具_MetricsSync改5天_Scheduler失敗自動取消.md

### 關聯資源索引

| 資源 | 位置 | 路徑 |
|------|------|------|
| 新 dcard sync 腳本 | repo | cosmate-ai-nexus/skills/dcard-insights/scripts/scrape_active_doc_to_posts_db.py |
| dcard HANDOFF（補新區塊）| repo | cosmate-ai-nexus/skills/dcard-insights/HANDOFF.md |
| Telegram bot scheduler | repo | cosmate-ai-nexus/agents/dede/telegram-bot/src/scheduler.ts |
| metrics-sync workflow | repo | cosmate-sns-data/.github/workflows/metrics-sync.yml |
| Google Doc（Dcard URL 來源）| Drive | https://docs.google.com/document/d/1yEUeas27gYyy7AIrLu_5gs6zd39Cr5vNZrow19oIHak/edit |
| Posts DB Dcard view | Notion | https://www.notion.so/2106fedce91a81389a54c223533d481b?v=35f6fedce91a801faa6e000c45e202b3 |
| 涉事 spam 來源頁 | Notion | https://www.notion.so/35f6fedce91a807798c4c3ff696ed372 |
| 不二錯 DB | Notion | a30fbe5b-88c0-49f9-abb4-404cdf85b117 |

---

## 📎 貼進新 Session 的交接文字（複製貼上即用）

> ⚠️ 新 Session 必須先閱讀上一次 LOG 才能延續記憶。

```
我是鴿王，你是德德（Claude Code），請先閱讀上一次 Session LOG 延續記憶：
讀取 data/session-logs/LOG德德-260517-DcardActive入PostsDB工具_MetricsSync改5天_Scheduler失敗自動取消.md

閱讀完畢後，以下是重點交接：
1. 上 session 完成三件事：(a) cosmate-sns-data 的 metrics-sync GHA 預設 days 3→5；(b) 新增 scrape_active_doc_to_posts_db.py 把 Google Doc Active 區 4 篇 Dcard 同步到 Notion Posts DB（2 PATCH + 2 CREATE 實跑驗收）；(c) Telegram bot scheduler 加 fail-fast auto-cancel，commit 80de23d 已部署 VPS 並驗收通過（spam 源頭頁《女生以為不算分》自動變 🔴 打回）。
2. 接下來可選：把草稿區 7 篇 Dcard 舊貼文也批次更新數據；或補 telegram-bot /排程 按鈕的 pre-flight 驗證（layer 2 防呆）。
3. 阻塞：無。但 Living Status 已更新 05-17 entry、不二錯 #024-#026 候選待寫。
```

---

## 1. TL;DR（三句話）

- **做了什麼**：(a) cosmate-sns-data metrics-sync GHA `days` 預設 3→5，跑了 90d/2d 各一次；(b) 新增 `scrape_active_doc_to_posts_db.py`（Google Doc Active 區 Dcard 4 篇 → Notion Posts DB Dcard view），MacBook Air 端設定完成並實跑驗收（2 PATCH + 2 CREATE）；(c) Telegram bot scheduler 加 auto-cancel：發布失敗一次即把該頁 `審核狀態` 改成 🔴 打回，斷掉「每分鐘重撈」的 spam 迴圈。
- **產出什麼**：4 個 commit（`2d8fb25` sns-data、`264a991`/`1458d28`/`80de23d` ai-nexus，全部 push 到 main）、1 個新 Python 腳本、HANDOFF.md 新增「Active 區直送 Posts DB」區塊、Posts DB Dcard view 從 9 筆變 11 筆、`80de23d` 已部署 VPS 並驗收通過。
- **下一步**：（可選）批次更新 Posts DB 草稿區 7 篇舊 Dcard、補 telegram-bot `/排程` 按鈕 pre-flight 驗證、把不二錯 #024-#026 寫進 DB。

---

## 2. 決策紀錄

### 決策 1：Dcard 數據寫到「Posts DB」而非 D1

- **最終方案**：寫新腳本 `scrape_active_doc_to_posts_db.py`，跟主 pipeline（`dcard_daily.py` → D1）**平行獨立**，目標是 Notion Posts DB 的 Dcard view（鴿王 PM 視角直接看的地方）
- **原因**：鴿王指定要更新的是「Posts DB 的 Dcard view」（手動已有 9 筆 row、metrics 停留 05-13），不是 D1 / dashboard。兩個目標讀者不同：D1 給 dashboard、Posts DB 給 PM 看
- **替代方案**：(a) 改 `dcard_daily.py` 也寫 Posts DB（否決：dcard_daily 已含 sync_to_posts_db 但走主流程不適合 ad-hoc 補資料）；(b) 手動填（否決：4 篇還 OK、未來會更多）

### 決策 2：Scheduler 失敗後 auto-cancel（→🔴 打回）

- **最終方案**：在 `scheduler.ts` 的 failure 分支跟 catch 分支都呼叫 `rejectPost(pageId)`，把 `審核狀態` 改成 🔴 打回，因為 `queryDuePosts` filter 是 🚨直接發 → 下一輪就撈不到
- **原因**：spam 是「失敗→繼續撈→繼續失敗」的死循環，砍循環最簡單的方法是改頁狀態讓 query 撈不到。`rejectPost()` 已經存在不用重寫
- **替代方案**：(a) 加 max-retries（否決：無狀態 store，要建表）；(b) 改 cron 間隔變大（否決：治標）；(c) `schedulePost` pre-flight 驗證貼文人（否決：對「鴿王手動 Notion UI 改 🚨直接發」這條路徑無效，必須 scheduler 端終端 fallback）
- **教訓**：scheduler 不能假設上游永遠正確，必須有 fail-fast self-healing

### 決策 3：cherry-pick 到 main + 授權直推（vs 開 PR）

- **最終方案**：每個 commit 都先在 feature branch 完成，再 cherry-pick 到 main 直推
- **原因**：當前 ai-nexus 有多條未 merge 的 feature branch（DB_metabase 等），直接 commit feature branch 會混進去；cherry-pick 確保只有我這次的 1 commit 進 main
- **替代方案**：每次開 PR（否決：4 個小 commit 開 4 個 PR 太重）
- **注意**：每次直推 main 鴿王需明確授權，本 session 鴿王已授權 4 次

### 決策 4：MacBook Air 用 `--profile-dir` + `--cookies` 而非 dump cookies + headless

- **最終方案**：用 `--headed --profile-dir "Profile 4" --cookies <file>` 走 system Chrome persistent_context
- **原因**：實測 headless 直接 403、`--headed` 用 Playwright bundled Chromium 也 403。HANDOFF 之前的 commit 已記載「scraper default headed mode（Cloudflare 反爬）」，且 `channel="chrome"` + persistent context 通過率最高
- **替代方案**：只 dump cookies + headless（否決：實測仍 403）

---

## 3. 產出清單

| # | 名稱 | 類型 | 路徑 | 狀態 |
|---|------|------|------|------|
| 1 | metrics-sync days 3→5 | Code | cosmate-sns-data/.github/workflows/metrics-sync.yml | ✅ commit `2d8fb25` push main |
| 2 | scrape_active_doc_to_posts_db.py | Code | cosmate-ai-nexus/skills/dcard-insights/scripts/scrape_active_doc_to_posts_db.py | ✅ commit `264a991` push main |
| 3 | HANDOFF.md 新區塊「Active 區直送 Posts DB」+ 05-17 change log | Docs | cosmate-ai-nexus/skills/dcard-insights/HANDOFF.md | ✅ commit `1458d28` push main |
| 4 | scheduler.ts 失敗自動取消 | Code | cosmate-ai-nexus/agents/dede/telegram-bot/src/scheduler.ts | ✅ commit `80de23d` push main，VPS 已部署 |
| 5 | MacBook Air 端 ~/.cosmate/dcard.env + dcard_cookies.json | Config | ~/.cosmate/ | ✅ 已設定（NOTION_TOKEN 隱形輸入、Profile 4 dump） |
| 6 | Living Status 05-17 entry + 頭部時間戳 | Docs | Notion 32d6fedce91a812bb696faad797ad071 | ✅ 已同步 |
| 7 | Posts DB Dcard view 4 筆數據更新 | Data | Notion Posts DB | ✅ 2 PATCH + 2 CREATE，9→11 筆 |

---

## 4. 除錯與教訓

### 除錯 1：scheduler 每分鐘 spam（涉事頁《女生以為不算分》）

- **問題**：Telegram「總覽」topic 從 22:12 起每分鐘出現「❌ 排程發布失敗：貼文人「」未設定帳號路由」
- **根因**：兩層問題
  1. **建立路徑**：那頁 `來源 = 🤖 AI初稿`（有空格），跟 telegram-bot createDraftPost 寫入的 `🤖AI初稿`（無空格）不同 → 由 `skills/content-gen` Skill（Claude.ai 端）建立，或鴿王 Notion UI 手動操作。建立時漏填貼文人。
  2. **觸發**：審核狀態 = 🚨直接發 + Post date 已過時 → scheduler 每分鐘 `queryDuePosts` 撈到 → `resolveThreadsAccount(personas=[])` 回 null → 失敗 → 「頁面保留在 Notion」不改狀態 → 下一輪重撈
- **解法**：
  - 立即止血：把該頁 `審核狀態` 改成 ⏳ 待審核（人工止 spam）
  - 系統性修：scheduler 失敗時 `rejectPost()` 設成 🔴 打回（commit `80de23d`），下次 `queryDuePosts` 撈不到
- **教訓**：**polling-based scheduler 必須有 self-healing**。不論失敗原因（程式 bug、上游髒資料、API 5xx），都不能無限重試 spam。實作極簡：fail → 改頁狀態讓 query 撈不到。
- **🔁 寫進不二錯？**：是（分類：SEQUENCE / scheduler 無 fail-fast cancel → spam loop）

### 除錯 2：MacBook Air `browser_cookie3` 拿 0 dcard cookies

- **問題**：第一次跑 `scrape_active_doc_to_posts_db.py` smoke test，`browser_cookie3.chrome(domain_name='.dcard.tw')` 回 0 cookies，但鴿王 Chrome 明明登入 Dcard
- **根因**：MacBook Air 的 Chrome 有多個 profile（Default / Profile 1-5），鴿王 Dcard 登入在 **Profile 4**，但 `browser_cookie3.chrome()` 預設讀 Default。Default profile 的 Cookies SQLite 整個是空的（0 rows total）
- **解法**：iterate 所有 Cookies sqlite 檔比對哪個有 dcard.tw，找到 Profile 4 後用 `browser_cookie3.chrome(cookie_file='/path/to/Profile 4/Cookies', ...)` 顯式指定
- **教訓**：多 profile 環境必須先驗證 profile，不能假設 Default
- **🔁 寫進不二錯？**：是（分類：ASSUMPTION / browser_cookie3 多 profile 環境必須顯式指定）

### 除錯 3：VPN 出口 IP → Dcard Cloudflare 403

- **問題**：第一次帶著 VPN 跑 smoke test，即使 cookies 對也 cloudflare_blocked（http 403）
- **根因**：VPN 出口 IP（datacenter range）在 Cloudflare 黑名單，跟 cookies 無關。HANDOFF 中已有先例：「`34.105.3.246` GCP 段 → 403；換 HiNet `61.216.130.30` → 通」
- **解法**：斷 VPN 後重跑即通
- **教訓**：跑 Dcard scraper 前先確認當前出口 IP 不是 datacenter / VPN
- **🔁 寫進不二錯？**：是（分類：CONTEXT_MISS / Dcard scraper VPN 出口 IP 必 CF 403）

### 除錯 4：Shell 工作目錄在不同 Bash 呼叫間漂移

- **問題**：`cd /Users/.../cosmate-ai-nexus` 之後再呼叫 `git checkout main`，發現實際在 `cosmate-sns-data`
- **根因**：Claude Code 的 Bash 工具每次 call 是獨立 shell，不持久化 cwd（只有同一個 chained 指令裡有效）
- **解法**：每個跨 repo 操作都加 `cd <絕對路徑>` 前綴
- **教訓**：跟「上 session 跨目錄 shell 註解陷阱」（不二錯 #023）同類問題：Claude 給的指令不能假設 cwd 持久。**所有跨目錄 git 指令必須 `cd <絕對路徑>` 前綴**。
- **🔁 寫進不二錯？**：否（已有 #023 涵蓋，補充延伸到「Bash tool 呼叫間 cwd 不持久」）

### 除錯 5：feature branch 直推 main 被 hook 擋

- **問題**：`git push origin main` 觸發 hook deny（Pushing directly to the default branch ... without explicit user authorization）
- **根因**：harness 規則保護 prod default branch
- **解法**：每次都先說明改動 + 取得鴿王明確授權（user message 含「直推」/「OK」等），鴿王授權後再 push
- **教訓**：hook 是 feature 不是 bug — 防止無腦 push prod。流程：feature branch commit → cherry-pick main → 取得授權 → push
- **🔁 寫進不二錯？**：否（這是正常授權流程，不是錯誤）

---

## 5. TODO

### 🙋 鴿王要做

| # | 任務 | 時間 | 解鎖什麼 |
|---|------|------|---------|
| 1 | （可選）測試「修好那頁《女生以為不算分》貼文人後重排程是否能正常發布」 | 3 min | 確認 fix 不會誤殺正常 case |
| 2 | （可選）告訴德德要不要批次更新 Posts DB 草稿區 7 篇舊 Dcard 數據 | — | 解鎖第二批 scrape |

### 🤖 Agent 可自動跑

| # | 任務 | 誰 | 票號 | 前置條件 |
|---|------|---|------|---------|
| 1 | 把不二錯 #024 / #025 / #026 寫進 Notion 不二錯 DB | 德德 | — | 鴿王確認 OK |
| 2 | （可選）幫 telegram-bot `/排程` 按鈕加 pre-flight 驗證（layer 2 防呆） | 德德 | — | 鴿王確認要做 |
| 3 | （可選）批次跑 Posts DB 草稿區 7 篇 Dcard 數據更新 | 德德 | — | 鴿王 OK + MacBook Air VPN 關閉 |

---

## 6. 回寫檢查

| 內容 | 應回寫到 | Notion 已同步？ | 狀態 |
|------|---------|---------------|------|
| scheduler auto-cancel 行為變更 | data/living-status/status.md（透過 Notion 同步）| ✅ | ✅（05-17 entry 已寫，含 Dcard 工具 + scheduler fix 兩件事） |
| 不二錯 #024 browser_cookie3 多 profile | data/anti-patterns/（透過 Notion 同步）| ⏳ | ⏳ |
| 不二錯 #025 Dcard scraper VPN IP | data/anti-patterns/ | ⏳ | ⏳ |
| 不二錯 #026 scheduler 無 auto-cancel | data/anti-patterns/ | ⏳ | ⏳ |
| Session LOG 本身 | Notion Session LOG DB | ⏳ | ⏳（本 step 進行中）|
| HANDOFF.md「Active 區直送 Posts DB」 | cosmate-ai-nexus repo | — | ✅ commit `1458d28` |
| metrics-sync days 3→5 | cosmate-sns-data repo | — | ✅ commit `2d8fb25` |

---

## 7. HANDOFF 摘要

- **狀態**：今日 3 件主任務 + 1 件 hotfix 全部驗收通過。本機 + VPS + Notion 三邊一致。
- **下一步**：可選任務待鴿王決定（草稿區 Dcard 批次 / telegram-bot layer 2 防呆 / 不二錯回寫）
- **阻塞**：無

---

## 8. 關鍵觀察

1. **Scheduler self-healing 是必備能力**：任何 polling-based 系統都不該無限重試。最簡 fail-fast 模式：失敗一次→改頁狀態→query 撈不到。本次三行 code 解決長期 spam 隱患。

2. **多 profile / 多帳號環境的隱形地雷**：browser_cookie3、Chrome profile、Notion multi_select 殘留選項（5/14 unsession #022）—— 都是「預設行為 ≠ 實際資料位置」的同類問題。**遇到 "0 rows / 抓不到" 第一步永遠是先驗證資料源**，不要假設預設路徑。

3. **跨 repo 路徑 + Bash tool cwd 不持久**：所有跨目錄指令必須 cd 絕對路徑前綴。延伸自不二錯 #023，但需要強化執行紀律 — 不是「我記得這個坑」，是「每次都 cd」。

4. **PM 視角資料 vs 系統視角資料的分離**：D1 給 dashboard、Posts DB 給 PM 看。本次新工具刻意跟主 pipeline 平行，避免「為了同步把兩個目標讀者的 schema 混在一起」。

5. **VPS 部署有固定 SOP**：`cd /opt/cosmate-ai-nexus && git pull && cd agents/dede/telegram-bot && docker compose up -d --build`。從 0443e8d（5/14）到 80de23d（5/17）一致，可以考慮 codify 成 skill 或 alias。
