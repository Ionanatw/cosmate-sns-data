# Daily GHA 建立 + Insights 歸檔系統 LOG — 2026-04-21

## 0. 文件資訊

- **建立時間**：2026-04-21 02:59 GMT+8
- **建立者**：德德（claude-sonnet-4-6）
- **Session 日期**：2026-04-21
- **對話串**：德德（Claude Code）
- **執行環境**：Antigravity
- **檔案路徑**：data/session-logs/LOG德德-260421-Daily_GHA建立_Insights歸檔系統_Secrets批次上傳_報告UI改版.md

### 關聯資源索引

| 資源 | 位置 | 路徑 |
|------|------|------|
| daily.sh | threads-dating-app-analysis | scripts/daily.sh |
| daily.yml | threads-dating-app-analysis | .github/workflows/daily.yml |
| analyze_by_topic.py | threads-dating-app-analysis | scripts/analyze_by_topic.py |
| render_daily.py | threads-dating-app-analysis | scripts/render_daily.py |
| generate_html_report.py | cosmate-ai-nexus | skills/threads-insights/scripts/generate_html_report.py |
| render_insights_archive.py | cosmate-ai-nexus | skills/threads-insights/scripts/render_insights_archive.py |
| threads-insights-weekly.yml | cosmate-ai-nexus | .github/workflows/threads-insights-weekly.yml |
| Threads Insights Archive | Cloudflare Pages | https://cosmate-ai-nexus.pages.dev/reports/threads-insights/ |

---

## 📎 貼進新 Session 的交接文字（複製貼上即用）

我是鴿王，你是德德，請先閱讀上一次 Session LOG 延續記憶：
讀取 data/session-logs/LOG德德-260421-Daily_GHA建立_Insights歸檔系統_Secrets批次上傳_報告UI改版.md

閱讀完畢後，以下是重點交接：
1. Daily GHA（threads-dating-app-analysis）+ Threads Insights 週報歸檔系統（cosmate-ai-nexus）均已完成並部署
2. 舊的三份報告（20260418-3days, 20260418-7days, 20260420-7days）已補上「← 歷史週報」導覽，但 metrics 顯示「—」——因為這三份預日期 REPORT_META 注入，下次重新產出才會填入數字
3. 下一步可考慮：定期 cron 排程（目前 daily.yml schedule 已 comment out，需要時解除）；考量把 threads-dating-app-analysis daily 也加上 Cloudflare Pages 部署

---

## 1. TL;DR（三句話）
- 消除了 daily 與 weekly pipeline 共用 `data/per_topic/` 中間檔的風險；建立了 GitHub Actions 一鍵產出 daily 報告（含 Apify 降級）。
- 為 cosmate-ai-nexus Threads Insights 建立了完整歸檔系統（ISO 週分組、REPORT_META 機器可讀 metadata、archive index 頁、topnav 返回連結、一鍵產出按鈕）。
- 批次上傳 25 個 GitHub Secrets（5 帳號 × TOKEN + USERID + Cloudflare 相關）並成功跑通第一次 GHA 自動週報。

---

## 2. 決策紀錄

### 決策 1：pipeline 隔離方案
- **最終方案**：`analyze_by_topic.py` 新增 `--output-dir` 參數，daily 輸出 `data/daily/`，weekly 輸出原本 `data/per_topic/`
- **原因**：最小改動，不破壞 weekly pipeline；daily 的中間檔和產出完全隔離
- **替代方案**：為 daily 建立全新腳本（否決原因：重複代碼；維護兩份難度高）

### 決策 2：GHA token 讀取方式
- **最終方案**：`generate_html_report.py` 改為先讀 `.env.threads`，不存在則 fallback 到 `os.environ`
- **原因**：本機開發不受影響，GHA 透過 secrets 注入即可，不需要兩套讀取邏輯
- **替代方案**：一律用環境變數（否決原因：影響本機開發體驗）

### 決策 3：REPORT_META 注入位置
- **最終方案**：HTML 首行插入 `<!-- REPORT_META: {...} -->` JSON comment
- **原因**：不影響渲染，archive 生成器可用 regex 一行抓取；未來格式升級向後兼容
- **替代方案**：獨立 .json sidecar 檔（否決原因：檔案管理更複雜；deploy 時容易漏傳）

### 決策 4：Cloudflare Pages 部署方式
- **最終方案**：cosmate-ai-nexus 透過 `git push` 自動觸發 CF Pages CD（非 wrangler-action）
- **原因**：repo 已接 CF Pages Git 整合，push 即部署；不需要額外 secrets
- **替代方案**：在 GHA 加 wrangler-action（否決原因：已有 git 整合，多此一舉）

---

## 3. 產出清單

