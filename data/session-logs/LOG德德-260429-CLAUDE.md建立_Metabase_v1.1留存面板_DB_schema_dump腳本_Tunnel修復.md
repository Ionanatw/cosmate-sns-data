# Metabase v1.1 + DB Schema Dump + Tunnel 修復 LOG — 2026-04-29

## 0. 文件資訊

- **建立時間**：2026-04-29 03:57 GMT+8
- **建立者**：德德（claude-sonnet-4-6）
- **Session 日期**：2026-04-29
- **對話串**：德德（Claude Code）
- **檔案路徑**：data/session-logs/LOG德德-260429-CLAUDE.md建立_Metabase_v1.1留存面板_DB_schema_dump腳本_Tunnel修復.md

### 關聯資源索引

| 資源 | 位置 | 路徑 |
|------|------|------|
| CLAUDE.md（cosmate-sns-data） | repo | cosmate-sns-data/CLAUDE.md |
| metabase_build_v11.py | repo | cosmate-ai-nexus/DB_metabase/metabase_build_v11.py |
| mysql_schema_dump.py | repo | cosmate-ai-nexus/DB_schema_dump/mysql_schema_dump.py |
| com.cosmate.rds-forward-tunnel.plist | Mac LaunchAgents | ~/Library/LaunchAgents/com.cosmate.rds-forward-tunnel.plist |
| TKT-181 Metabase v1 | Notion | https://www.notion.so/3506fedce91a811ba5fbfe078fd9965a |
| TKT-183 Metabase v1.1 | Notion | https://www.notion.so/3506fedce91a81a68a96d28797332c9c |
| Dashboard | Metabase | https://metabase.srv1479079.hstgr.cloud/dashboard/2 |

---

## 📎 貼進新 Session 的交接文字（複製貼上即用）

```
我是鴿王，你是德德，請先閱讀上一次 Session LOG 延續記憶：
讀取 data/session-logs/LOG德德-260429-CLAUDE.md建立_Metabase_v1.1留存面板_DB_schema_dump腳本_Tunnel修復.md

閱讀完畢後，以下是重點交接：
1. 本次完成：TKT-183 Metabase v1.1（11 張留存 Panel）、TKT-182 schema dump 腳本草稿、Tunnel 連線架構修復
2. 接下來：TKT-182 等待不二錯 #049 解除後正式執行；留存指標定義討論待決策
3. 阻塞：TKT-182 blocked by 不二錯 #049（PII 欄位遮蔽）
```

---

## 1. TL;DR（三句話）

- 做了什麼？本 session 從 context 接續，完成 cosmate-sns-data CLAUDE.md 建立、TKT-183 Metabase v1.1 留存面板（11 張）、TKT-182 schema dump 腳本草稿、Tunnel 斷線除錯。
- 產出什麼？Metabase Dashboard/2 新增 Panel A/B/C 共 11 張；`mysql_schema_dump.py` + README 已進 cosmate-ai-nexus；forward tunnel LaunchAgent 修復；兩個 repo 都 push 成功。
- 下一步？TKT-182 等不二錯 #049 解除後正式跑；留存指標定義（D0-D7 vs 累積）待決策；Panel A D30 跨月趨勢圖可排入下次迭代。

---

## 2. 決策紀錄

### 決策 1：DB_metabase 和 DB_schema_dump 存入 cosmate-ai-nexus
- **最終方案**：放在 `cosmate-ai-nexus/DB_metabase/` 與 `cosmate-ai-nexus/DB_schema_dump/`
- **原因**：工具腳本放 nexus，資料/報表留在 sns-data；符合既有分工
- **替代方案**：放在 cosmate-sns-data（否決：該 repo 只管 SNS pipeline）

### 決策 2：Metabase 連線架構需要兩條 LaunchAgent
- **最終方案**：Forward tunnel（Mac:3307→bastion→RDS）+ Reverse tunnel（VPS:3308→Mac:3307）各自一個 LaunchAgent
- **原因**：原本只有 reverse tunnel，forward tunnel 缺漏，導致 VPS 連回 Mac:3307 找不到目標
- **替代方案**：把 VPS IP 加進 bastion Security Group（否決：鴿王說不想動 AWS）

### 決策 3：Panel C 留存曲線用 CROSS JOIN 版 SQL
- **最終方案**：`CROSS JOIN v_members（782 rows） × 30-row 數字表 = 23,460 rows`，直接在 SQL 計算 retention_pct
- **原因**：23,460 rows 應在 timeout 閾值內；SQL 一次完整輸出折線所需資料
- **替代方案**：30 條獨立 COUNT（如 CROSS JOIN timeout 時的 fallback，備而不用）

---

## 3. 產出清單

| # | 名稱 | 類型 | 路徑 | 狀態 |
|---|------|------|------|------|
| 1 | CLAUDE.md | 知識庫 | cosmate-sns-data/CLAUDE.md | ✅ committed |
| 2 | metabase_build_v11.py | 腳本 | cosmate-ai-nexus/DB_metabase/metabase_build_v11.py | ✅ committed |
| 3 | DB_metabase/README.md（更新） | 文件 | cosmate-ai-nexus/DB_metabase/README.md | ✅ committed |
| 4 | mysql_schema_dump.py | 腳本 | cosmate-ai-nexus/DB_schema_dump/mysql_schema_dump.py | ✅ committed |
| 5 | DB_schema_dump/README.md | 文件 | cosmate-ai-nexus/DB_schema_dump/README.md | ✅ committed |
| 6 | com.cosmate.rds-forward-tunnel.plist | LaunchAgent | ~/Library/LaunchAgents/ | ✅ loaded（不進 repo） |
| 7 | Metabase Dashboard/2 v1.1 | 儀表板 | https://metabase.srv1479079.hstgr.cloud/dashboard/2 | ✅ 11 cards added |

