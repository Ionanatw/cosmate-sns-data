# Metrics 同步遷移 GHA + Code Review LOG — 2026-04-24

## 0. 文件資訊

- **建立時間**：2026-04-24 17:29 GMT+8
- **建立者**：德德（Claude Sonnet 4.6）
- **Session 日期**：2026-04-24
- **對話串**：threads-dating-app-analysis（Claude Code CLI）
- **檔案路徑**：data/session-logs/LOG德德-260424-Metrics同步遷移GHA_五帳號擴充_CodeReview修復.md

### 關聯資源索引

| 資源 | 位置 | 路徑 |
|------|------|------|
| GHA workflow | repo | `.github/workflows/metrics-sync.yml` |
| Threads 同步腳本 | repo | `scripts/fetch_insights.sh` |
| IG 同步腳本 | repo | `scripts/fetch_ig_insights.sh` |
| Secrets 上傳腳本 | repo | `scripts/upload_secrets.sh` |
| Notion 同步 | repo | `scripts/sync_to_notion.py` |
| IG Notion 同步 | repo | `scripts/sync_ig_to_notion.py` |
| GHA Actions | GitHub | `https://github.com/Ionanatw/threads-dating-app-analysis/actions` |

---

## 📎 貼進新 Session 的交接文字（複製貼上即用）

```
我是鴿王，你是德德，請先閱讀上一次 Session LOG 延續記憶：
讀取 data/session-logs/LOG德德-260424-Metrics同步遷移GHA_五帳號擴充_CodeReview修復.md

閱讀完畢後，以下是重點交接：
1. Threads/IG metrics 每日同步已從 CoWork 搬到 GitHub Actions（metrics-sync.yml），每天 09:30 GMT+8 自動執行，不需電腦開著
2. 5 個 Threads 帳號（cosmate/olie/dadana/kiki/amy）已擴充，IG 同步 cosmate
3. Token 問題未解：workflow 正確 exit 1，但所有帳號均回傳「Cannot parse access token」，COCO 本機跑正常，懷疑 upload_secrets.sh 讀值有誤
4. 下一步：手動用 gh secret set 設定一個 token，確認是 upload 腳本問題還是 GHA 環境問題
```

---

## 1. TL;DR

- 把 CoWork COCO 每日 Threads 同步任務搬到 GitHub Actions，帳號從 3 個擴充到 5 個，同時加入 IG 同步
- 產出：metrics-sync.yml + upload_secrets.sh + 4 個腳本進 repo，修了 8 個 bug，跑完 code review
- 下一步：診斷 token 問題（手動 gh secret set 測試）

---

## 2. 決策紀錄

### 決策 1：用 GitHub Actions 取代 CoWork Desktop Commander
- **最終方案**：GHA cron 排程，每天 09:30 GMT+8 自動執行
- **原因**：不需電腦開著，完全伺服器端，已有 daily.yml 和 weekly.yml 可參考
- **替代方案**：Claude Code schedule skill（雲端 Agent）→ 否決，腳本依賴本機環境不易搬

### 決策 2：複製腳本進 repo（不參照 Skills 目錄）
- **最終方案**：從 `~/.claude/skills/threads-insights/scripts/` 複製 4 個腳本到 `scripts/`
- **原因**：GHA runner 只能存取 repo 內的檔案，無法讀本機 Skills 路徑
- **替代方案**：從 cosmate-ai-nexus clone Skills → 否決，複雜度太高

### 決策 3：upload_secrets.sh 讀值方式
- **最終方案**：`grep -F | cut -d'=' -f2- | tr -d '\r'` + 去頭尾引號 + `printf '%s'` 管道
- **原因**：`bash source` 自動處理引號，但 grep|cut 不會；`echo` 帶換行，`printf '%s'` 不帶
- **問題**：目前仍懷疑讀值有誤，尚未確認根因

---

## 3. 產出清單

| # | 名稱 | 類型 | 路徑 | 狀態 |
|---|------|------|------|------|
| 1 | GHA workflow | 新建 | `.github/workflows/metrics-sync.yml` | ✅ push |
| 2 | Threads 同步腳本 | 新建（複製+修改） | `scripts/fetch_insights.sh` | ✅ push |
| 3 | IG 同步腳本 | 新建（複製+修改） | `scripts/fetch_ig_insights.sh` | ✅ push |
| 4 | Notion 同步 | 新建（複製） | `scripts/sync_to_notion.py` | ✅ push |
| 5 | IG Notion 同步 | 新建（複製） | `scripts/sync_ig_to_notion.py` | ✅ push |
| 6 | Secrets 上傳腳本 | 新建 | `scripts/upload_secrets.sh` | ✅ push |
| 7 | 21 個 GitHub Secrets | 設定 | GitHub Repo Secrets | ✅ 上傳 |

---

## 4. 除錯與教訓

