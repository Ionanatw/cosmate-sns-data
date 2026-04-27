# IG同步修復 + Repo 改名整理 LOG — 2026-04-27

## 0. 文件資訊

- **建立時間**：2026-04-27 16:01 GMT+8
- **建立者**：德德（Claude Sonnet 4.6）
- **Session 日期**：2026-04-27
- **對話串**：threads-dating-app-analysis → cosmate-sns-data（Claude Code CLI）
- **檔案路徑**：data/session-logs/LOG德德-260427-IG同步VIDEO修復_Repo改名cosmate-sns-data_本機目錄整理.md

### 關聯資源索引

| 資源 | 位置 | 路徑 |
|------|------|------|
| GHA workflow | repo | `.github/workflows/metrics-sync.yml` |
| IG Notion 同步腳本 | repo | `scripts/sync_ig_to_notion.py` |
| GHA Actions | GitHub | https://github.com/Ionanatw/cosmate-sns-data/actions |

---

## 📎 貼進新 Session 的交接文字（複製貼上即用）

```
我是鴿王，你是德德，請先閱讀上一次 Session LOG 延續記憶：
讀取 data/session-logs/LOG德德-260427-IG同步VIDEO修復_Repo改名cosmate-sns-data_本機目錄整理.md

閱讀完畢後，以下是重點交接：
1. IG metrics 同步已全部正常：inserted/updated/skipped=0 對五帳號 Threads + cosmate IG 均通過
2. Repo 已從 threads-dating-app-analysis 改名為 cosmate-sns-data（GitHub + 本機路徑均已更新）
3. 本機路徑：/Users/ionachen/Documents/Claude/cosmate-sns-data
4. 無待解阻塞，系統目前全部 green
```

---

## 1. TL;DR

- 修了 Notion 欄位名稱尾端空格問題，IG VIDEO/REEL 同步從 skipped=8 → updated=16
- 把 repo 從 `threads-dating-app-analysis` 改名為 `cosmate-sns-data`，本機路徑同步更新
- 清理 root 層垃圾檔案（媒體資料夾、舊 HTML、遺留文件）

---

## 2. 決策紀錄

### 決策 1：Repo 改名而非拆分
- **最終方案**：改名 `cosmate-sns-data`，涵蓋「抓數據 + 分析報告」兩種用途
- **原因**：GHA secrets 和 workflow 都在這裡，拆 repo 代價高；分析報告和數據同步共用同一份數據源，放一起合理
- **替代方案**：拆成 `cosmate-reports` + `cosmate-metrics-sync`（否決：搬移成本高，要重設一份 secrets + workflows）

### 決策 2：index.html / server.py 不刪、加 .gitignore
- **最終方案**：加進 `.gitignore`，本機保留
- **原因**：是 `weekly.sh` 的產出物，每次執行自動重生，不需要 git track

---

## 3. 產出清單

| # | 名稱 | 類型 | 路徑 | 狀態 |
|---|------|------|------|------|
| 1 | IG sync 空格修復 | bug fix | `scripts/sync_ig_to_notion.py` | ✅ push |
| 2 | GitHub repo 改名 | 設定 | GitHub Ionanatw/cosmate-sns-data | ✅ |
| 3 | 本機資料夾改名 | 本機 | `/Users/ionachen/Documents/Claude/cosmate-sns-data` | ✅ |
| 4 | 媒體資料夾刪除 | 清理 | `cosmatedaily_DW_JoDWkloS/`、`oliehuangmix_DXRQdqiE4QL/` | ✅ |
| 5 | 舊 HTML 刪除 | 清理 | `ig_carousel_preview.html`、`threads-bot-ikea-guide.html` | ✅ |
| 6 | 文件歸位 | 整理 | `docs/TELEGRAM_BOT_HANDOFF.md`、`docs/analysis_report.md` | ✅ push |
| 7 | .gitignore 更新 | 設定 | `.gitignore` | ✅ push |

---

## 4. 除錯與教訓

### 除錯 1：`總觀看時間(分) ` 尾端空格導致 Notion PATCH 400
- **問題**：IG VIDEO/REEL 同步 skipped=8，`updated=8, skipped=8`
- **根因**：Notion Posts DB 的欄位名稱是 `總觀看時間(分) `（尾端有空格），但 `sync_ig_to_notion.py` 程式碼寫的是 `總觀看時間(分)`（無空格）。Notion PATCH 找不到欄位 → HTTP 400。POST（新建）不報錯是因為 Notion 新建時忽略未知欄位，但 PATCH（更新）嚴格比對。
- **解法**：`POSTS_DB_METRICS_MAP` 對應鍵改為 `"總觀看時間(分) "`（補上空格）
- **教訓**：Notion 欄位名稱要直接從 DB schema API 抓，不要憑肉眼判斷有沒有尾端空白
- **🔁 寫進不二錯？**：是（Notion 欄位名稱空格陷阱）

---

## 5. TODO

### 🙋 鴿王要做

（無）

### 🤖 Agent 可自動跑

（無）

---

## 6. 回寫檢查

| 內容 | 應回寫到 | Notion 已同步？ | 狀態 |
|------|---------|---------------|------|
| Notion 欄位名稱空格陷阱 | 不二錯 DB | ⏳ | ⏳ |
| Repo 改名決策 | Living Status Doc | ⏳ | ⏳ |
| Session LOG 本身 | Notion Session LOG DB | ⏳ | ⏳ |

---

## 7. HANDOFF 摘要

**狀態**：metrics-sync pipeline 全部正常。Threads 五帳號 + IG cosmate 每天 09:30 GMT+8 自動同步，無阻塞。

**下一步**：無待辦，系統 green。

**阻塞**：無。

---

## 8. 關鍵觀察

Notion PATCH vs POST 對未知欄位的行為差異是個容易踩的坑：POST 靜默忽略未知 property，PATCH 直接 400。未來凡是寫 Notion 欄位名稱一律從 API schema 驗證，不憑 UI 目測。
