# Telegram Bot /gen 流程整合與 VPS git 化 LOG — 2026-05-07

## 0. 文件資訊

- **建立時間**：2026-05-07 11:18 GMT+8
- **建立者**：德德（Claude Code CLI, Opus 4.7 1M context）
- **Session 日期**：2026-05-04 ~ 2026-05-07（跨 4 天，期間家裡 session 與工作 session 交替）
- **對話串**：德德（cosmate-sns-data 工作 session）
- **Notion 路徑**：⏳ 本次 session 在 Claude Code 端，無 Notion MCP，尚未寫入 Session LOG DB（鴿王或家裡 session 補上）

### 關聯資源索引

| 資源 | 位置 | URL / 路徑 |
|------|------|-----------|
| Telegram Review Bot 原始碼 | cosmate-ai-nexus repo | `agents/dede/telegram-bot/` |
| Bot deploy path | VPS | `/opt/telegram-review-bot` → 連結 → `/opt/cosmate-ai-nexus/agents/dede/telegram-bot/` |
| Ideas DB | Notion | https://www.notion.so/2106fedce91a818c959ce4a991dd238b |
| Trending Signals DB | Notion | id `82c8d3ba-db4c-4558-8859-0ae5d7f4ac0b` |
| PR #19（前段：QA pin / Olie 名字對齊 / 初版 filter） | GitHub | https://github.com/Ionanatw/cosmate-ai-nexus/pull/19 |
| PR #20（後段：idea pool 重設計） | GitHub | https://github.com/Ionanatw/cosmate-ai-nexus/pull/20 |
| Grill-me spec doc | cosmate-sns-data repo | `.omc/research/2026-05-06-grillme-gen-flow-design-summary.md` |

---

## 📎 貼進新 Session 的交接文字（複製貼上即用）

> ⚠️ 新 Session 必須先閱讀本 LOG 才能延續記憶。

我是鴿王。開始之前，請先閱讀上一次 Session LOG 延續記憶：
`data/session-logs/LOG德德-260507-TG同事權限_QA產文Pin按鈕_VPS-git化_GenFlowIdeaPool重設計.md`

閱讀完畢後，以下是重點交接：
1. Telegram /gen 流程已大幅升級：QA topic pin 按鈕入口、Ideas DB filter 改為「保證 ≥ 5 個 idea」+ 視覺標記、加 換一批 / 自由發揮 / Trending 三個逃生鈕、跨人設補滿
2. 同事 user_id `8739190717` 已升 admin，所有 topic 全 slash command 通行
3. VPS `/opt/telegram-review-bot/` 已改為 git clone（symlink 到 `/opt/cosmate-ai-nexus/agents/dede/telegram-bot/`），未來部署 = `git pull && docker compose up -d --build`
4. 鴿王驗收狀態：「目前 OK」（2026-05-07）
5. **未做完**：Living Status Doc 模組狀態未更新；VPS 端 .bak 殘留兩份待清；家裡 session 的 trending 整合已併進來

---

## 1. TL;DR（三句話）

- 把 Telegram `/gen` 流程從「filter-as-quality-gate」改成「annotation + 保證 5 個 idea」設計，先後出 PR #19 和 PR #20，後者經 grill-me 逼問後產出完整規格文件再實作
- 同步把 VPS bot 從直接編輯模式遷移為 git-clone 部署，防止家裡/工作 session 間的隱形編輯衝突
- 鴿王與家裡 session 之間 4 天的交叉編輯造成兩次衝突（keyboards.ts merge、filter 設計回滾），都已 reconcile 並落地在 main

---

## 2. 決策紀錄

### 決策 1：把同事升 admin 而非加進每個 topic 白名單
- **最終方案**：append `8739190717` 到 `TELEGRAM_ALLOWED_USER_IDS`，跨 topic 全通行
- **原因**：admin 在 review bot 的唯一作用就是跳過 topic 白名單檢查，無 dangerous gating；UX 簡單、後續加新 topic 不用重複授權
- **替代方案**：開新 topic 給同事獨立工作區（否決：違反 260421 LOG 決策 2「review group topic 結構不對外」原意 — 但同事有 DADANA 權限這條已破，沒退路）