### 除錯 1：腳本 source 本機 .env 路徑，GHA 找不到
- **問題**：`source /Users/ionachen/.../env.threads` 在 GHA runner（Ubuntu）失敗
- **根因**：硬寫本機 Mac 路徑，GHA 上不存在
- **解法**：改為 `[ -f "$_ENV_THREADS" ] && source "$_ENV_THREADS"`，GHA 靠 workflow env: 提供
- **教訓**：腳本設計需考量跨環境執行，env 載入要有 fallback
- **🔁 寫進不二錯？**：是（跨環境腳本設計）

### 除錯 2：`date -v` macOS 專屬語法，Linux 不認識
- **問題**：`date -v-${DAYS}d` 在 ubuntu-latest 噴 `date: invalid option 'v'`，fetch_ig_insights.sh 因 `set -e` 直接 exit 1
- **根因**：macOS BSD date vs Linux GNU date 語法差異
- **解法**：改用 `python3 -c "import time; print(int(time.time()) - ${DAYS} * 86400)"` 跨平台
- **教訓**：macOS 開發、Linux 部署的專案，date/sed/awk 等工具語法要用跨平台版本
- **🔁 寫進不二錯？**：是（macOS vs Linux CLI 工具差異）

### 除錯 3：`echo "$val" | gh secret set` 帶換行符導致 token 格式錯誤
- **問題**：Token 被 Threads API 回傳「Cannot parse access token」
- **根因**（假設）：`echo` 在值後面加 `\n`，`gh secret set --body -` 把換行也存進 Secret
- **解法**：改用 `printf '%s' "$val"` 不加換行
- **狀態**：⚠️ 修了但問題仍在，尚未確認是否此根因

### 除錯 4：`declare -A` bash 3.x 不支援
- **問題**：macOS 內建 bash 3.x 不支援關聯陣列
- **根因**：腳本用了 bash 4.x 語法
- **解法**：改用 `grep -E "^${key}="` 直接讀值，不用關聯陣列
- **教訓**：macOS bash 是 3.x（GPLv2），`declare -A` 要用 zsh 或 brew bash
- **🔁 寫進不二錯？**：是

### 除錯 5：token 失敗時 `return 0`，GHA 仍顯示綠色（Code Review 發現）
- **問題**：所有 token 失效時，workflow 顯示通過但 Notion 完全沒更新
- **根因**：`return 0` on token failure + `|| true` in loop = 靜默失敗
- **解法**：改 `return 1`，加 `_OK` 計數器，全失敗時 `exit 1`
- **教訓**：排程任務的失敗一定要讓 CI 知道，不能 swallow error
- **🔁 寫進不二錯？**：是

---

## 5. TODO

### 🙋 鴿王要做

| # | 任務 | 優先 | 解鎖什麼 |
|---|------|------|---------|
| 1 | 手動 `gh secret set THREADS_TOKEN_COSMATE` 設一個 token | 立即 | 確認 token 問題根因 |
| 2 | 若手動設完能過 → 重跑 `upload_secrets.sh` 確認全部帳號 | 後續 | 解鎖自動同步 |

### 🤖 Agent 可自動跑

| # | 任務 | 誰 | 前置條件 |
|---|------|---|---------|
| 1 | token 確認通後，觸發 `accounts=all` workflow 驗收 | 德德 | 鴿王手動 secret set 完成 |

---

## 6. 回寫檢查

| 內容 | 應回寫到 | Notion 已同步？ | 狀態 |
|------|---------|---------------|------|
| GHA 腳本跨環境設計規則 | 不二錯 DB | ⏳ | ⏳ |
| macOS vs Linux date 差異 | 不二錯 DB | ⏳ | ⏳ |
| bash 3.x declare -A 問題 | 不二錯 DB | ⏳ | ⏳ |
| 排程任務靜默失敗問題 | 不二錯 DB | ⏳ | ⏳ |
| Session LOG 本身 | Notion Session LOG DB | ⏳ | ⏳ |
| Metrics 同步模組狀態 | Living Status Doc | ⏳ | ⏳ |

---

## 7. HANDOFF 摘要

**狀態**：metrics-sync.yml 已部署，workflow 能正確 exit 1 偵測 token 失效，但 token 問題尚未解決

**下一步**：
1. 手動 `gh secret set THREADS_TOKEN_COSMATE`，測試能否繞過 upload_secrets.sh 讓 token 被正確接受
2. 確認根因後視情況修 upload_secrets.sh 或更新 Threads token

**阻塞**：Threads API "Cannot parse access token" — 本機 COCO 正常、GHA 失敗，根因未定論

---

## 8. 關鍵觀察

- fetch_insights.sh 和 fetch_ig_insights.sh 是從 Skills 複製的，未來 Skills 更新時 repo 版本會漂移。應考慮建立同步機制或在 Skills 加上「canonical 在 repo」的說明。
- GHA 的 "workflow passes green" 是很容易讓人誤以為一切正常的陷阱，任何排程型任務都要確保失敗有明確訊號（exit code + notification）。
