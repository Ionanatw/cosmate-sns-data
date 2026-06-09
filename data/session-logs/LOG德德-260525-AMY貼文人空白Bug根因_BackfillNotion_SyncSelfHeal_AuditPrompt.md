# AMY 貼文人空白 Bug 根因 + Backfill + Sync Self-Heal LOG — 2026-05-25

## 0. 文件資訊

- **建立時間**：2026-05-26 12:11 GMT+8
- **建立者**：德德（Claude Opus 4.7）
- **Session 日期**：2026-05-25
- **對話串**：Claude Code（德德）
- **檔案路徑**：data/session-logs/LOG德德-260525-AMY貼文人空白Bug根因_BackfillNotion_SyncSelfHeal_AuditPrompt.md

### 關聯資源索引

| 資源 | 位置 | 路徑 / URL |
|------|------|----------|
| sync_to_notion.py | repo | cosmate-sns-data/scripts/sync_to_notion.py |
| 修復 commit | GitHub | `f7d55a6` on cosmate-sns-data@main |
| Notion Posts DB | Notion | 2106fedce91a81389a54c223533d481b |
| Session LOG DB | Notion | data_source_id `53dd498e-624b-493e-942b-d0107bde7221` |
| 前篇相關 LOG | repo | data/session-logs/LOG德德-260514-Olie貼文人空格Bug根因_*.md |

---

## 📎 貼進新 Session 的交接文字（複製貼上即用）

> ⚠️ 新 Session 必須先閱讀上一次 LOG 才能延續記憶。

```
我是鴿王，你是德德（Claude Code），請先閱讀上一次 Session LOG 延續記憶：
讀取 data/session-logs/LOG德德-260525-AMY貼文人空白Bug根因_BackfillNotion_SyncSelfHeal_AuditPrompt.md

閱讀完畢後，以下是重點交接：
1. 上 session 修了 sync_to_notion.py 漏掉 amy → 社畜Amy 對應的 bug，commit f7d55a6 已 push 到 main。Backfill 了 13 筆 Notion Posts DB 既有 AMY 貼文「貼文人=社畜Amy」。Update path 也加了 self-heal 邏輯（空白才補），未來其他帳號漏標也會自動修。
2. 接下來：鴿王已準備好 audit prompt（在 §3 產出清單）交給另一個 agent 跑全帳號 sweep；若該 agent 回報任何 ⚠️ 再決定是否手動處理。
3. 阻塞：無。但本機 .env.threads 的 AMY token 是 placeholder（7 字元），若要本機跑 sync 測 AMY 需先補正確 token；GHA secrets 那邊 AMY token 是正常的。
```

---

## 1. TL;DR（三句話）

- **做了什麼**：診斷鴿王回報「Notion Posts DB 沒更新到最新日 + AMY 沒被更新」，找出根因是 `sync_to_notion.py` 的 `ACCOUNT_TO_POSTER` 對應表漏 amy；澄清「最新日 views=None」是 content-gen AI 初稿（無 Threads Post ID）造成的視覺誤會。
- **產出什麼**：commit `f7d55a6`（sync_to_notion.py 加 amy mapping + update path self-heal 邏輯）、backfill 13 筆 Notion Posts DB 既有 AMY 貼文「貼文人」欄位、給另一個 agent 跑 5 帳號 audit 的 hand-off prompt。
- **下一步**：鴿王把 audit prompt 丟給另一個 agent 跑全帳號 sweep；若回報任何空白/錯標再 case-by-case 處理。

---

## 2. 決策紀錄

### 決策 1：self-heal 邏輯放哪裡

- **最終方案**：在 update path（既有列 PATCH）加判斷 — 若 Notion 上「貼文人」是空、且程式碼有對應 poster name，就一併補上
- **原因**：未來其他帳號若再發生 mapping 漏掉、後來補上，下次 sync 會自動修，不需要再手寫 backfill；既有 metrics-only 更新路徑無破壞性影響
- **替代方案**：只做一次性 backfill 不動程式碼（否決原因：bug 復現時還是要手動 backfill，違反「能 self-healing 就 self-healing」原則）

### 決策 2：Backfill 範圍

- **最終方案**：全部 13 筆 AMY sync 貼文（4/17～5/22）一次補完
- **原因**：鴿王已明確選擇「全部 backfill」；風險低（只動有 Threads Post ID 且「貼文人」為空的列）；補完後 filter 看得到完整歷史
- **替代方案**：只 backfill 過去 30 天（否決原因：對舊資料完整性無益，鴿王明確選了全部）

