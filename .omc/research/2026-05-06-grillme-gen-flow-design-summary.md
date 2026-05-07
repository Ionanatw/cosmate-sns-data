# Grill Me 摘要 — Telegram /gen 流程 idea 抓取設計

- **日期**：2026-05-06 GMT+8
- **執行 Agent**：德德（Claude Code CLI, Opus 4.7）
- **對話串**：cosmate-sns-data 工作 session
- **提問數**：Phase 1 = 6 題 + Phase 2 = 3 題
- **方案來源**：基於 KIKI 產文 only 1 idea 命中 + 家裡 session 把 filter 改太嚴的衝突

---

## ✅ 已解決的決策

| # | 決策 | 結論 | 原因 |
|---|------|------|------|
| 1 | 主要 user | 鴿王 + 同事 50/50 | UX 必須對不熟 Notion 的同事也成立 |
| 2 | `Status='列入貼文'` 處理 | 看得到（不 filter）、前綴 `🔄(×N) ` 標記 | 已 curated 的 idea 不該浪費；user 有資訊 agency |
| 3 | `Priority=High｜可寫` 處理 | sort 信號（不 filter） | 鴿王明示「至少 5 個 idea 可選」，gate 不能擋 |
| 4 | `Platform=Threads` 處理 | 移除（不 filter） | 多數 idea 沒填，當必選等於誤殺 |
| 5 | persona 不夠 5 個怎麼辦 | 跨人設補滿，前綴 `🔀 [來源] ` | 鴿王硬性要求每次 ≥ 5 |
| 6 | 5 個都不滿意怎麼辦 | 加「🔄 換一批」+「🎲 自由發揮」雙逃生 | 給 user agency，避免 dead-end |
| 7 | Trending 位置 | 清單底部 `🔥` 按鈕（限 Olie/Dadana/Kiki） | 跟現狀一致，不破壞家裡 session 設計 |

---

## ⏸️ 明確延後的項目

| # | 項目 | 延後原因 | 預計何時處理 |
|---|------|---------|------------|
| 1 | Priority gate ROI 觀察 | bot 跑 3 個月後再看是否有人補 Priority | 觀察 3 個月 |

---

## ⚠️ 未完全解決的風險

| # | 風險 | 為什麼沒解決 | 建議下一步 |
|---|------|------------|-----------|
| 1 | Ideas DB 補貨速度跟不上 bot 消化 | 系統性問題、單靠 bot UX 不能解 | 推 grab-idea 自動化 / 排程 |
| 2 | 同事看不懂 `🔄` / `🔀` emoji 含義 | 第一次見到沒 onboarding | 訊息開頭加圖例說明（已含在實作） |
| 3 | 跨人設 idea 借用後人設語氣不對 | Claude 仍以原 persona 寫，但素材脈絡跨領域 | 先觀察、必要時加 prompt hint |

---

## ⚔️ 挑戰模式發現

| 題 | 鴿王回應 | 影響 |
|----|---------|------|
| Priority gate nudge 跑 3 月仍 0 補的話？ | **「不論哪個答案，每次流程要至少 5 個 idea 可選」** | 直接覆寫 Priority gate 從 filter 變成 sort，這是整次逼問最大轉折 |
| 5 個都不滿意怎麼辦？ | 加 `🔄 換一批` + `🎲 自由發揮` 雙選 | 雙逃生機制納入 design |
| 跨人設補滿時怎麼顯示？ | 前綴 `🔀 [來源人設]` | 同事一眼看到「這不是本人設的 idea」 |

---

## 💡 逼問過程中浮出的洞察

1. **「列入貼文」≠「不能再寫」** — Olie 35 筆裡 34 筆已產過，但每筆 `應用貼文 relation count = 2~3` 早就證明同 idea 寫多版是常態。家裡 session 把它當「已產過要排除」是沿用舊版 SOP 直覺，但與實況不符。

2. **Filter 是粗暴工具，annotation 才是正解** — 對比 family session 的 strict filter「不見」vs 我先前 propose 的 C 方案「換 relation 當 filter」，最終結論是兩個都錯：應該全部讓 user 看到、用視覺標記給足資訊。

3. **「至少 5 個」是 UX 硬規則，不是 nice-to-have** — 鴿王直接覆寫前面 3 題的所有 implementation philosophy。一旦這條成立，Priority/Platform/列入貼文 三個 filter 全部退化成 sort 信號或 annotation。

4. **同事是次要 user 但是 UX 上限** — 鴿王自己怎樣都能用，但「同事不熟 Notion」是 UX 設計的最低標。任何「鴿王看得懂、同事看不懂」的 UX 都不過關。

---

## 📐 完整實作規格

### Filter（Notion query 階段）