---

## 4. 除錯與教訓

### 除錯 1：Metabase 顯示「There was a problem displaying this chart」
- **問題**：v1.1 腳本跑完後，所有新 Panel 都顯示錯誤
- **根因**：Metabase 連線走 VPS:3308 → reverse tunnel → Mac:3307，但 Mac:3307 沒人監聽（forward tunnel 缺漏）。日誌顯示 `connect_to 127.0.0.1 port 3307: failed`
- **解法**：新增 `com.cosmate.rds-forward-tunnel.plist` LaunchAgent，啟動 `autossh -L 3307:RDS:3306 ubuntu@bastion`；Port 3307 LISTEN 後 Dashboard 恢復正常
- **教訓**：Metabase→RDS 的 tunnel 鏈需要「兩條」LaunchAgent，不是一條。README 已更新反映完整架構
- **🔁 寫進不二錯？**：是（分類：連線架構；描述：reverse tunnel 只是半截，必須同時有 forward tunnel Mac:3307→RDS 才通）

### 除錯 2：autossh 路徑錯誤（上一個 session 已修，本次確認）
- **問題**：plist 用 `/usr/local/bin/autossh`，Apple Silicon Mac 應為 `/opt/homebrew/bin/autossh`
- **根因**：路徑沒有隨 Homebrew 位置更新
- **解法**：new LaunchAgent 已使用正確路徑 `/opt/homebrew/bin/autossh`
- **🔁 寫進不二錯？**：已在上一個 session 記錄

---

## 5. TODO

### 🙋 鴿王要做

| # | 任務 | 時間 | 解鎖什麼 |
|---|------|------|---------|
| 1 | 確認 不二錯 #049（PII 欄位遮蔽）完成後，執行 TKT-182 schema dump | Sprint 4 | mysql_schema_dump.py 正式跑 production |
| 2 | 決策：留存指標定義——D0-D7 早鳥留存 vs 累積留存的 Metabase 展示方式 | 下次 session | Panel A/B 數字定義統一 |

### 🤖 Agent 可自動跑

| # | 任務 | 誰 | 票號 | 前置條件 |
|---|------|---|------|---------|
| 1 | mysql_schema_dump.py --dry-run 測試連線 | 德德 | TKT-182 | Forward tunnel 已開（已完成） |
| 2 | Schema dump 正式執行（prod） | 德德 | TKT-182 | 不二錯 #049 解除 |

---

## 6. 回寫檢查

| 內容 | 應回寫到 | Notion 已同步？ | 狀態 |
|------|---------|---------------|------|
| Tunnel 需要兩條 LaunchAgent | 不二錯 DB | ⏳ | 待寫入 |
| TKT-181 狀態 | Ticket DB | ✅ 已是完成 | ✅ |
| TKT-183 狀態 | Ticket DB | ✅ 已更新完成 | ✅ |
| DB_metabase README 更新 | cosmate-ai-nexus | ✅ committed | ✅ |
| Session LOG 本身 | Notion Session LOG DB | ⏳ | 寫入中 |
| 留存指標定義問題 | 決策紀錄 DB or next session | ⏳ | 待決策 |

---

## 7. HANDOFF 摘要

**狀態**：TKT-183 完成，Dashboard/2 共 19 張 Panel（v1 × 8 + v1.1 × 11）。Tunnel 架構修復，Mac 側兩條 LaunchAgent 均 active。

**下一步**：
1. 不二錯 #049 解除 → 執行 TKT-182 schema dump 正式版
2. 留存指標定義決策（D0-D7 窗口留存 vs 累積留存的顯示方式）
3. 可考慮 Panel A D30 按月趨勢折線圖（追蹤改版效果的最直觀指標）

**阻塞**：TKT-182 blocked by 不二錯 #049

---

## 8. 關鍵觀察

**留存指標雙定義問題（待決策）**

本 session 發現 Metabase 的留存數字（49.4% D7）與原始 D7 分析報告（10.7% D7）不一致。根因是定義不同：

- **點快照留存**（10.7%）：在特定時間點（D7 = ~3/12）測量「到目前為止有沒有回來」，資料是 frozen snapshot
- **累積留存**（49.4%）：今天（4/29）測量「53 天內任何時候有沒有活躍」，是 rolling/cumulative

兩個都是有意義的指標，但要追蹤的問題不同：
- 追蹤「onboarding 品質」→ 用 D7 窗口留存（有多少人在第一週內回來）
- 追蹤「長期習慣化」→ 用 Panel A 月份 cohort 的 D30 按月趨勢（改版後的 cohort 累積留存有沒有提升）

真正最有用的 onboarding 追蹤指標可能需要 session log table（每日活躍記錄），不只是 v_members.last_seen_at。這是架構層面的討論，可排入下次數據串。