### 決策 3：只 commit 本次 fix 檔案

- **最終方案**：只 stage + commit `scripts/sync_to_notion.py`，把其他 4 個 working tree 上的 modified 檔案（weekly.yml / CLAUDE.md / scrape_playwright_topics.py / weekly.sh）跟未追蹤的 `scripts/extract_trending_signals.py` 和 `scripts/lib/` 留著不動
- **原因**：這些檔案的改動跟本次 AMY bug 無關，併 commit 會弄混 atomic commit 邊界
- **替代方案**：`git add -A` 一鍵全推（否決原因：違反 atomic commit 原則 + 可能誤推未驗的中途工作）

---

## 3. 產出清單

| # | 名稱 | 類型 | 連結 / 路徑 | 狀態 |
|---|------|------|-----------|------|
| 1 | sync_to_notion.py 修改（加 amy mapping + self-heal） | 程式碼 | scripts/sync_to_notion.py L96-L102, L252-L260 | ✅ commit + push |
| 2 | Commit `f7d55a6` | git | https://github.com/Ionanatw/cosmate-sns-data/commit/f7d55a6 | ✅ on main |
| 3 | Backfill 13 筆 AMY「貼文人=社畜Amy」 | Notion | Posts DB 2106fedce91a81389a54c223533d481b | ✅ 全部成功 |
| 4 | Audit prompt for 5-account sweep | 對話 | 見 §8 關鍵觀察 | ✅ 已交付鴿王 |

---

## 4. 除錯與教訓

### 除錯 1：AMY 貼文「貼文人」全空白

- **問題**：鴿王回報「AMY 好像沒有被更新」，按「貼文人=社畜Amy」filter 查 Posts DB 0 筆結果
- **根因**：`scripts/sync_to_notion.py:96-101` 的 `ACCOUNT_TO_POSTER` 只列了 cosmate / olie / dadana / kiki，**漏掉 amy**。`build_posts_db_new_entry_props()` 裡 `poster = ACCOUNT_TO_POSTER.get(account)` 對 amy 回 None，所以 if 條件不寫入「貼文人」欄位；既存頁面的 update path 本來也只更新 metrics，永遠不會回補
- **解法**：
  1. 加 `"amy": "社畜Amy"` 進對應表
  2. Update path 加 self-heal：讀既有頁面的「貼文人」，若空 + 程式碼有 mapping 就補上
  3. Backfill 13 筆既有空白列
- **教訓**：擴充帳號清單時，**「帳號清單」跟「人設對應表」是兩個地方**（`fetch_insights.sh:35` 的 `ALL_ACCOUNTS` array 跟 `sync_to_notion.py:96` 的 `ACCOUNT_TO_POSTER` dict）— 加新帳號得兩邊都動。本次 amy 是只動了 `ALL_ACCOUNTS` 沒動 dict，造成 7+ 個月的潛伏 bug
- **🔁 寫進不二錯？**：是（分類：CONTEXT_MISS — 加新帳號時沒同步更新所有相關對應表）

### 除錯 2：「最新日 views=None」是視覺誤會

- **問題**：鴿王感受到「Posts DB 沒更新到最新日」
- **根因**：用戶按「Post date」倒序排，最新一筆是 content-gen skill 寫的 AI 初稿（`來源=🤖 AI初稿`、沒有 Threads Post ID、views/likes 自然是 None）— 它的 Post date 是「預定發文日」不是已發文，所以 metrics 本來就空。同日 sync 進來的真實貼文 metrics 是正常的，只是在排序時被 AI 初稿那筆擋住
- **解法**：澄清 + 不需修程式
- **教訓**：Posts DB 同一日期可能存在「AI 初稿（未發文，無 metrics）」跟「sync 進來的真實貼文（已發文，有 metrics）」混排；之後若要做「最新已發文」面板，filter 應該加上「Threads Post ID 非空」或「來源 = ✍️ 人工」
- **🔁 寫進不二錯？**：否（已是設計上的混排，僅需 UI/filter 層注意）

### 除錯 3：本機 AMY token 是 placeholder