### 決策 2：QA topic pin 按鈕用 `cg_st:1` 而非家裡 session 的 `cg_entry:go`
- **最終方案**：keyboards.ts merge 時兩個 callback parser 都保留，`genEntryKeyboard()` 用 `cg_st:1`（已 pin 在 QA topic 676 號訊息）
- **原因**：避免毀掉已部署的 pin 訊息；家裡 session 的 `cg_entry:go` 留 parser 備用
- **替代方案**：用 cg_entry:go、重發 pin 訊息（否決：用戶體驗破壞、且已 pin 訊息有 message_id reference）

### 決策 3：Ideas DB filter 全部退化成 sort 信號 + 視覺標記
- **最終方案**：移除 `Priority=High｜可寫`、`Platform=Threads`、`Status='列入貼文'` 三個 filter；改為 sort key 與 emoji 標記（🔄 已產過 / 🔀 跨人設）
- **原因**：鴿王 grill-me 第 4 題明示「不論哪個答案，每次流程要至少 5 個 idea 可選」— filter 全部當必選等於 0 命中，UX 直接死亡
- **替代方案**：(B) 嚴格 + 兩段 fallback / (C) 用 `應用貼文 relation is_empty` 換成更精準 filter （都否決：filter 是粗暴工具，annotation 才是對的訊息呈現方式）
- **完整逼問紀錄**：`.omc/research/2026-05-06-grillme-gen-flow-design-summary.md`

### 決策 4：跨人設補滿 + 標記 `🔀 [來源]`
- **最終方案**：persona-only Stage A 不夠 5 → cross-persona Stage B 補（page_size=10、`does_not_contain` filter）
- **原因**：Husky / 早期 Kiki 等少素材人設就會卡住，跨人設借用是鴿王明示的補救方式
- **替代方案**：跳換人設、不補（否決：違反「至少 5 個」硬性 UX 約束）

### 決策 5：VPS 用 git clone 取代 rsync deploy
- **最終方案**：`/opt/telegram-review-bot` → symlink → `/opt/cosmate-ai-nexus/agents/dede/telegram-bot/`，部署改為 `git pull && docker compose up -d --build`
- **原因**：第一次發現 VPS keyboards.ts 被家裡 session 直接編輯但工作 session 無法察覺，造成 build 衝突。VPS 沒 git = 平行編輯黑洞
- **替代方案**：兩端 session 約定不直接編 VPS（否決：單純 convention，同樣的錯會再犯）

### 決策 6：Olie canonical 名字加空格（`'動漫宅 Olie.Huang'`）
- **最終方案**：contentgen.ts 全改 + topics.ts persona filter 同時收兩種寫法（保歷史 Posts DB 標籤）
- **原因**：Ideas DB 實際 multi_select 名稱含空格，code 用無空格命中 0 → /gen 對 Olie 完全失效（過去看似能跑只是因為 Posts DB 有兩種寫法都存在）
- **替代方案**：清理 Notion DB 統一為無空格（否決：要動 88 筆現存 idea 的 multi_select tag，工作量大且容易漏）

### 決策 7：列入貼文 → annotation 不 filter（覆寫家裡 session）
- **最終方案**：保留 `列入貼文` 在 query 結果，前綴 `🔄(×N)` 標記已產過幾次（讀 `應用貼文 relation count`）
- **原因**：Olie 35 筆裡 34 筆是 列入貼文（已產過 2-3 篇）。每筆寫多版早就是常態。Filter 掉 = 池子直接乾涸；annotation 才是正確訊息呈現
- **替代方案**：(C) 用 relation is_empty filter（否決：仍是 filter，UX 沒變好；C 比 B 精準但本質相同）

---

