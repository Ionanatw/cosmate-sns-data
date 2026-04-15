# Threads 週一熱榜 — 規格 + 工作流程

**呼叫別名**：`threads-weekly` / `monday-threads-report` / `週一熱榜`

鴿王對任一別名喊出來 → Agent 執行本文件的完整流程。

---

## 1. 報告目標

每週一產出一份 Threads 四區塊熱榜報告，用於：
- **市場熱榜（anime × love × cosplay）**：觀察 Threads 垂直社群近期流行話題，找鴿舍貼文內容靈感
- **CosMate 自家表現**：追蹤 @cosmatedaily 近期貼文成效（官方 Threads Graph API）
- 驗證 Coser / 動漫宅 / 交友話題在 Threads 的熱度差異
- 市場熱榜與自家表現並列，能快速看出「市場在紅什麼」vs「我們的哪幾篇打中」

**非目標**：帳號深度 insights 週報（那是 `threads-insights` skill 的範圍）、訓練口吻 corpus（那是 `extract_training_corpus.py` 的範圍）。

---

## 2. 產出

| 檔案 | 用途 |
|---|---|
| `data/raw/{topic}_{timestamp}.json` | Apify 爬蟲原始資料（按主題分檔）|
| `data/per_topic/{topic}.json` | 每主題結構化分析結果（排行、統計、分類）|
| `index.html` | 三 tab 儀表板（瀏覽器直接打開可看）|
| Cloudflare Pages: `https://threads-analytics-report.pages.dev` | 部署線上版 |

---

## 3. 流程總覽

```
┌──────────────────┐     ┌──────────────────────┐     ┌────────────────────┐     ┌──────────────┐
│ Step 1: 爬取     │ ──▶ │ Step 2: 單主題分析   │ ──▶ │ Step 3: 產 HTML    │ ──▶ │ Step 4: 部署 │
│ Apify Threads   │     │ 近 30 天 + 近 7 天   │     │ 3 tab + JSON 內嵌  │     │ Cloudflare   │
│ 按主題存檔名    │     │ 繁中過濾 (cosplay)   │     │                    │     │ Pages        │
└──────────────────┘     └──────────────────────┘     └────────────────────┘     └──────────────┘
 scrape_multi_topic.py    analyze_by_topic.py         render_index.py           deploy.sh
```

**一鍵執行**：`bash scripts/weekly.sh` / `bash scripts/weekly.sh deploy`

---

## 4. 四主題定義

| 主題 | 資料來源 | 檔名前綴 | 關鍵字 / 帳號 | 特殊過濾 |
|---|---|---|---|---|
| **anime** 動漫 | Playwright + Chrome cookie | `anime_` | `動漫 咒術迴戰 芙莉蓮 我推的孩子 排球少年 鬼滅之刃 MAPPA 動畫瘋` | — |
| **love** 交友 | Playwright + Chrome cookie | `love_` | `交友軟體 曖昧 暈船 脫單 約會 告白 單身 戀愛` | — |
| **cosplay** Cosplay | Playwright + Chrome cookie | `cosplay_` | `cosplay coser cos服 漫展 CWT FF ACOSTA CCF` | **zh-TW 過濾** |
| **cosmate** CosMate | **Threads Graph API** | `cosmate_` | @cosmatedaily 所有貼文 | — |

**資料來源差異**：
- 市場 3 主題用 Playwright 借 Chrome cookie 爬 Threads DOM → **能拿到 repost/share**（Apify 拿不到）
- 失敗時降級到 Apify（只有 likes+comments）— 見 weekly.sh
- cosmate 用官方 API 直接列帳號所有貼文 + insights（含 views/quotes）

**Cookie 需求**（本機跑需要）：
```bash
# 一次性：從本機 Chrome 匯出 cookies（需先在 Chrome 登入 Threads）
python3 /Users/ionachen/Documents/Claude/cosmate-ai-nexus/skills/threads-analytics/scripts/scrape_threads.py \
  --dump-cookies ~/.cosmate/threads_cookies.json
```
之後任何機器（未來雲端/VPS）只要讀得到這個 JSON 就能跑，Cookie 有效期通常幾週。

---

## 5. 一則貼文能否列入 — 六層過濾

```
┌────────────────────────────────────────────────────────────────┐
│ 第 1 層｜爬取                                                   │
│   市場熱榜: Apify 按 keyword 搜 Threads（上限 MAX_POSTS=80）    │
│   CosMate:  官方 Graph API 列該帳號所有貼文（無上限）            │
├────────────────────────────────────────────────────────────────┤
│ 第 2 層｜檔名分流：依主題存成 {topic}_*.json                    │
│   analyze_by_topic.py 信任檔名（不做 keyword 二次過濾）          │
├────────────────────────────────────────────────────────────────┤
│ 第 3 層｜時間過濾：只留 published_on >= now - 30 天             │
│   進階區塊再過濾到近 7 天；無時間戳貼文會被丟掉                  │
├────────────────────────────────────────────────────────────────┤
│ 第 4 層｜語言過濾（僅 cosplay）：CJK >= 30% 且 >= 8 字           │
│   不含簡體獨有字。英/越/他加祿/純簡中 → 濾掉                     │
├────────────────────────────────────────────────────────────────┤
│ 第 5 層｜分類：依百分位算出 Type A-E + X（長尾）                 │
├────────────────────────────────────────────────────────────────┤
│ 第 6 層｜排行：僅 Type A-E（排除 X），依總互動降序，取 Top 10   │
│   - 「符合標準」= Type A-E                                       │
│   - 若該窗格無符合標準貼文，顯示空狀態訊息（不硬塞）             │
└────────────────────────────────────────────────────────────────┘
```