- **問題**：本機 `.env.threads` 的 `THREADS_TOKEN_AMY` / `THREADS_USERID_AMY` 都只有 7 字元，curl Threads Graph API 回 `Invalid OAuth access token`
- **根因**：本機 env 沒填正式值，可能是 placeholder「PENDING」字串
- **解法**：本次不需本機跑 AMY sync，跳過；若未來要在本機 debug AMY 需先補正確 token
- **教訓**：GHA Secrets 跟本機 .env 的同步狀態要分開驗證；本機 env 缺值不代表 production sync 壞
- **🔁 寫進不二錯？**：否（環境本身的維護問題，不算 code bug）

---

## 5. TODO

### 🙋 鴿王要做

| # | 任務 | 時間 | 解鎖什麼 |
|---|------|------|---------|
| 1 | 把 §8 的 audit prompt 丟給另一個 agent 跑 5 帳號 sweep | 5 分鐘觸發、agent 跑可能 5-10 分鐘 | 確認其他 4 帳號沒類似潛伏 bug |
| 2 | 若 audit 回報任何 ⚠️，鴿王 review + 決定是否手動 patch | 看回報筆數 | 收尾 |
| 3（選）| 把本機 .env.threads 的 AMY token 補成正確值（從 GHA secrets / 1Password 拉） | 5 分鐘 | 未來本機 debug AMY 可用 |

### 🤖 Agent 可自動跑

| # | 任務 | 誰 | 票號 | 前置條件 |
|---|------|---|------|---------|
| - | 無 | - | - | - |

---

## 6. 回寫檢查

| 內容 | 應回寫到 | 狀態 |
|------|---------|------|
| 加新帳號要同時更新 `ALL_ACCOUNTS` + `ACCOUNT_TO_POSTER` 兩處 | 不二錯 DB（CONTEXT_MISS 分類） | ⏳ 待寫 |
| sync_to_notion.py self-heal 邏輯（既有空白可自動補） | CLAUDE.md（如有 metrics-sync 章節） | N/A（CLAUDE.md 沒這層細節） |
| 本次提到的 Ticket | Ticket DB | N/A（本次無 Ticket 關聯） |
| Living Status Doc 模組狀態 | https://www.notion.so/32d6fedce91a812bb696faad797ad071 | N/A（sync 流程未變更，只是補漏） |
| Skill 同步鏈路 | - | N/A（本次無 SKILL.md 改動） |
| **本次 LOG** | **Session LOG DB** | **⏳ 寫入中** |

---

## 7. HANDOFF 摘要

**狀態**：AMY 貼文人 bug 已修復、commit `f7d55a6` 已 push、Notion 上 13 筆已 backfill；其他 4 帳號是否有類似潛伏問題尚未 sweep（已備好 audit prompt 待鴿王觸發）

**下一步**：鴿王把 audit prompt 丟給另一個 agent 跑全帳號 sweep；若回報 ⚠️ 再 case-by-case 處理

**阻塞**：無

---

## 8. 關鍵觀察

### 與 5/14 olie 空格 bug 是同一類問題的不同變體

- **5/14**：Notion DB 「貼文人」multi_select 有兩個外觀類似 option（`動漫宅Olie.Huang` vs `動漫宅 Olie.Huang` 有空格）造成 SCAN 失敗
- **5/25**：sync_to_notion.py 的對應表漏掉 amy 整列，造成「貼文人」永遠空白
- **共通**：「人設 / 帳號名稱對應表」散佈多處（Notion select options、Python dict、bash array），任何一處漏一個都會造成下游靜默失敗
- **建議**：未來考慮把帳號→人設對應表抽到一個 single source of truth（例如 Notion DB 或 YAML），程式啟動時讀；目前先靠 review checklist 把關

### 給另一個 agent 的 audit prompt（本次 session 產出）

完整 prompt 已交付鴿王，掃 4 件事：
1. 每帳號「Link contains pattern + Threads Post ID 非空 + 貼文人空白」筆數（預期 0）
2. 每帳號「Link pattern 跟貼文人對不上」筆數（預期 0；特別留意 kiki 的「交友中Kiki」vs「交友中的Kiki」）
3. 每帳號 sync 最新一筆 Post date vs Threads API 上實際最新貼文日
4. 每帳號「來源=✍️ 人工 + 有 Threads Post ID 但瀏覽數=None」筆數（預期 0）

明確要求「不要 mass-modify，只報告」— 避免另一個 agent 又跑去 backfill 而沒先讓鴿王看到結果。
