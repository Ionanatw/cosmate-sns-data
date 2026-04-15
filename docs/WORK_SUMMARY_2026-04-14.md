# 工作摘要 — Threads 週一熱榜 Pipeline 建立

**日期**：2026-04-14
**執行**：工程鴿頭子（Claude Opus 4.6）
**觸發**：鴿王「週一了，你來調用用來做報告的 SKILLS 或功能」

---

## 🎯 起點 vs 終點

### 起點
- 既有 repo `threads-dating-app-analysis` 只能出「交友 App 單一報告」
- 分析邏輯有 keyword re-filter bug（anime 貼文含「戀愛」會被歸進交友）
- love 主題從沒被獨立爬過
- Cosplay 主題完全沒進 dashboard
- 無時間過濾、無自家帳號追蹤

### 終點
- 四主題獨立報告（**動漫 × 交友 × Cosplay × CosMate**），一份 HTML 四 tab
- 過濾嚴謹（檔名分流 + 30 天/7 天時間窗 + Cosplay 繁中過濾 + Type A-E 標準）
- 自家帳號用官方 Graph API 直取 insights
- 一鍵執行 + 完整文件 + 記憶別名

---

## ✅ 交付清單

| # | 類型 | 產出 | 位置 |
|---|---|---|---|
| 1 | 新爬蟲 | 補抓 love 主題（從無到有）| `scripts/scrape_multi_topic.py` love keyword 既有 |
| 2 | 新爬蟲 | 清理 cosplay 關鍵字（`同人/場次/痛包` → `cosplay coser cos服 漫展 CWT FF ACOSTA CCF`）| [scripts/scrape_multi_topic.py:29](../scripts/scrape_multi_topic.py#L29) |
| 3 | 新腳本 | `scrape_cosmate.py` — 官方 Graph API 抓 @cosmatedaily | [scripts/scrape_cosmate.py](../scripts/scrape_cosmate.py) |
| 4 | 新腳本 | `analyze_by_topic.py` — 單主題分析（不做汙染的 keyword re-filter）| [scripts/analyze_by_topic.py](../scripts/analyze_by_topic.py) |
| 5 | 新功能 | 30 天時間窗過濾（`--days 30`，可調）| `filter_by_days()` in analyze_by_topic.py |
| 6 | 新功能 | 7 天進階區塊（獨立跑 Type 分類）| `top_posts_7d` field |
| 7 | 新功能 | Cosplay zh-TW 繁中過濾（CJK≥30% + 無簡體獨有字）| `is_zh_tw()` in analyze_by_topic.py |
| 8 | 新功能 | 排行榜僅收 Type A-E，空狀態顯示「本週無符合標準貼文」| `qualified30d` / `qualified7d` in render_index.py |
| 9 | 新腳本 | `render_index.py` — 產 4-tab HTML（JSON 內嵌、純 CSS+JS tab 切換）| [scripts/render_index.py](../scripts/render_index.py) |
| 10 | 新腳本 | `weekly.sh` — 一鍵跑完整流程 | [scripts/weekly.sh](../scripts/weekly.sh) |
| 11 | 新文件 | `WORKFLOW.md` — 規格 + 流程 + 過濾邏輯 + 指令速查 | [docs/WORKFLOW.md](WORKFLOW.md) |
| 12 | 新文件 | 本工作摘要 | [docs/WORK_SUMMARY_2026-04-14.md](WORK_SUMMARY_2026-04-14.md) |
| 13 | Agent 記憶 | 三個別名寫入 project memory | `~/.claude/projects/.../memory/project_threads_weekly.md` |

---

## 🔧 診斷紀錄（給下次除錯用）

### Bug 1：`analyze.py` 主題汙染
**症狀**：交友報告裡混入大量動漫 / cosplay / mood 貼文
**根因**：[scripts/analyze.py:92-94](../scripts/analyze.py#L92-L94) 用 `DATING_KEYWORDS` 把 `data/raw/` 所有 JSON 全文重掃
**修法**：新建 `analyze_by_topic.py`，信任檔名前綴判主題，**完全不做 keyword re-filter**
**舊 analyze.py 決策**：保留不動（鴿王指示），但不再進主流程

### Bug 2：時間窗跨兩年
**症狀**：報告顯示 `2024-01 ~ 2026-04`
**根因**：Apify 回的是 all-time top，`analyze_by_topic.py` 沒套 `filter_by_date`
**修法**：新增 `--days` 參數（預設 30），`filter_by_days()` 過濾

### Bug 3：Cosplay 混入外語貼文
**症狀**：Top 10 出現英文、越南文、他加祿文
**根因**：Apify 搜 `cosplay` 關鍵字會命中國際 coser
**修法**：新增 `TOPIC_LANG_FILTER = {"cosplay": "zh-tw"}`，用 CJK 比例 + 簡體獨有字判繁中

### Bug 4：@cosmatedaily 貼文沒被抓到
**症狀**：鴿王指定那篇「咒術cosplay 大賽」完全不在任何 raw 檔
**根因**：**不是 MAX_POSTS 問題**。Threads search API 按 `engagement × recency × author_reach` 排序，小粉絲帳號被大帳號擠出 top results
**修法**：新增 `scrape_cosmate.py` 用官方 Graph API 直接列帳號所有貼文，繞開 search 機制

---

## 📊 本次資料實績

| 主題 | 來源 | 原始 | 近 30 天 | 近 7 天 | Top 1 互動 |
|---|---|---|---|---|---|
| anime | Apify search | 86 | 45 | 16 | 65,207（@xinxiongceng）|
| love | Apify search | 90 | 37 | 25 | 34,684（@demkuo.gdl）|
| cosplay | Apify search + zh-TW | 70→32 | 14 | 10 | 16,550（@blackdog9876543210）|
| cosmate | Graph API | 28 | 26 | 8 | 9,193（@cosmatedaily）|

---

## 🔁 下週一呼叫方式（任一句都可）

```
threads-weekly
monday-threads-report
週一熱榜
```

Agent 看到 → 自動跑 `bash scripts/weekly.sh` → 打開 index.html → 鴿王確認後才 deploy。

---

## 🚧 已知限制 / 未來可動

1. **Apify MAX_POSTS 上限**：Threads search API 回的結果 finite，加大 MAX_POSTS 效益遞減
2. **cosplay 繁中過濾誤殺**：香港粵語貼文可能因簡/繁混用被誤濾（目前 heuristic 沒有完美解法，鴿王要手動調 `SIMPLIFIED_ONLY` 清單）
3. **CosMate 單帳號**：目前只接 `cosmatedaily`，`olie` / `dadana` 未納入（threads-insights skill 有支援，可延伸）
4. **沒 sync 到 Notion**：threads-insights skill 有 `--sync-notion`，本 pipeline 沒串接（後續若要歸檔可加）
5. **沒 diff/趨勢**：每週報告是 snapshot，沒做「vs 上週」的 delta 分析

---

## 📎 相關文件 / Skill

- [docs/WORKFLOW.md](WORKFLOW.md) — 完整規格
- [~/.claude/skills/threads-insights/](file:///Users/ionachen/.claude/skills/threads-insights/) — 官方 API insights（CosMate 資料來源參考）
- [scripts/analyze.py](../scripts/analyze.py) — 舊版 dating 單一報告（已不進主流程，但保留）

---

## 🧭 Agent 下次接手時

讀這份摘要 + `docs/WORKFLOW.md` 就能無痛接上。三個別名任一句觸發 → 跑 `bash scripts/weekly.sh` → 按 WORKFLOW.md §10 的順序走完。若鴿王問「某篇為什麼沒列入」，按 WORKFLOW.md §5 的六層過濾逐層診斷，不要直接建議加大 MAX_POSTS。