| # | 名稱 | 類型 | 路徑 | 狀態 |
|---|------|------|------|------|
| 1 | analyze_by_topic.py --output-dir | 功能修改 | scripts/analyze_by_topic.py | ✅ |
| 2 | daily.sh Apify fallback | 功能修改 | scripts/daily.sh | ✅ |
| 3 | render_daily.py DAILY_DATA_DIR | 路徑修正 | scripts/render_daily.py | ✅ |
| 4 | .github/workflows/daily.yml | 新建 GHA | .github/workflows/daily.yml | ✅ |
| 5 | generate_html_report.py env fallback | 功能修改 | cosmate-ai-nexus/skills/threads-insights/scripts/generate_html_report.py | ✅ |
| 6 | generate_html_report.py 相對路徑修正 | 修正 | 同上 | ✅ |
| 7 | generate_html_report.py REPORT_META 注入 | 功能新增 | 同上 | ✅ |
| 8 | generate_html_report.py topnav 返回連結 | UI 新增 | 同上 | ✅ |
| 9 | render_insights_archive.py | 新建腳本 | cosmate-ai-nexus/skills/threads-insights/scripts/render_insights_archive.py | ✅ |
| 10 | threads-insights-weekly.yml | 新建 GHA | cosmate-ai-nexus/.github/workflows/threads-insights-weekly.yml | ✅ |
| 11 | index.html 一鍵產出按鈕 | UI 新增 | cosmate-ai-nexus/reports/threads-insights/index.html | ✅ |
| 12 | 舊報告補 topnav | 補丁 | 3 份既有 HTML | ✅ |
| 13 | GitHub Secrets 批次上傳 | 設定 | threads-dating-app-analysis + cosmate-ai-nexus | ✅ |

---

## 4. 除錯與教訓

### 除錯 1：GHA FileNotFoundError（硬寫本機路徑）
- **問題**：`generate_html_report.py` 中 `REPORTS_DIR` 硬寫 `/Users/ionachen/Documents/Claude/cosmate-ai-nexus/...`，GHA 跑到這行直接炸掉
- **根因**：腳本最初在本機開發，沒有考慮 CI 環境
- **解法**：`_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent`，所有路徑改為相對腳本位置推算
- **教訓**：Python 腳本中所有路徑一律用 `Path(__file__).resolve()` 計算，絕對不寫本機絕對路徑
- **🔁 寫進不二錯？**：是（分類：GHA / 路徑）

### 除錯 2：git push 被 reject（fetch first）
- **問題**：本機 push 時遇到 GHA 已有新 commit 在 remote，rebase 衝突
- **根因**：GHA 跑完 commit + push，本機同時有未 push 的變更
- **解法**：`git stash && git pull --rebase && git stash pop && git push`
- **教訓**：有 GHA 自動 commit 的 repo，每次 push 前先 pull --rebase
- **🔁 寫進不二錯？**：是（分類：git / GHA 衝突）

### 除錯 3：既有報告頁缺 topnav
- **問題**：`20260418-3days.html` 等三份舊報告無「← 歷史週報」導覽，因為在 build_html 加 topnav 之前產生
- **根因**：只修改了 build_html template，沒有回填既有檔案
- **解法**：sed patch 所有既有 HTML：`sed -i '' "s|<body>|<body>\n{TOPNAV}|"`
- **教訓**：HTML template 加 UI 元素後，要同時掃現有檔案補丁
- **🔁 寫進不二錯？**：否（情境太 specific）

---

## 5. TODO

### 🙋 鴿王要做

| # | 任務 | 時間 | 解鎖什麼 |
|---|------|------|---------|
| 1 | 決定 daily.yml schedule 何時開啟（目前 comment out） | 隨時 | 全自動每日熱榜 |
| 2 | 確認 cosmate-ai-nexus CF Pages Git 整合正常（push = 部署） | 下次 deploy 前 | 確保 GHA 週報自動上線 |

### 🤖 Agent 可自動跑

| # | 任務 | 誰 | 前置條件 |
|---|------|---|---------|
| 1 | 下次週報產出後確認舊報告 metrics 是否填入（-- 變成數字） | 德德 | 等下次 GHA weekly 成功跑 |

---

## 6. 回寫檢查

| 內容 | 應回寫到 | Notion 已同步？ | 狀態 |
|------|---------|---------------|------|
| Path(__file__) 相對路徑規則 | 不二錯 DB | ⏳ | ⏳ |
| git pull --rebase before push（有 GHA 自動 commit 的 repo） | 不二錯 DB | ⏳ | ⏳ |
| Session LOG 本身 | Notion Session LOG DB | ⏳ | ⏳ |

---

## 7. HANDOFF 摘要

**狀態**：Daily GHA + Insights 歸檔系統完整上線，兩個 repo 均已 push
**下一步**：鴿王決定是否開啟 daily.yml schedule；確認 CF Pages 自動部署鏈路
**阻塞**：無

---

## 8. 關鍵觀察

- `--output-dir` pattern 非常適合「同一分析腳本，不同 pipeline 的輸出隔離」場景。若未來有第三條 pipeline（如 hourly），複用這個 flag 即可，不需改腳本邏輯。
- REPORT_META HTML comment 方案比 sidecar JSON 更健壯——HTML 是單一 deploy 單位，comment 跟著 HTML 走，archive 生成器 regex 一行提取，未來升級欄位只需更新 inject 端和 parse 端。
