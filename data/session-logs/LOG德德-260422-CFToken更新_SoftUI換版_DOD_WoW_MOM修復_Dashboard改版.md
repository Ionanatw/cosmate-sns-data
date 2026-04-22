# Dashboard 全面改版 + CF Token 安全處理 LOG — 2026-04-22

## 0. 文件資訊

- **建立時間**：2026-04-22 23:18 GMT+8
- **建立者**：德德（claude-sonnet-4-6）
- **Session 日期**：2026-04-22
- **對話串**：德德（Claude Code）
- **檔案路徑**：data/session-logs/LOG德德-260422-CFToken更新_SoftUI換版_DOD_WoW_MOM修復_Dashboard改版.md

### 關聯資源索引

| 資源 | 位置 | 路徑 |
|------|------|------|
| wow-dashboard.html | cosmate-ai-nexus | reports/threads-insights/wow-dashboard.html |
| ui-ux-pro-max skill | cosmate-ai-nexus | .claude/skills/ui-ux-pro-max/ |
| GHA Secret | GitHub | ionanatw/cosmate-ai-nexus → CF_API_TOKEN |
| WoW 儀表板計劃 v3 | Claude plans | /Users/ionachen/.claude/plans/7-raw-wow-joyful-clarke.md |

---

## 📎 貼進新 Session 的交接文字（複製貼上即用）

我是鴿王，你是德德，請先閱讀上一次 Session LOG 延續記憶：
讀取 data/session-logs/LOG德德-260422-CFToken更新_SoftUI換版_DOD_WoW_MOM修復_Dashboard改版.md

閱讀完畢後，以下是重點交接：
1. WoW 儀表板 Phase 1 前端全部完成：Soft UI Evolution 風格、DOD/WoW/MOM toggle 修復、指標說明 + 業界基準、AI Insights 全改版（健診卡 + 領先指標週行動清單）、X軸時間標籤
2. CF_API_TOKEN 已更新（舊 token cfut_BCB... 需確認已 revoke，鴿王已執行 gh secret set）
3. Phase 2 待做：Worker 接管 ingestion（token 改存 Worker Secrets）、follower/profile_views 待 Threads API 修復後補抓

---

## 1. TL;DR（三句話）

- 完成 WoW 儀表板前端全面升級：安裝 uipro-cli、套用 Soft UI Evolution 風格、修復 DOD/WoW/MOM toggle、修正 Engagement Mix、加入指標說明與業界基準。
- AI Insights tab 全面改版：從淺層 rule-based alerts 升級為「本週帳號健診 + 領先指標週行動清單 + 警示 + Haiku 洞察」四層結構，每帳號產出具體 tips。
- CF_API_TOKEN 因舊 token 外洩，已引導鴿王透過 gh secret set 更新 GHA Secret；Phase 2 Worker ingestion 接管待下一個 session 執行。

---

## 2. 決策紀錄

### 決策 1：uipro-cli 安裝方式
- **最終方案**：`npm install -g uipro-cli`，在 cosmate-ai-nexus 目錄執行 `uipro init --ai claude`，Skill 安裝至 `.claude/skills/ui-ux-pro-max/`
- **原因**：鴿王指定，該工具提供 67 種 UI 風格的設計系統查詢腳本
- **替代方案**：手動套用 CSS（否決：鴿王要求走正式 skill 安裝流程）

### 決策 2：Soft UI Evolution 設計系統
- **最終方案**：主色 `#2563EB`（藍）取代原本紫 `#8b62cc`；多層 soft shadow；Fira Code + Fira Sans 字型；背景 `#EEF2F8`
- **原因**：Analytics Dashboard 適合藍色系 + 等寬字型呈現數據，WCAG AA+ 合規
- **補充**：Analytics Dashboard 設計系統由 `search.py "analytics dashboard data visualization SaaS" --design-system` 查詢得出

### 決策 3：DOD/WoW/MOM toggle 修復
- **問題根因**：`renderTrends()` 硬寫 `wow_views`/`wow_er`，不讀 `state.period`
- **最終方案**：改為 `latest?.[`${p}_views`]` 動態取值；section title 和表頭也動態更新
- **補充**：目前 D1 只有一週資料，delta 欄位 NULL 屬 cold start 正常現象，下週 GHA 執行後才會有值

### 決策 4：AI Insights 架構重設計
- **最終方案**：四層 — A. 本週帳號健診卡（ER/發文/Volatility/最佳格式）→ B. 領先指標週行動清單（規則引擎，每帳號 ≤3 tips）→ C. 規則型警示 → D. Haiku 洞察
- **原因**：原版只有 rule-based alerts，缺乏「每帳號可執行的週方向」
- **三個 helper functions**：`getERBenchmark(followers)`、`getBestFormat(account)`、`getWeeklyTips(snap)`