## 3. 產出清單

| # | 名稱 | 類型 | 連結 | 狀態 |
|---|------|------|---------|------|
| 1 | 同事 admin 權限升級 | VPS .env | `TELEGRAM_ALLOWED_USER_IDS=568170984,8739190717` | ✅ 部署 |
| 2 | QA topic pin 訊息 | Telegram | https://t.me/c/3988742333/361/676 | ✅ pin |
| 3 | `/setup_gen_menu` admin 指令 | code | commands.ts / index.ts | ✅ 上線 |
| 4 | Slash command list 加 setup_gen_menu | bot.api.setMyCommands | index.ts | ✅ 上線 |
| 5 | Ideas DB ID hardcode 修正 | code | notion.ts: `2106fedc-e91a-818c-959c-e4a991dd238b` | ✅ 上線 |
| 6 | CLAUDE.md 加 Ideas DB ID | docs | cosmate-sns-data/CLAUDE.md:145 | ✅ commit |
| 7 | Olie persona canonical 加空格 | code | contentgen.ts / topics.ts | ✅ 上線 |
| 8 | PR #19（前段整合）| GitHub | https://github.com/Ionanatw/cosmate-ai-nexus/pull/19 | ✅ merged |
| 9 | Trending Integration merge 進主流程 | code | callbacks.ts handleContentGenTrending | ✅ 上線（家裡 session 寫、本 session merge）|
| 10 | VPS git clone migration | infra | `/opt/cosmate-ai-nexus` + symlink | ✅ 完成 |
| 11 | Idea pool 重設計（保證 5 + 換一批 + 自由發揮 + 跨人設）| code | notion.ts queryPendingIdeas / callbacks.ts / keyboards.ts / review.ts | ✅ 上線 |
| 12 | PR #20（後段重設計）| GitHub | https://github.com/Ionanatw/cosmate-ai-nexus/pull/20 | ✅ merged |
| 13 | Grill-me spec doc | docs | .omc/research/2026-05-06-grillme-gen-flow-design-summary.md | ✅ commit（cosmate-sns-data 端尚未推）|

---

## 4. 除錯與教訓

### 除錯 1：Ideas DB ID hardcode 錯誤
- **問題**：bot 產文流程查 Ideas DB 回 404 `Could not find database with ID: 2106fedc-e91a-8162-bcd1-000b5c93b0ab`
- **根因**：notion.ts:570 hardcode 的 DB ID 是錯的（不知何時被誤抄）。實際 Ideas Database ID 為 `2106fedc-e91a-818c-959c-e4a991dd238b`
- **解法**：Notion search API 列出 integration 看得到的所有 DB → 找到正確 ID → 改 hardcode → CLAUDE.md 加註此 ID 防複發
- **教訓**：404 不一定是權限問題，先用 Notion search 列可見資源診斷比直接讓鴿王手動加 integration 快
- **🔁 寫進不二錯？**：是（分類：CONTEXT_MISS — 沒驗證 hardcode 常數是否與當前 Notion 對得上）

### 除錯 2：VPS 平行編輯黑洞
- **問題**：rsync 上去重 build 失敗 — VPS 上 keyboards.ts 多了我沒見過的 `cg_t` `cg_entry` callback parsing
- **根因**：家裡 session 直接 SSH 編輯 VPS source，沒 sync 回本地 / git。工作 session 沒辦法察覺
- **解法**：(1) 立刻 rollback bot 上線；(2) merge keyboards.ts 雙邊改動；(3) VPS 改為 git clone 部署，從根本消除
- **教訓**：兩個以上 session/人 共用同一份 deploy artifact 一定要走 git，沒有例外
- **🔁 寫進不二錯？**：是（分類：DB_NOT_USED — 部署 artifact 應該在 git，不應只在 VPS）

