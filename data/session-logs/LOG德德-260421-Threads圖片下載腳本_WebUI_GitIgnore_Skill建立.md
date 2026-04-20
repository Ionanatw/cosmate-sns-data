# Threads 圖片下載工具開發 LOG — 2026-04-21

## 0. 文件資訊

- **建立時間**：2026-04-21 01:57 GMT+8
- **建立者**：德德（claude-sonnet-4-6）
- **Session 日期**：2026-04-17～2026-04-21
- **對話串**：threads-dating-app-analysis（德德串）
- **檔案路徑**：data/session-logs/LOG德德-260421-Threads圖片下載腳本_WebUI_GitIgnore_Skill建立.md

### 關聯資源索引

| 資源 | 位置 | 路徑 |
|------|------|------|
| 圖片下載腳本 | repo | scripts/download_threads_images.py |
| Web UI 伺服器 | repo | server.py |
| Skill 定義 | 本機 | ~/.claude/skills/threads-dl/SKILL.md |
| INDEX 快查表 | 本機 | ~/.claude/skills/INDEX.md |

---

## 📎 貼進新 Session 的交接文字（複製貼上即用）

我是鴿王，你是德德，請先閱讀上一次 Session LOG 延續記憶：
讀取 data/session-logs/LOG德德-260421-Threads圖片下載腳本_WebUI_GitIgnore_Skill建立.md

閱讀完畢後，以下是重點交接：
1. Threads 圖片下載腳本已完成，支援 threads.net 和 threads.com，登入 session 持久化在 ~/.threads-scraper/browser-profile/
2. threads-dl skill 已建立在 ~/.claude/skills/threads-dl/，但不會出現在 / 斜線選單（plugin 系統限制），直接說「下載這個 Threads 圖片」即可觸發
3. server.py（Web UI）已建立但鴿王決定放棄給多人使用的方向；CDN 過濾已補上 fbcdn，--headless 模式建議避免（圖片抓不到）

---

## 1. TL;DR（三句話）
- 從 PP 分享的腳本出發，重寫並修掉 5 個核心 bug，產出生產可用的 Threads 圖片下載器
- 額外產出 Web UI（server.py）、gitignore 修正、threads-dl skill
- 下一步：腳本本身功能穩定，skill 日後可考慮加進 cosmate-ai-nexus repo 做版控

---

## 2. 決策紀錄

### 決策 1：放棄 Web UI 多人使用方向
- **最終方案**：保留 server.py 但不推廣給同事
- **原因**：需要本機跑 Playwright，同事難以複製環境
- **替代方案**：CLI 腳本（採用）

### 決策 2：按鈕 click 改為只點 "展開更多回覆" 連結
- **最終方案**：只點 `role="link"` + 包含數字的文字（如「View 5 more replies」）
- **原因**：原版 :has-text("回覆") 命中所有 action button，造成開 modal、頁面跳轉、阻斷 scrollBy
- **替代方案**：移除全部 click（過於保守，失去展開嵌套回覆的能力）

### 決策 3：CDN 過濾加上 fbcdn
- **最終方案**：`scontent or cdninstagram or fbcdn`
- **原因**：Threads 部分圖片走 Meta 的 fbcdn.net CDN，原本過濾漏抓

---

## 3. 產出清單

| # | 名稱 | 類型 | 路徑 | 狀態 |
|---|------|------|------|------|
| 1 | Threads 圖片下載器 | Python 腳本 | scripts/download_threads_images.py | ✅ 完成 |
| 2 | Web UI 伺服器 | Python Flask | server.py | ✅ 完成（已放棄推廣） |
| 3 | gitignore 更新 | 設定檔 | .gitignore | ✅ 完成 |
| 4 | threads-dl Skill | Skill | ~/.claude/skills/threads-dl/SKILL.md | ✅ 完成 |
| 5 | INDEX.md 更新 | 快查表 | ~/.claude/skills/INDEX.md | ✅ 完成 |

---

## 4. 除錯與教訓

### 除錯 1：按鈕 click 阻斷頁面滾動
- **問題**：滾動迴圈每輪點擊大量 role="button" 元素，導致頁面無法 scroll
- **根因**：:has-text("回覆")、:has-text("View") 等 selector 命中範圍太廣，點到 action button
- **解法**：改為只點 role="link" + 文字含數字的展開連結
- **教訓**：Playwright click 操作必須鎖定非常精確的 selector，廣泛文字匹配在 SPA 上風險極高
- **🔁 寫進不二錯？**：是（分類：Playwright / DOM 操作）

### 除錯 2：headless 模式找不到圖片
- **問題**：--headless 跑出 0 張圖片
- **根因**：未登入 + headless 下 Threads 不渲染完整圖片
- **解法**：不加 --headless，或先用 --login 建立 session
- **教訓**：Threads 對 headless 有限制，首次必須有視窗登入
- **🔁 寫進不二錯？**：否（已記在 SKILL.md 常見問題）

### 除錯 3：threads.com vs threads.net domain 不符
- **問題**：regex 只認 threads.net，用戶貼 threads.com URL 解析失敗
- **根因**：Threads 已從 threads.net 遷移到 threads.com 但腳本未更新
- **解法**：改為 `threads\.(?:net|com)`
- **教訓**：Threads URL domain 要同時支援兩個
- **🔁 寫進不二錯？**：否（已修復在程式碼中）

---

## 5. TODO

### 🙋 鴿王要做

| # | 任務 | 解鎖什麼 |
|---|------|---------|
| 1 | 首次執行加 --login 建立 session | 之後免登入直接用 |
| 2 | 確認 headless 模式是否可正常運作（需 session 後再試） | 可背景靜默下載 |

### 🤖 Agent 可自動跑

| # | 任務 | 誰 | 前置條件 |
|---|------|---|---------|
| 1 | 將 threads-dl skill 同步到 cosmate-ai-nexus repo | 德德 | 鴿王確認要版控 |

---

## 6. 回寫檢查

| 內容 | 應回寫到 | Notion 已同步？ | 狀態 |
|------|---------|---------------|------|
| Playwright click selector 要精確 | 不二錯 DB | ⏳ | ⏳ |
| threads-dl 工具誕生 | Living Status Doc | ⏳ | ⏳ |
| Session LOG 本身 | Notion Session LOG DB | ⏳ | ⏳ |

---

## 7. HANDOFF 摘要

**狀態**：圖片下載腳本功能完整，skill 已建立，可正常使用  
**下一步**：無緊急待辦，按需使用 `/threads-dl <URL>` 觸發  
**阻塞**：無

---

## 8. 關鍵觀察

- Threads 的 CDN 現在同時走 `scontent`、`cdninstagram`、`fbcdn` 三個來源，未來如果又出現 0 張的情況，優先懷疑 CDN filter 又漏了新的 domain
- Playwright 在 Threads 上做 click 操作要非常保守，SPA 的 role="button" 幾乎都是功能性的，一個 click 就可能開 modal 或跳頁
- threads-dl skill 在 system-reminder 可見（自然語言觸發），但不在 / 斜線選單（plugin 系統限制），這是平台限制，非 bug
