# content-meme 套版產文流程設計與 P1 實作 LOG — 2026-06-30

## 0. 文件資訊

- **建立時間**：2026-06-30 11:43 GMT+8
- **建立者**：德德（Claude Code，Opus 4.8）
- **Session 日期**：2026-06-29 ~ 06-30
- **對話串**：德德（Claude Code，cosmate-sns-data）
- **檔案路徑**：data/session-logs/LOG德德-260630-contentmeme套版流程設計_P1實作PR57_QC語義一致_D13分流.md

### 關聯資源索引

| 資源 | 位置 | 路徑 / URL |
|------|------|-----------|
| spec 設計文件 | repo | docs/superpowers/specs/2026-06-29-content-meme-套版產文流程-design.md |
| P1 實作計畫 | repo | docs/superpowers/plans/2026-06-29-P1-content-meme.md |
| content-meme skill（新） | cosmate-ai-nexus | skills/content-meme/（PR #57） |
| PR #57 | GitHub | https://github.com/Ionanatw/cosmate-ai-nexus/pull/57 |
| 不二錯 #082 | Notion | https://app.notion.com/p/38f6fedce91a817a87c6d16e1f49cff0 |

---

## 📎 貼進新 Session 的交接文字（複製貼上即用）

```
我是鴿王，你是德德（Claude Code），請先閱讀上一次 Session LOG 延續記憶：
讀取 data/session-logs/LOG德德-260630-contentmeme套版流程設計_P1實作PR57_QC語義一致_D13分流.md

閱讀完畢後，以下是重點交接：
1. 完成 Threads 產文流程重新規劃：新建 content-meme「套版引擎」skill（P1），PR #57 已開（cosmate-ai-nexus，9 commits，21 測試綠），含 3 支 stdlib 工具 + SKILL.md。
2. 接下來：先等鴿王最終判定 Task 5 套版品質 → 收尾 P1 → 寫 P2（grab-idea 強化）/ P3（A 型自動升級橋）/ P4（Telegram 並排卡）計畫與實作。
3. 阻塞/待決：Task 5 品質主觀認可待鴿王拍板；spec/plan 已 commit 到 docs/content-meme-redesign 分支（未合 main、未開 PR）。
```

---

## 1. TL;DR（三句話）
- **做了什麼**：把 CosMate Threads 產文流程從「自由創作」重新規劃為「套版」，完成設計 spec + P1 計畫，並用 subagent-driven-development 實作出 content-meme skill。
- **產出什麼**：content-meme skill（3 支 TDD 工具 + SKILL.md，21 測試）PR #57；spec + P1 plan 文件；不二錯 #082；兩輪樣本驗證逼出 QC-語義一致 與 D13 兩個設計洞。
- **下一步**：等鴿王判定 Task 5 品質 → P2/P3/P4。

---

## 2. 決策紀錄

### 決策 1：產文模式 自由創作 → 套版
- **最終方案**：以市場已驗證爆文原文為骨架，高保真照抄、只換關鍵詞（變動 15–25%）。
- **原因**：解決 content-gen 兩大症狀「方向錯」（骨架已驗證會紅）、「內容假」（血肉來自真實原文）。
- **替代方案**：自由創作迭代（否決：另起爐灶才是病根）。

### 決策 2：架構走方案 B，新 skill content-meme
- **最終方案**：grab-idea / content-gen 不動，中間插獨立套版引擎 content-meme，靠 Ideas DB 鬆耦合。
- **原因**：套版邏輯獨立、好測試。content-meme 主力、content-gen 罕用備援。

### 決策 3：擴散規則 2-3 人設、≥7 天錯開（D3/D4）
- **最終方案**：一筆素材最多 2-3 人設、跨人設發布間隔 ≥7 天。廢除交友類 union 全員 6 人。
- **原因**：高保真照抄下，全員 6 人會撞臉（6 帳號發 80% 雷同文）。

### 決策 4：第二源頭 A 型爆款自動升級（D9）
- **最終方案**：daily/weekly 爬到的 Type=A 自動寫進 Ideas DB（既有 pipeline 補最後一哩）。

### 決策 5：Telegram 預寫 2-3 版並排卡（D10）
- **最終方案**：content-meme 為短名單各寫一版 → Telegram 並排卡 → 鴿王點人設＝選版。content-meme 不直接寫 Posts DB（D12）。

### 決策 6：QC-語義一致（樣本驗證新增）
- **最終方案**：換入專有名詞必須維持原文真實世界關係，禁止盲換；無法查證就別動；語義誠實優先於變動率。
- **原因**：盲換名詞會在變動率 pass 同時造假，比自由創作更危險（披真爆文外皮）。已寫進 SKILL.md + spec §5.4 + 不二錯 #082。

### 決策 7：D13 逐字套版 only，格式套版路由 content-gen
- **最終方案**：content-meme 只做逐字套版（同域、換關鍵詞）；格式套版（換域重寫、爆點在格式）交 content-gen。
- **原因**：長文樣本顯示換域必然變動率爆表（0.87）；怎麼改都進不了 15–25% 即非逐字套版料。

---

## 3. 產出清單

