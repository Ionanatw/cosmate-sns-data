# 自動化品質加固 + 選項值 canonical 統一 LOG — 2026-06-16

## 0. 文件資訊

- **建立時間**：2026-06-16 01:53 GMT+8
- **建立者**：德德（Claude Code，Fable 5 / Opus 4.8）
- **Session 日期**：2026-06-12 ～ 2026-06-16（跨數日）
- **對話串**：德德（Claude Code，本機 Mac）
- **檔案路徑**：data/session-logs/LOG德德-260616-改善計劃P1P2實作_選項無空格Canonical統一_本機Skills改Symlink.md

### 關聯資源索引

| 資源 | 位置 | 路徑 / URL |
|------|------|------|
| PR #4（Phase 1-2 加固） | GitHub | https://github.com/Ionanatw/cosmate-sns-data/pull/4（已 merge） |
| 帳號註冊表 | repo | scripts/lib/accounts.py |
| Notion schema 驗證 | repo | scripts/validate_notion_schema.py |
| 跨平台 lint | repo | scripts/lint_repo.py |
| PR smoke fixtures | repo | tests/make_fixtures.py |
| Telegram 通知工具 | repo | scripts/notify_telegram.py |
| lint + smoke workflow | repo | .github/workflows/lint.yml |
| 7 張 Phase 1-2 Ticket | Notion | Ticket DB（P1-1~P2-7，全 ✅ 已完成） |
| 不二錯 #027 | Notion | 不二錯 DB（Notion API rename 選項靜默忽略） |

---

## 📎 貼進新 Session 的交接文字（複製貼上即用）

> ⚠️ 新 Session 必須先閱讀上一次 LOG 才能延續記憶。

```
我是鴿王，你是德德（Claude Code），請先閱讀上一次 Session LOG 延續記憶：
讀取 data/session-logs/LOG德德-260616-改善計劃P1P2實作_選項無空格Canonical統一_本機Skills改Symlink.md

閱讀完畢後，以下是重點交接：
1. 完成了 SNS pipeline 改善計劃 Phase 1-2（PR #4 已 merge）+ 把所有 Notion 選項值統一成「無空格 canonical」（Notion 1,275 頁遷移 + 兩 repo + 本機 skills symlink + VPS bot redeploy）
2. 接下來：改善計劃 Phase 3-4 尚未開票（報告錯字掃描、deploy canary、Trending 寫入驗證、token 到期提醒、不二錯回寫自動化）；nadia token 2026-08-01 到期需提醒
3. 待鴿王手動：claude.ai 重貼 content-gen + grab-idea 兩個 skill（桌面有整合檔）、Notion saved view 篩選若失效要重設、Ideas DB「Status」status 型欄位兩個含空格選項需 UI 手改
```

---

## 1. TL;DR（三句話）
- **做了什麼**：實作 SNS pipeline 改善計劃 Phase 1-2（帳號註冊表、Notion schema 防呆、結果斷言、CI lint、cookies 降級通知、PR smoke test），再把全鏈路選項值統一成「無空格 canonical」。
- **產出什麼**：PR #4（9 commit，已 merge）+ 5 個新腳本/workflow；Notion 1,275 頁選項遷移；兩 repo 寫入端對齊；本機 3 個 skill 改 symlink；VPS telegram-bot redeploy 修掉 400。
- **下一步**：Phase 3-4 待開票；鴿王手動補 claude.ai 兩個 skill + Notion saved view 篩選。

---

## 2. 決策紀錄

### 決策 1：帳號清單建單一註冊表 accounts.py
- **最終方案**：`scripts/lib/accounts.py` 為唯一帳號定義點，shell/python 全部改讀它，CI 加 `--check-workflow` 一致性比對。
- **原因**：帳號清單散落 5+ 處是本 repo 最高頻 bug 來源（amy mapping 漏補、nadia 漏 token 檢查）。
- **替代方案**：每處各自維護（否決：就是現狀，會繼續漏）。

### 決策 2：選項值 canonical 一律「無空格」
- **最終方案**：⏳待審核 / ✅審核通過 / 🔴打回 / 💬有建議 / 🤖AI初稿 / ✍️人工 / 動漫宅Olie.Huang / 文青聽團仔Kevin 等，全部去空格；Notion 端遷移 + 所有寫入端對齊。
- **原因**：鴿王 260612 拍板。「動漫宅 Olie.Huang」空格 bug 已踩 3 次（不二錯 #022），決定根治。
- **替代方案**：保留空格版當 canonical（否決：歷史資料與程式碼多數already無空格，改無空格動的最少）。