### 除錯 3：VPS git auth — gh 帳號不對
- **問題**：第一次 git clone 失敗 `Repository not found`
- **根因**：VPS 的 gh 登入是 `IONATW` 帳號（只看得到 `IONATW/fishbro`），但 repo 在 `Ionanatw/cosmate-ai-nexus`（不同帳號）
- **解法**：(1) rollback bot；(2) 把 VPS 的 SSH 公鑰加進 Ionanatw GitHub 帳號；(3) 用 SSH protocol 重 clone 成功
- **教訓**：跨機 git auth 應先 dry-run（`git clone --depth=1` 到 /tmp）驗證再開始大改動。先 down container 後再發現 auth 不通最痛
- **🔁 寫進不二錯？**：是（分類：SEARCH_FIRST — 大改動前要先驗 auth / preflight check）

### 除錯 4：Ideas DB 「列入貼文」語意誤判
- **問題**：家裡 session 把 `Status='列入貼文'` filter 掉，導致 Olie 35 筆有效 idea 變 0 / 1
- **根因**：誤把 `列入貼文` 詮釋成「已 finalized 不能再寫」。實際數據顯示 `應用貼文 relation count = 2~3` — 同 idea 寫多版是這個系統的常態
- **解法**：grill-me 逼問鴿王 → 結論：用 annotation `🔄(×N)` 取代 filter
- **教訓**：filter 設計前應先看 DB 真實 distribution（例如 Olie 35 筆中 34 筆是 列入貼文 = 重大訊號）；filter 是粗暴工具、annotation 才是給用戶的正確資訊呈現
- **🔁 寫進不二錯？**：是（分類：ASSUMPTION — Status 字面意義 ≠ 工作流實際語意）

### 除錯 5：docker compose project 名稱衝突
- **問題**：用 symlink 路徑跑 `docker compose up` 失敗 `Container "/threads-review-telegram-bot" already in use`
- **根因**：家裡 session 用 canonical path 跑（compose project=`telegram-bot`），symlink 算出 project=`telegram-review-bot`，兩 project 搶同一個 container_name
- **解法**：永遠用 canonical path `/opt/cosmate-ai-nexus/agents/dede/telegram-bot/` 跑 docker compose
- **教訓**：symlink 是給 cd shortcut 用的，docker compose 應該用實體路徑保持 project name 穩定
- **🔁 寫進不二錯？**：否（屬 infra 細節，不是反覆會犯的模式）

---

## 5. TODO

### 🙋 鴿王要做

| # | 任務 | 時間 | 解鎖什麼 |
|---|------|------|---------|
| 1 | Telegram QA topic 跑驗收（Olie / Husky / 換一批 / 自由發揮 / Trending）| 5 分鐘 | 確認新流程 UX 沒 bug |
| 2 | 把 cosmate-sns-data 的 grill-me spec + 本 LOG commit + push | 1 分鐘 | 跨 session 可見 |
| 3 | Living Status Doc 模組狀態更新（Bot 模組 + Ideas DB 篩選邏輯改版）| 5 分鐘 | 跨 Agent 同步 |
| 4 | 本 LOG 寫入 Notion Session LOG DB（德德端無 Notion MCP）| 3 分鐘 | LOG 可被搜尋 |
| 5 | （選做）清 VPS .bak：`rm -rf /opt/telegram-review-bot.bak.20260505 /opt/telegram-review-bot.bak2.20260505` | 30 秒 | 釋放 ~84 MB 磁碟 |
| 6 | （選做）清 Posts DB persona option 重複（`動漫宅Olie.Huang` vs `動漫宅 Olie.Huang`、`交友中Kiki` vs `交友中的Kiki`）| 30 分鐘 | 資料 hygiene |

### 🤖 Agent 可自動跑