```typescript
// queryPendingIdeas / queryRecentIdeas 共用
function ideasBaseFilter(persona: string) {
  return [
    { property: '貼文人', multi_select: { contains: persona } },
    { property: 'Status', status: { does_not_equal: 'Drop' } },
    { property: 'Status', status: { does_not_equal: '不採用' } },
    { property: 'Status', status: { does_not_equal: 'Done' } },
    { property: 'Status', status: { does_not_equal: '⏰ 已過期' } },
    { property: 'Archive', checkbox: { equals: false } },
    // 注意：保留 '列入貼文'（不過濾）、移除 Priority、移除 Platform
  ];
}
```

### Sort（in-memory）

排序 key：
```
1. _priorityRank: 'High｜可寫' = 0, else = 1
2. _draftedRank:  fresh (應用貼文 relation = 0) = 0, else = 1  
3. _crossPersonaRank: 該人設 = 0, 跨人設 = 1
4. _idx: created_time desc 原始順序
```

排序 cascade：`a._crossPersonaRank - b._crossPersonaRank || a._priorityRank - b._priorityRank || a._draftedRank - b._draftedRank || a._idx - b._idx`

跨人設一律後排（即使 fresh + High｜可寫）— 同人設優先。

### 三段查詢確保 ≥ 5 筆

```
Stage A: persona-only base filter (page_size=20, in-memory rank, take all)
  ↓ 若 < 5 補
Stage B: cross-persona base filter (排除 Stage A 已抓到的 pageId, page_size=10)
  → 合併 Stage A + Stage B 取前 5
```

注意：原本逼問時提了三段 (priority gate / persona / cross-persona)，但「至少 5 個」覆寫後簡化為兩段：persona + cross-persona 補滿。Priority 退化為 sort 信號。

### Annotation 規則

| idea 屬性 | label 前綴 |
|----------|-----------|
| 該人設、fresh | （無）|
| 該人設、已產過 N 次 | `🔄(×N) ` |
| 跨人設、fresh | `🔀 [來源] ` |
| 跨人設、已產過 N 次 | `🔀 [來源] 🔄(×N) ` |

讀取：`應用貼文?.relation?.length` 取代「Status='列入貼文'」判斷已產過。

### Keyboard 結構

```
[ 1. 16宮格挑戰 ]                          (cg_i:{pageId})
[ 2. 🔄(×2) 輪到你了 16宮格 ]              (cg_i:{pageId})
[ 3. 🔀 [Olie] 動畫評論 ]                   (cg_i:{pageId})
[ 4. 🔄(×1) 約會踩雷 ]                      (cg_i:{pageId})
[ 5. 16宮格 reels ]                         (cg_i:{pageId})
─ 分隔 ─
[ 🔄 換一批 ]                              (cg_more:1)
[ 🎲 自由發揮 ]                            (cg_freestyle:1)
[ 🔥 來自 Trending System ]                (cg_t:go) — 限 Olie/Dadana/Kiki
```

### 換一批 implementation

- Stage A query 改 `page_size=20`
- 全部存 `pendingContentGen.ideaPool`，只 slice 前 5 顯示
- 點 `cg_more` → cursor +5 取下個 5 筆
- pool 用完再 fetch 新一頁

### 自由發揮 implementation

- 點 `cg_freestyle` → 直接 setState `step='generating'`、`ideaTitle='自由發揮'`
- 呼叫 `finalizeAndReview`（contentgen.ts 已支援 `topic === '自由發揮'`）

### 訊息文案

```
📋 共 {N} 筆素材：
{listText}

💡 圖例：🔄 = 已產過(×次數) ｜ 🔀 = 跨人設借用 ｜ 都不滿意可點下方逃生鍵
```

第一次顯示時帶圖例，後續「換一批」省略（已說明過）。

---

## 📂 檔案影響

| 檔案 | 改動 |
|------|------|
| `notion.ts` | `queryPendingIdeas` 重寫為兩段查詢；`IdeaEntry` 加 `appliedCount` `sourcePersona` 欄位；移除 Priority/Platform filter |
| `callbacks.ts` | `handleContentGenFormat` 改用新 return type；加 `cg_more` / `cg_freestyle` callback；annotation 邏輯 |
| `keyboards.ts` | `ideaListKeyboard` 加 `showMore` `showFreestyle` 參數；callback parser 加 `cg_more` `cg_freestyle` |
| `review.ts` | `PendingContentGen` 加 `ideaPool` `ideaPoolCursor` 欄位 |
| `commands.ts` | 微調自由發揮入口（如需）|

預計改動量：~150 行。

---

## 🔚 下一步

1. 鴿王 review 此 spec
2. 點頭後我開工，做完先 typecheck + tests
3. PR → 等鴿王 / 家裡 session merge
4. VPS `git pull && docker compose up -d --build`
5. Telegram QA topic 各人設跑一輪驗證