**貼文沒列入，最常見 5 種原因**：

| 症狀 | 卡哪層 | 修法 |
|---|---|---|
| 該寫的帳號沒出現（市場熱榜）| 第 1 層（關鍵字沒命中 OR Threads search 沒回）| 擴充 `TOPICS` 關鍵字 / 改加進 cosmate bucket |
| 某主題只抓到 10 幾篇 | 第 1 層（Apify 上限）| 加 `--max-posts 150` |
| 知名爆款沒出現 | 第 3 層（> 30 天）| `--days 60` |
| 想看的國外 coser 被濾掉 | 第 4 層（非繁中）| 改 `TOPIC_LANG_FILTER` |
| CosMate 某篇互動不錯但沒上榜 | 第 6 層（Type X 長尾）| 確認是否該篇相對同窗貼文 engagement 真的不高；放寬排行榜標準則改 render_index.py 的 `filter(p => p.primary_type !== 'X')` |

---

## 6. 互動分類（Type A–X）

[scripts/analyze.py:110-180](../scripts/analyze.py#L110-L180) 的 `classify_posts()` 用百分位門檻：

| Type | 名稱 | 規則 |
|---|---|---|
| **A** | 全能爆款 🔥 | ❤️≥P90 且 💬≥P90 |
| **B** | 私域擴散型 ✈️ | 🔁+✈️ ≥P75（排除 A）|
| **C** | 戰場議論型 💬 | 💬≥P75 且 留言率>3%（排除 A）|
| **D** | 靜默共鳴型 ❤️ | ❤️≥P75 且 💬<P25（排除 A）|
| **E** | 穩定互動型 📊 | 總互動≥P50 且 ❤️≥P25 且未歸 A-D |
| **X** | 長尾內容 🫧 | 以上皆否 |

**注意**：同一篇可屬於多 Type（primary 是第一個匹配的）。

---

## 7. 指令速查

```bash
# 一鍵全跑（不部署）—— 自動跑三主題市場熱榜 + CosMate 自家表現
bash scripts/weekly.sh

# 一鍵全跑 + 部署
bash scripts/weekly.sh deploy

# 不重抓，只用現有資料重新分析 + 出 HTML
bash scripts/weekly.sh skip-scrape

# 個別步驟
python3 scripts/scrape_multi_topic.py anime love cosplay    # 市場三主題
python3 scripts/scrape_cosmate.py --days 30                 # CosMate 官方 API
python3 scripts/analyze_by_topic.py --all --days 30         # 分析所有主題
python3 scripts/analyze_by_topic.py --topic cosmate --days 7
python3 scripts/render_index.py                             # 出 4-tab HTML
bash scripts/deploy.sh                                       # Cloudflare Pages
```

---

## 8. 環境需求

- **`APIFY_TOKEN`**：市場熱榜三主題用，放在 `threads-dating-app-analysis/.env`（已 gitignore）
- **`THREADS_TOKEN_COSMATE` + `THREADS_USERID_COSMATE`**：CosMate 自家表現用，位於 `/Users/ionachen/Documents/Claude/project/.env.threads`（threads-insights skill 共用）
- `python3` 3.9+（標準函式庫即可，無額外 pip 依賴）
- `wrangler` + Cloudflare 登入（部署用，已在 `.wrangler/`）

---

## 9. 檔案結構

```
threads-dating-app-analysis/
├── scripts/
│   ├── scrape_multi_topic.py    ← 爬市場熱榜（Apify + keyword）
│   ├── scrape_cosmate.py        ← 抓 CosMate 自家貼文（官方 Graph API）
│   ├── analyze_by_topic.py      ← 單主題分析（30d + 7d + zh-tw 過濾）
│   ├── render_index.py          ← 產 4-tab HTML
│   ├── deploy.sh                ← Cloudflare Pages 部署
│   ├── weekly.sh                ← 一鍵跑完整流程
│   └── analyze.py               ← 舊版單一 dating 報告（已棄用但保留）
├── data/
│   ├── raw/                     ← 原始 JSON（anime_*, love_*, cosplay_*, cosmate_*）
│   └── per_topic/               ← 分析後結構化 JSON（HTML 讀這裡）
├── docs/
│   └── WORKFLOW.md              ← 本文件
├── index.html                   ← 四 tab 儀表板（render_index.py 產生）
└── .env                         ← APIFY_TOKEN（已 gitignore）
```

---

## 10. 週一呼叫流程（Agent 視角）

鴿王說 **「threads-weekly」/「monday-threads-report」/「週一熱榜」** 任一句時，Agent 按以下順序執行：

1. 確認 `APIFY_TOKEN` 可用（`.env` 或 env 變數）
2. 執行 `bash scripts/weekly.sh`
3. 查看 stats：回報每主題 30d / 7d 篇數
4. 打開 `index.html` 給鴿王視覺確認
5. 確認版面 OK → 執行 `bash scripts/weekly.sh deploy` 或 `bash scripts/deploy.sh`
6. 回報 Cloudflare 線上連結

**預設行為**：不直接部署，先讓鴿王看過 index.html 再確認。