### 決策 3：本機 skills 用「逐個 symlink」而非整夾 symlink
- **最終方案**：grab-idea / threads-publisher 各自 symlink 到 repo，其餘不動。
- **原因**：`setup-skills.sh` 是整夾 symlink 到 repo/skills/，但本機 `~/.claude/skills` 已累積大量非鴿舍 skill（gstack/superpowers…），整夾覆蓋會全部消失；且 threads-publisher 在 repo/skills/ 只有 DEPRECATED 殘骸。
- **替代方案**：跑 setup-skills.sh（否決：會誤刪非鴿舍 skill + 載入到廢棄版）。

### 決策 4：threads-publisher 不搬進 skills/
- **最終方案**：維持在 `agents/dede/threads-publisher/`。
- **原因**：有正式架構決策（ai-pigeon-loft-repo-structure-final.md）——它是德德專屬執行工具非共用 skill，且 claude.ai 不載入它。搬進 skills/ 語意反而錯。

---

## 3. 產出清單

| # | 名稱 | 類型 | 路徑 | 狀態 |
|---|------|------|------|------|
| 1 | 帳號單一註冊表 | code | scripts/lib/accounts.py | ✅ merged |
| 2 | Notion schema 防呆 | code | scripts/validate_notion_schema.py | ✅ merged |
| 3 | 跨平台 lint | code | scripts/lint_repo.py | ✅ merged |
| 4 | PR smoke fixtures | code | tests/make_fixtures.py | ✅ merged |
| 5 | Telegram 通知工具 | code | scripts/notify_telegram.py | ✅ merged |
| 6 | lint + smoke workflow | ci | .github/workflows/lint.yml | ✅ merged |
| 7 | token-health 補 nadia | ci | .github/workflows/token-health-check.yml | ✅ merged |
| 8 | metrics-sync 掛 schema 驗證 + 結果斷言 | ci/code | metrics-sync.yml / fetch_insights.sh / sync_to_notion.py | ✅ merged |
| 9 | Notion 選項遷移（兩波，1,275 頁） | data | Posts DB + Ideas DB | ✅ 完成 |
| 10 | nexus 寫入端 canonical（27 檔） | code | telegram-bot/discord-bot/threads-publisher/content-gen/grab-idea/dcard-insights | ✅ pushed |
| 11 | 本機 3 skill 改 symlink | infra | ~/.claude/skills/{content-gen,grab-idea,threads-publisher} | ✅ 完成 |
| 12 | VPS telegram-bot redeploy | infra | hostinger-vps:/opt/cosmate-ai-nexus | ✅ 完成 |
| 13 | claude.ai skill 重貼整合檔 | doc | ~/Desktop/claude-ai-skills-重新同步-260616.md | ✅ 產出（待鴿王貼） |

---

## 4. 除錯與教訓

### 除錯 1：VPS telegram-bot 早安挑稿 400
- **問題**：260612 09:00 早安挑稿失敗，Notion query 400「`✅ 審核通過` not found」。
- **根因**：Notion 選項已改名（去空格），但 VPS 上 bot 跑兩週前舊 build，查詢仍用舊值「✅ 審核通過」。
- **解法**：SSH 進 VPS 跑 `git pull && docker compose up -d --build`，新 build 內全無空格版，bot 同款查詢重演成功。
- **教訓**：改 Notion 選項 = 所有消費端（含 VPS 已部署服務）都要同步，「source 改完」≠「線上生效」。
- **🔁 寫進不二錯**：已含於 canonical 統一脈絡，併入 #027 敘事。

### 除錯 2：Notion API rename select 選項靜默忽略
- **問題**：v1 遷移用 `PATCH /databases` 傳「舊 id + 新名」想 rename，回 200 但名稱沒改。
- **根因**：Notion API 不支援 rename select/multi_select 選項，靜默忽略；同 PATCH 內的「移除選項」卻有效，易誤判全成功。
- **解法**：改三步法——加新選項 → query 搬頁改值 → 刪舊選項；且改完重拉 schema 驗證，不只看 HTTP 200。
- **教訓**：Notion 選項 rename 必用三步法。
- **🔁 寫進不二錯**：✅ 已建 #027（分類 ASSUMPTION）。

