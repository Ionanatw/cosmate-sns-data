# Nadia 第 6 帳號 + Trending Signals 加網址原文 + Backfill LOG — 2026-06-03

## 0. 文件資訊

- **建立時間**：2026-06-03 02:49 GMT+8
- **建立者**：德德（Claude Opus 4.7, 1M context）
- **Session 日期**：2026-05-27 起 → 2026-06-03（跨多天連續對話）
- **對話串**：Claude Code（cosmate-sns-data）
- **檔案路徑**：data/session-logs/LOG德德-260603-Nadia第6帳號上線_TrendingSignals加網址原文_Backfill34Row.md

### 關聯資源索引

| 資源 | 位置 | 路徑 / URL |
|------|------|-----------|
| Commit: nadia 上線 | GitHub | [76042cc](https://github.com/Ionanatw/cosmate-sns-data/commit/76042cc) |
| Commit: Trending Signals 加 網址+body | GitHub | [306ee7e](https://github.com/Ionanatw/cosmate-sns-data/commit/306ee7e) |
| Commit: Backfill script | GitHub | [d677097](https://github.com/Ionanatw/cosmate-sns-data/commit/d677097) |
| Ticket: nadia 第 6 帳號 | Notion | https://www.notion.so/36c6fedce91a8189a9e5fff60b31d0b8 |
| Trending Signals DB | Notion | https://www.notion.so/82c8d3badb4c455888590ae5d7f4ac0b |
| scripts/extract_trending_signals.py | repo | scripts/extract_trending_signals.py |
| scripts/backfill_trending_signal_urls.py | repo | scripts/backfill_trending_signal_urls.py（新建） |

---

## 📎 貼進新 Session 的交接文字（複製貼上即用）

> ⚠️ 新 Session 必須先閱讀上一次 LOG 才能延續記憶。

```
我是鴿王，你是德德（Claude Code），請先閱讀上一次 Session LOG 延續記憶：
讀取 data/session-logs/LOG德德-260603-Nadia第6帳號上線_TrendingSignals加網址原文_Backfill34Row.md

閱讀完畢後，以下是重點交接：
1. 上次完成了：(a) 新增 nadiawuuuu 為 metrics-sync 第 6 個 Threads 帳號（含 GHA secrets、Notion Posts DB 選項），(b) Trending Signals 寫入時順手附「網址」欄 + 原文 body，(c) backfill 舊 row 34/40 補完網址。
2. 接下來如果要做：(a) 觀察 60 天後 nadia token 過期前提醒換 token；(b) 6 個無 Source marker 的舊 trending row 可選擇手動補或讓它自然過期。
3. 阻塞：無。系統穩定運作中。
```

---

## 1. TL;DR（三句話）

- **做了什麼**：新增 nadia 為第 6 個 Threads 帳號（從 Meta token 申請 → env → script → GHA secrets → smoke test 全流程）；Trending Signals 寫入時加「網址」欄位 + 原文 body；寫 backfill script 補完 40 row 中 34 row 舊缺的網址。
- **產出什麼**：3 個 commit (`76042cc`, `306ee7e`, `d677097`)、1 個新 script (`backfill_trending_signal_urls.py`)、1 張 Notion Ticket、Trending Signals DB 中 34 row 網址回補。
- **下一步**：無 immediate action。觀察明早 GHA metrics-sync 跑 6 帳號穩定運作；60 天後（~2026-08-01）nadia token 到期前換新。

---

## 2. 決策紀錄

### 決策 1：新增帳號用代號 `nadia`（而非 `nadiawuuuu`）
- **最終方案**：env var 後綴用 `NADIA`，script ALL_ACCOUNTS 用 `nadia`
- **原因**：對齊現有 cosmate / olie / dadana / kiki / amy 短代號風格，env var 全大寫的慣例
- **替代方案**：`NADIAWUUUU`（否決：太長，與既有 4 帳號短代號不一致）

### 決策 2：Trending Signals 「網址」欄回補策略走 A 不走 B
- **最終方案 A**：直接寫 `https://www.threads.com/post/<id>`，不打 Threads server
- **原因**：(1) Threads 會自動 redirect 補 @author，URL 點得到；(2) 不打 Threads 避免 rate-limit (429)；(3) 速度快 ~10s
- **替代方案 B**：HEAD 每個 URL 拿 redirect 後完整 `/@<author>/post/<id>`（否決：rate-limit + 慢 ~80s + redirect 失敗會殘缺）

### 決策 3：舊 6 row 無 Source marker 的 trending signal 不強行回補
- **最終方案**：列出 6 個 row 標題給鴿王看，讓自然 7 天過期掃除
- **原因**：原始 per_topic JSON 已 gitignored 覆蓋，找不回原文與完整 URL；強補假資料會污染 DB
- **替代方案**：手動 google 找 URL 補（否決：性價比低，且這些 row 都接近過期）

---

## 3. 產出清單

| # | 名稱 | 類型 | 路徑 / URL | 狀態 |
|---|------|------|-----------|------|
| 1 | nadia 第 6 帳號完整上線（env / script / GHA / Notion） | Pipeline 變更 | commit `76042cc` | ✅ 已部署 |
| 2 | Trending Signals 寫入加「網址」+ body children | Code 變更 | commit `306ee7e` | ✅ 已部署，待下次 weekly run 驗證 |
| 3 | scripts/backfill_trending_signal_urls.py | 新工具 | commit `d677097` | ✅ 已實際跑過 34 row |
| 4 | Notion Ticket：新增第 6 帳號 nadia | 紀錄 | https://www.notion.so/36c6fedce91a8189a9e5fff60b31d0b8 | ✅ 狀態已完成 |
| 5 | Trending Signals DB 34 row 補完網址 | Notion 資料修復 | 直接寫入 DB | ✅ 完成 |

---

## 4. 除錯與教訓

### 除錯 1：第一次取的 token 對應錯帳號
- **問題**：在 osascript 對話框收到的 token，跑 `/me` 驗證發現是 `cosmate.app`，不是 `nadiawuuuu`
- **根因**：Meta App User Token Generator 那邊點 Generate 時，nadia 還沒接受 Tester 邀請，所以列表只列出 cosmate.app；鴿王 generate 的是現有帳號的 token
- **解法**：先讓 nadia 用她的帳號到 https://www.threads.net/settings 接受邀請，等狀態變「作用中」後，User Token Generator 列表才會出現 nadiawuuuu，再 generate
- **教訓**：每次新增帳號 token，第一步永遠先打 `https://graph.threads.net/v1.0/me?fields=id,username` 驗 token 對應身份，不要直接信任 user 貼的 user_id。差點把 nadia 的數據污染到 cosmate 帳號。
- **🔁 寫進不二錯？**：否（單一情境、操作層注意事項，不到 systemic 程度）

### 除錯 2：osascript hidden answer 顯示明碼
- **問題**：第一個對話框預設沒加 `with hidden answer`，token 變明碼顯示
- **根因**：osascript `display dialog` 預設 plain text input
- **解法**：加 `with hidden answer` 後變 ●●●●● 遮罩
- **教訓**：未來收 token / secret 一律帶 hidden answer
- **🔁 寫進不二錯？**：否（操作層細節）

### 除錯 3：GHA 5/31 metrics-sync 失敗
- **問題**：scheduled run 失敗，exit code 92
- **根因**：Threads (6 帳號含 nadia) step 全綠，後續獨立 IG (cosmate) step exit 92。手動觸發後全綠 → 確認是 transient (IG Graph API 偶發抽搐)
- **解法**：手動 `gh workflow run` 確認 → 全綠 → 不需修
- **教訓**：scheduled GHA 失敗時先別急著改 code，先手動觸發一次重現，transient vs 真壞區分後再決定
- **🔁 寫進不二錯？**：否（觀察性結論，不是錯誤）

### 除錯 4：git push 被 reject（兩次）
- **問題**：commit 完 push 被 reject（remote ahead）
- **根因**：跨多天的對話期間，遠端被其他 commit 推進過（PR merges / 其他 workflow）
- **解法**：`git pull --rebase origin main` 後再 push，乾淨無 merge commit
- **教訓**：長期未交互的 commit 前先 fetch 看 divergence，rebase > merge 保持線性
- **🔁 寫進不二錯？**：否（git 基本操作）

---

## 5. TODO

### 🙋 鴿王要做

| # | 任務 | 時間 | 解鎖什麼 |
|---|------|------|---------|
| 1 | 觀察明早（~2026-06-03 09:30 GMT+8）GHA metrics-sync 跑 6 帳號 | 隔天 | 確認 nadia 持續穩定 |
| 2 | 2026-08-01 附近 nadia token 60 天到期前重做 Meta token generator 流程 | 2 個月後 | 避免 token 失效後 GHA 報錯 |
| 3 | （選做）6 個無 Source marker 舊 trending row 手動補 URL，或讓它自然過期 | 一週內 | DB 整齊度 |

### 🤖 Agent 可自動跑

| # | 任務 | 誰 | 票號 | 前置條件 |
|---|------|---|------|---------|
| — | 無 | — | — | — |

---

## 6. 回寫檢查

| 內容 | 應回寫到 | Notion 已同步？ | 狀態 |
|------|---------|---------------|------|
| nadia 第 6 帳號上線 | Living Status Doc（如有列 metrics-sync 帳號數） | ⏳ | ⏳ 待檢查 |
| Trending Signals 寫入規格變更 | Living Status Doc（如有列 trending pipeline） | ⏳ | ⏳ 待檢查 |
| nadia ticket | Ticket DB | ✅ | ✅ 已完成 |
| Session LOG 本身 | Notion Session LOG DB | ⏳ | ⏳ 本步驟稍後 sync |

---

## 7. HANDOFF 摘要

**狀態**：所有開發任務收工，3 個 commit 已 push 至 main，34 row backfill 已完成。系統穩定。

**下一步**：等待明早 GHA metrics-sync 自動驗證 6 帳號運作；無 immediate 工作。

**阻塞**：無。

---

## 8. 關鍵觀察

1. **新增 Threads 帳號的流程已穩定**：第 6 個帳號 nadia 從 Meta token → env → script → GHA → smoke test 全流程 < 3 小時。流程定型，可寫成 SOP。
2. **Trending Signals 資料品質補完**：新格式（網址 + body）+ 舊 row backfill 後，DB 從「公式 + post_key path」進化到「公式 + 完整 URL + 原文 body」，內容溯源能力大幅提升。後續可考慮 dedupe 邏輯從 `萃取公式 contains post_key` 切到 `網址 equals URL`，更可靠。
3. **GHA failure 處理 SOP 隱然成型**：scheduled run 失敗時，先看是不是 transient（用 workflow_dispatch 手動觸發重現），再決定是 fix code 還是 wait & see。本次節省了不必要的除錯時間。