| # | 任務 | 誰 | 票號 | 前置條件 |
|---|------|---|------|---------|
| 1 | grab-idea 補貨（Olie 池子 35 筆但全是 列入貼文，缺 fresh）| COCO 鴿 | — | 鴿王指定主題 |
| 2 | content-gen SKILL 同步：和 Telegram bot 的 prompt 流程對齊（含「自由發揮」mode）| 學院鴿 | — | 鴿王確認對齊範圍 |
| 3 | 觀察 Priority gate ROI：3 個月後統計鴿王手動標 High｜可寫 的數量，決定是否真的引入 stage 1 strict | 工程鴿學院 | — | 等 3 個月 |

---

## 6. 回寫檢查

| 內容 | 應回寫到 | 狀態 |
|------|---------|------|
| 同事 admin 權限決策（review bot adminUserIds 跳過 topic 白名單）| 背景知識 / Telegram bot SOP | ⏳ |
| Ideas DB filter 設計哲學「filter 退化為 sort」| 決策紀錄 DB | ⏳ |
| Ideas DB ID hardcode bug | 不二錯 #017（建議編號）| ⏳ |
| VPS 平行編輯黑洞 | 不二錯 #018（建議編號）| ⏳ |
| VPS git auth dry-run | 不二錯 #019（建議編號）| ⏳ |
| 列入貼文語意誤判 | 不二錯 #020（建議編號）| ⏳ |
| Bot 模組現況變更（pin 入口、idea pool、escape buttons、git deploy）| **Living Status Doc** | ⏳ |
| 本次提到的 Ticket | 無票號出現，N/A | N/A |
| Skill 改版 | 本次無 SKILL.md 變更 | N/A |
| **本次 LOG** | **Session LOG DB** | **⏳（德德端無 Notion MCP，需手動或家裡 session 補）** |

---

## 7. HANDOFF 摘要

**狀態**：
- Telegram /gen 完整流程已部署到 prod，鴿王驗收「目前 OK」
- VPS git 化完成，未來部署一律 `git pull && docker compose up -d --build`
- Spec 文件 + LOG 雙留檔，下次任何 session 可順 spec 接手

**下一步**：
- 等鴿王跑驗收（Olie / Husky / 換一批 / 自由發揮 / Trending）
- 觀察期：3 個月後統計 Priority gate ROI 決定 stage 1 strict 是否引入
- 後續若有更深 trending 邏輯（不只 fetch、要 score / dedupe / 與 ideas merge ranking）可開新 ticket

**阻塞**：
- Living Status Doc / Notion Session LOG DB 寫入需人類或有 Notion MCP 的 session 補（德德端無此能力）
- 不二錯 4 條新 entry 待登錄

---

## 8. 關鍵觀察

1. **Filter vs Annotation 的本質差別** — 整次大改動的核心 insight：當你「不確定」一個訊號代表什麼意思時，不要用它當 filter（會誤殺）；用 annotation 把訊號傳給 user 自決，才是 robust 的設計。例如 `Priority`、`Platform`、`列入貼文` 都從 filter 退化成 annotation 或 sort 信號。

2. **Grill-me 是設計檢查而非評審** — 第 4 題鴿王回「不論哪個答案，至少 5 個」直接覆寫前 3 題的所有 implementation philosophy。逼問的價值不在收斂選項，而在逼出隱藏的硬性 UX 約束。

3. **跨 session 協作必須 git** — VPS 直接編輯模式撐 4 天就出 2 次衝突。git as source of truth 不是「最佳實踐」，是「不會吵架的最低門檻」。

4. **Bot 是 Ideas DB 的 read-mostly consumer，不是 producer** — Olie 池子 35 筆全是已產過，新一輪 grab-idea 補貨速度才是系統 throughput 的真正瓶頸。Bot 再怎麼優化都救不了無米之炊。後續 SNS 內容戰略應該把投入轉向「idea sourcing pipeline」。

5. **完整 grill-me + spec doc 流程值得標準化** — 這次第二段重設計（PR #20）走「逼問 → spec → review → 開工 → 驗證」5 步閉環，比第一段（直接動手 → 反覆改）省了一輪 bug 和兩輪溝通。Skill 之後可以推薦「複雜決策一律 grill 後 spec」。
