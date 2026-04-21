# WoW 多帳號儀表板規劃 + 橋接架構決策 LOG — 2026-04-21

## 0. 文件資訊

- **建立時間**：2026-04-21 12:16 GMT+8
- **建立者**：德德（claude-sonnet-4-6）
- **Session 日期**：2026-04-21
- **對話串**：德德（Claude Code）
- **檔案路徑**：data/session-logs/LOG德德-260421-WoW儀表板規劃_橋接架構決策_指標定案_PP顧問整合.md

### 關聯資源索引

| 資源 | 位置 | 路徑 |
|------|------|------|
| 計劃檔（v3 最終版） | Claude plans | /Users/ionachen/.claude/plans/7-raw-wow-joyful-clarke.md |
| generate_html_report.py | cosmate-ai-nexus | skills/threads-insights/scripts/generate_html_report.py |
| threads-insights-weekly.yml | cosmate-ai-nexus | .github/workflows/threads-insights-weekly.yml |
| threads-analytics-report | Cloudflare Pages | https://threads-analytics-report.pages.dev/ |
| cosmate-ai-nexus CF Pages | Cloudflare Pages | https://cosmate-ai-nexus.pages.dev/reports/threads-insights/ |

---

## 📎 貼進新 Session 的交接文字（複製貼上即用）

我是鴿王，你是德德，請先閱讀上一次 Session LOG 延續記憶：
讀取 data/session-logs/LOG德德-260421-WoW儀表板規劃_橋接架構決策_指標定案_PP顧問整合.md

閱讀完畢後，以下是重點交接：
1. WoW 多帳號儀表板計劃已完整定案（v3），計劃檔在 /Users/ionachen/.claude/plans/7-raw-wow-joyful-clarke.md
2. 本次 session 純規劃，零行程式碼——下一步從 Step 1「建 D1 database」開始實作
3. 關鍵架構決定：Python 暫時 ingestion owner（bridge）→ 直接寫 D1 via CF REST API；Worker 只做唯讀 API；Phase 2 才換 Worker 接管 ingestion（用 Worker Secrets 存 token）

---

## 1. TL;DR（三句話）
- 完整規劃了 Threads 5 帳號 WoW 多時間維度儀表板（DOD/WoW/MOM），含 AI Insights 自動生成。
- 歷經三輪 PP 顧問回饋，架構從「理想分層」收斂到「這週能上線的橋接版」，指標清單按 Threads API 可行性三分層定案。
- 計劃檔（v3）已更新完畢，下一個 session 從建 D1 開始實作，預計 6-8 小時工。

---

## 2. 決策紀錄

### 決策 1：資料存儲選 Cloudflare D1（非 VPS / GitHub JSON）
- **最終方案**：Cloudflare D1 作為主資料庫，Claude Code 透過 D1 MCP 工具直接 SQL 查詢
- **原因**：與現有 CF Pages 同平台；有 D1 MCP 工具；CF Worker 讀 D1 提供 JSON API 給 Perplexity
- **替代方案**：VPS PostgreSQL（否決：管理成本高）；GitHub JSON 快照（否決：AI 工具查詢不便）

### 決策 2：橋接架構——Python 暫時 ingestion owner
- **最終方案**：`fetch_all_accounts.py` 唯一打 Threads API，寫 D1 via CF REST API（bridge write path）；Worker 只讀 D1 提供 API
- **原因**：這週要上線；Worker 成為 ingestion owner 需要 multi-account token 管理（Phase 2 才做）
- **PP 修正**：CF REST API 是 bridge path，文件標明不是終局架構；token 存 Worker Secrets（非 KV）

### 決策 3：指標定義單一來源 metrics.py
- **最終方案**：新建 `skills/threads-insights/scripts/metrics.py`，所有 ER、爆款率、Volatility 計算集中這裡
- **原因**：避免「報表 5.2% / dashboard 5.0% / AI 說 4.8%」三個版本的災難（PP v1 警告）
- **替代方案**：各腳本自行計算（否決：指標分散難維護）

### 決策 4：schema 精簡兩層半
- **最終方案**：normalized（posts + post_metrics_daily + account_snapshots）+ serving（benchmark_snapshots + ai_insights）；raw 層跳過
- **PP 補充**：posts 單表不夠存時間序列變化，需補 `post_metrics_daily`
- **raw 替代**：GHA artifact 保 14 天；需要時補 R2

### 決策 5：quotes 和 profile_views 需補進 API 抓取
- **最終方案**：`fetch_all_accounts.py` 補抓 `quotes` 和 `profile_views`（現有 generate_html_report.py 缺這兩個）
- **ER 公式更新**：(likes+replies+reposts+**quotes**)/views