| # | 名稱 | 類型 | 路徑 | 狀態 |
|---|------|------|------|------|
| 1 | 套版流程設計 spec | 文件 | docs/superpowers/specs/2026-06-29-content-meme-套版產文流程-design.md | ✅ commit（docs 分支）|
| 2 | P1 實作計畫 | 文件 | docs/superpowers/plans/2026-06-29-P1-content-meme.md | ✅ commit（docs 分支）|
| 3 | variation_check.py | 程式 | cosmate-ai-nexus/skills/content-meme/scripts/ | ✅ PR #57 |
| 4 | dedup_check.py | 程式 | 同上 | ✅ PR #57 |
| 5 | emit_candidate_bundle.py | 程式 | 同上 | ✅ PR #57 |
| 6 | SKILL.md | skill | 同上 | ✅ PR #57 |
| 7 | SAMPLE_VALIDATION.md | 驗證紀錄 | skills/content-meme/tests/ | ✅ PR #57 |
| 8 | 不二錯 #082 | Notion | https://app.notion.com/p/38f6fedce91a817a87c6d16e1f49cff0 | ✅ |
| 9 | PR #57 | GitHub | cosmate-ai-nexus（9 commits，21 測試綠）| ✅ 開啟，待合 |

---

## 4. 除錯與教訓

### 除錯 1：套版盲換專有名詞 → 語義造假
- **問題**：初版把 Vaundy/黃泉使者 換成 米津玄師/地。，變動率 0.18 pass，但兩者無真實關係，動漫宅一眼看假。
- **根因**：為壓變動率盲換名詞，沒驗證換入詞的真實關係；變動率只量「改多少」量不出「改得對不對」。
- **解法**：web search 查證 米津玄師→KICK BACK→鏈鋸人 OP 真實關係後重做；新增 QC-語義一致。
- **教訓**：套版可照抄結構，但塞進去的事實必須真、可查證；語義誠實優先於變動率。
- **🔁 寫進不二錯？**：是（#082，分類 ASSUMPTION）

### 除錯 2：長文逼出逐字 vs 格式套版之分
- **問題**：把演唱會吐槽清單換域成同人場 → 變動率 0.87 too_high。
- **根因**：該爆文爆點在「格式」而非字句，換域＝內容全重寫，必然超標。
- **解法**：釐清兩種模式；content-meme 只做逐字套版（同域 Olie 去別場 → 0.20 pass），格式套版交 content-gen。
- **教訓**：怎麼改都進不了 15–25%（同域 too_low 撞臉 / 一改 too_high 換域）＝此篇非逐字套版料 → 路由 content-gen。
- **🔁 寫進不二錯？**：否（已固化為 spec D13 + SKILL.md 適用範圍段）

---

## 5. TODO

### 🙋 鴿王要做

| # | 任務 | 時間 | 解鎖什麼 |
|---|------|------|---------|
| 1 | 判定 Task 5 套版品質是否達標 | 隨時 | 解鎖 P1 收尾 + P2/P3/P4 啟動 |
| 2 | 決定 PR #57 是否合併、docs 分支是否開 PR | 隨時 | 程式碼落地 |

### 🤖 Agent 可自動跑

| # | 任務 | 誰 | 票號 | 前置條件 |
|---|------|---|------|---------|
| 1 | 寫 P2（grab-idea 強化）計畫 | 德德 | — | Task 5 過關 |
| 2 | 寫 P3（A 型自動升級橋）計畫 | 德德 | — | Task 5 過關 |
| 3 | 寫 P4（Telegram 並排卡）計畫 | 德德 | — | P1 合併 |
| 4 | 補長文 + 新鮮 A 型樣本各一輪驗證 | 德德 | — | — |

---

## 6. 回寫檢查

| 內容 | 應回寫到 | Notion 已同步？ | 狀態 |
|------|---------|---------------|------|
| QC-語義一致（盲換名詞造假）| 不二錯 DB | ✅ #082 | ✅ |
| 套版流程設計決策 | spec 文件（docs 分支）| — | ✅ |
| content-meme 新模組狀態 | Living Status Doc | ⏳ 見下方說明 | ⏳ |
| Session LOG 本身 | Notion Session LOG DB | ⏳ Step 4 進行中 | ⏳ |

> Living Status：content-meme 尚在 PR 階段（未合 main、未上線），暫不更新 Living Status（待合併上線後再標）。

---

## 7. HANDOFF 摘要

**狀態**：P1（content-meme skill）程式碼完成、PR #57 開啟（21 測試綠、雙審 + 最終 review 過）。兩輪樣本驗證（短文 米津玄師案 + 長文 演唱會清單案）機制驗證通過。
**下一步**：等鴿王判定 Task 5 品質 → 收尾 P1 → 寫並實作 P2（grab-idea 強化）/ P3（A 型自動升級橋）/ P4（Telegram 並排卡）。
**阻塞**：Task 5 品質主觀認可待鴿王拍板。spec/plan 在 docs/content-meme-redesign 分支（未合 main）。

---

## 8. 關鍵觀察

- 這次兩個最有價值的設計洞（QC-語義一致、D13）都是**鴿王逼問逼出來的**，非我主動發現——攻擊者濾鏡有效：鴿王一句「米津玄師跟地。有什麼關係」直接戳破盲換造假；一句長文需求逼出兩種套版模式之分。
- 套版的真正風險不在「抄太多」，而在「抄得像但事實是假」——變動率閘門管前者，QC-語義一致管後者，兩者正交、都要過。
- 變動率閘門的雙端（too_low 撞臉 / too_high 換域）本身就是「這篇適不適合逐字套版」的訊號，意外好用。