---

## 3. 產出清單

| # | 名稱 | 類型 | 路徑 | 狀態 |
|---|------|------|------|------|
| 1 | Soft UI Evolution 風格套用 | CSS 改版 | reports/threads-insights/wow-dashboard.html | ✅ |
| 2 | DOD/WoW/MOM toggle 修復 | JS bug fix | 同上 | ✅ |
| 3 | 趨勢圖 X 軸標籤（W-7…本週） | JS 功能 | 同上 | ✅ |
| 4 | Engagement Mix 去 % + Amy footnote | JS fix | 同上 | ✅ |
| 5 | Volatility Score 說明文字 | HTML 內容 | 同上 | ✅ |
| 6 | 指標說明可折疊 card（含業界基準） | HTML 功能 | 同上 | ✅ |
| 7 | AI Insights tab 全面改版 | JS 重寫 | 同上 | ✅ |
| 8 | CF_API_TOKEN GHA Secret 更新 | 安全處理 | GitHub Actions Secrets | ✅ |
| 9 | uipro-cli v2.2.3 安裝 | CLI 工具 | npm global | ✅ |
| 10 | ui-ux-pro-max skill 安裝 | Skill | cosmate-ai-nexus/.claude/skills/ui-ux-pro-max/ | ✅ |

---

## 4. 除錯與教訓

### 除錯 1：gh secret set 指令語法錯誤
- **問題**：鴿王把 token 值直接附在指令後面，收到 `accepts at most 1 arg(s), received 2`
- **根因**：`gh secret set` 只接受 secret 名稱，token 值要在 prompt 輸入，不能當 arg 傳入
- **解法**：`gh secret set CF_API_TOKEN --repo ionanatw/cosmate-ai-nexus` → 互動式貼入
- **🔁 寫進不二錯？**：否（通用 CLI 使用知識，非 AI 鴿舍特定錯誤）

### 除錯 2：DOD/WoW/MOM 沒有啟動任何畫面
- **問題**：切換 period toggle 後數據沒有更新
- **根因**：`renderTrends()` 硬寫 `wow_views`/`wow_er`；section title 和表頭也是靜態
- **解法**：三處改動（delta value、section title、table header 全改為動態）
- **補充**：目前 delta 欄位 NULL 是 D1 冷啟動正常，不是 bug
- **🔁 寫進不二錯？**：否（屬架構設計問題，已修復）

---

## 5. TODO

### 🙋 鴿王要做

| # | 任務 | 說明 |
|---|------|------|
| 1 | 確認 revoke 舊 CF Token | 進 CF Dashboard → My Profile → API Tokens，刪除 cfut_BCB... |

### 🤖 Agent 可自動跑（下一個 session）

| # | 任務 | 誰 | 前置條件 |
|---|------|---|---------|
| 1 | Worker 接管 ingestion（Phase 2） | 德德 | 鴿王建新 CF Token 並設定 Worker Secrets |
| 2 | follower_count / profile_views 補抓 | 德德 | Threads API 修復後 |

---

## 6. 回寫檢查

| 內容 | 應回寫到 | Notion 已同步？ | 狀態 |
|------|---------|---------------|------|
| Soft UI Evolution 設計系統參數 | 計劃檔（若需保留） | — | ⏳ 可選 |
| AI Insights 三 helper functions 架構 | 計劃檔 Phase 2 | — | ⏳ |
| Session LOG 本身 | Notion Session LOG DB | ⏳ | ⏳ |

---

## 7. HANDOFF 摘要

**狀態**：WoW 儀表板 Phase 1 前端全部完成；CF Token 已更新。
**下一步**：Phase 2 — Worker 接管 ingestion（鴿王先確認舊 Token revoke + 新 Token 建立後，德德開始 Phase 2 實作）。
**阻塞**：Phase 2 執行前需要鴿王建立新 CF Token 並設定 Worker Secrets；Threads API 尚未提供 follower_count 和 profile_views，Phase 2 這兩個指標暫時 skip。

---

## 8. 關鍵觀察

- **uipro-cli 是個設計智能 CLI**：內含 67 種 UI 風格、96 色板、57 字型配對的查詢腳本（`search.py`），未來改版任何頁面可直接呼叫取得設計系統建議，避免從零開始配色。
- **領先指標 vs 落後指標的區別**：Views/ER/Followers 都是落後指標（反映過去表現）；Posting Frequency、Content Format Mix、Posting Timing 才是真正的領先指標（預測未來表現）。這個區別是本次 AI Insights 改版的核心思路，值得寫進 PM 思維升級材料。
- **Cold Start 必然遇到空值**：任何依賴時間序列比較的系統，第一次執行時 delta 欄位必然是 NULL。設計上應讓 NULL 有合理顯示（N/A），而不是讓 UI 破版或顯示 0。