### 決策 6：Phase 2 路線圖（暫緩）
- Worker 接管 ingestion（token 存 Worker Secrets）
- `skills/threads-insights/` 搬到 `apps/` 或 `analytics/`（語義上更準確）
- 帳號管理 UI

---

## 3. 產出清單

| # | 名稱 | 類型 | 路徑 | 狀態 |
|---|------|------|------|------|
| 1 | WoW 儀表板計劃 v3（橋接版） | 計劃文件 | /Users/ionachen/.claude/plans/7-raw-wow-joyful-clarke.md | ✅ |
| 2 | D1 Schema（5 張表） | 設計文件 | 計劃檔內 | ✅ |
| 3 | 指標定案清單（API 可行性三分層） | 設計文件 | 計劃檔內 | ✅ |
| 4 | 目錄結構確認 | 設計文件 | 計劃檔內 | ✅ |
| 5 | 儀表板 UI 5 Tab 設計 | 設計文件 | 計劃檔內 | ✅ |
| 6 | Worker API contract（5 endpoints） | 設計文件 | 計劃檔內 | ✅ |

---

## 4. 除錯與教訓

本次 session 純規劃，無除錯記錄。

### 觀察 1：兩份 PP 顧問建議互相衝突需整合
- **問題**：PP v1（Worker 是 ingestion owner）vs PP v2（Python 是 ingestion owner，MVP 優先），兩者互相矛盾
- **解法**：橋接版——這週用 v2 的 execution，但 schema 按 v1 的乾淨邊界設計；bridge write path 標明，Phase 2 換軌成本最小
- **🔁 寫進不二錯？**：否（架構判斷情境，不是可複用的錯誤模式）

---

## 5. TODO

### 🙋 鴿王要做

無（所有實作由德德執行）

### 🤖 Agent 可自動跑（下一個 session）

| # | 任務 | 誰 | 前置條件 |
|---|------|---|---------|
| 1 | 建 D1 database `threads-metrics`，執行 schema SQL（5 張表） | 德德 | 無 |
| 2 | 新建 `metrics.py`（指標定義單一來源） | 德德 | D1 建好 |
| 3 | 新建 `fetch_all_accounts.py`（唯一 API 入口，補 quotes + profile_views） | 德德 | metrics.py 完成 |
| 4 | 新建 `generate_ai_insights.py`（只讀 D1 → Claude Haiku） | 德德 | fetch 完成 |
| 5 | 改造 `generate_html_report.py`（改讀 D1，格式不變） | 德德 | fetch 完成 |
| 6 | 建 `infra/threads-metrics-worker/`（TypeScript Worker，5 endpoint 唯讀） | 德德 | D1 建好 |
| 7 | 新建 `wow-dashboard.html`（5 Tab + DOD/WoW/MOM toggle） | 德德 | Worker 完成 |
| 8 | 更新 `threads-insights-weekly.yml`（加 steps + `CF_D1_DATABASE_ID` Secret） | 德德 | 全部完成 |

---

## 6. 回寫檢查

| 內容 | 應回寫到 | Notion 已同步？ | 狀態 |
|------|---------|---------------|------|
| 橋接架構決策（Python bridge ingestion） | 計劃檔 | — | ✅ 已在計劃檔 |
| token 存 Worker Secrets（非 KV）修正 | 計劃檔 | — | ✅ 已在計劃檔 |
| post_metrics_daily 表（PP 補充） | 計劃檔 | — | ✅ 已在計劃檔 |
| D1 REST API = bridge write path | 計劃檔 | — | ✅ 已在計劃檔 |
| Session LOG 本身 | Notion Session LOG DB | ⏳ | ⏳（下一步） |

---

## 7. HANDOFF 摘要

**狀態**：計劃完整定案（v3），零行程式碼。Worker .gitignore 已加 `.worktrees/`，但 worktree 尚未建立。
**下一步**：開新 session → 讀此 LOG → 開始 Step 1（建 D1 via CF MCP）
**阻塞**：無。CF MCP 工具（`mcp__claude_ai_Cloudflare_Developer_Platform__d1_database_create`）已可用。

---

## 8. 關鍵觀察

- **「理想架構 vs 這週上線」是一個真實張力**：PP v1 和 PP v2 都對，但針對不同目標。橋接版的核心是：schema 設計一次做對，ingestion owner 可以之後換，API contract 先固定。
- **指標定義必須集中**：三個地方各自算 ER 是常見陷阱，`metrics.py` 單一來源解決這個問題。
- **D1 REST API 的定位**：Cloudflare 官方說明 REST API 適合 admin/batch write，應用層長期應透過 Worker。這週先用，但文件標明是 bridge，技術債清楚可追蹤。
- **Threads API 不提供非粉絲觀看數**：PP 顧問確認，這個指標不在 v1 範圍，避免做了一半發現拿不到資料。