### 除錯 3：本機 grab-idea 停在舊版 v2.2
- **問題**：本機 `~/.claude/skills/grab-idea` 是獨立 copy，停在 v2.2（缺 v3.3 的「claude.ai/德德 不得寫 Notion」執行護欄）。
- **根因**：setup-skills.sh 當初沒把它 link 進去（只 content-gen 是 symlink），git pull 不會更新。
- **解法**：改 symlink → 立即升 v3.3。
- **教訓**：「獨立 copy」的 skill 會悄悄漂移到舊版，symlink 才能保證跟 GitHub 一致。

---

## 5. TODO

### 🙋 鴿王要做

| # | 任務 | 時間 | 解鎖什麼 |
|---|------|------|---------|
| 1 | claude.ai 重貼 content-gen + grab-idea（桌面整合檔，各 2-3 行差異） | 有空時 | claude.ai 端不再寫回帶空格值 |
| 2 | Notion saved view 篩選若失效（option id 已換）重設一次 | 遇到再做 | view 顯示正常 |
| 3 | Ideas DB「Status」status 型欄位「⚠️ 資訊待校對 / ⏰ 已過期」UI 手改去空格 | 有空時 | 該欄位 canonical 完整 |
| 4 | nadia Threads token 2026-08-01 到期前換新 | 2026-07-25 前 | metrics-sync nadia 不斷線 |

### 🤖 Agent 可自動跑

| # | 任務 | 誰 | 票號 | 前置條件 |
|---|------|---|------|---------|
| 1 | 改善計劃 Phase 3（報告錯字掃描 / deploy canary / Trending 寫入驗證） | 德德 | 待開 | 鴿王點頭 |
| 2 | Phase 4（token 到期提醒 workflow / 新帳號 SOP 腳本 / 不二錯回寫自動化） | 德德 | 待開 | 鴿王點頭 |
| 3 | setup-skills.sh 加註解：勿在已累積非鴿舍 skill 的機器整夾覆蓋 | 德德 | 待開 | — |

---

## 6. 回寫檢查

| 內容 | 應回寫到 | Notion 已同步？ | 狀態 |
|------|---------|---------------|------|
| 選項值無空格 canonical 決策 | Instruction（高頻錯字/選項規範） | ⏳ | ⏳ 建議升級進 Instruction |
| Notion API rename 三步法 | 不二錯 DB #027 | ✅ | ✅ |
| 選項 canonical 全鏈路狀態 | Claude Memory | ✅（notion-option-canonical-no-space） | ✅ |
| 五大反覆糾正模式 | Claude Memory | ✅（recurring-correction-patterns） | ✅ |
| 7 張 Phase 1-2 Ticket | Ticket DB | ✅ 全 ✅ 已完成 | ✅ |
| Session LOG 本身 | Notion Session LOG DB | ⏳ | ⏳ 本步驟處理中 |

---

## 7. HANDOFF 摘要

**狀態**：改善計劃 Phase 1-2 全數上線並 merge；選項 canonical 統一在所有可自動化環節完成並驗證（Notion 1,275 頁、兩 repo、本機 skills、VPS bot、n8n 確認免動）。
**下一步**：Phase 3-4 待鴿王決定是否開票；鴿王手動補 claude.ai 兩 skill + Notion view 篩選。
**阻塞**：無技術阻塞。claude.ai Project Skills 無 API，只能鴿王 UI 手貼。

---

## 8. 關鍵觀察

- 這次最大的系統性收穫不是個別修補，而是把「單一事實多處複製」這個最高頻 bug 模式，用 accounts.py 註冊表 + CI 一致性檢查 + validate_notion_schema.py 三道關卡擋在 PR / 每日同步階段——從「事故驅動」轉為「事前攔截」。
- 選項統一過程本身又示範了同一個模式的另一面：source 改完不等於生效，VPS bot、本機 skill copy、claude.ai skill 三個「離線副本」都是潛在污染源；symlink 化解掉本機那條，VPS 靠 redeploy SOP，claude.ai 只能靠人。
- 「版本號相同、檔案幾乎一樣」是最危險的偽安全感——content-gen claude.ai 版只差 2 行卻足以再污染整個 DB。
