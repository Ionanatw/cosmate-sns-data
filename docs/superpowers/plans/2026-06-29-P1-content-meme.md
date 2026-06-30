# P1：content-meme 套版引擎 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 `content-meme` skill，把 CosMate Threads 產文從「自由創作」改為「套版」——以爆文原文為骨架，為 2-3 個人設各產一版高保真套版稿（變動率 15–25%），輸出成 candidate bundle 供 Telegram 審核。

**Architecture:** 一個 SKILL.md（LLM 執行套版轉寫）+ 三支 stdlib Python 工具（客觀量測變動率、防撞臉判斷、輸出 bundle）。LLM 負責創意換皮，Python 負責可量測的把關與交接契約。本計畫是 spec 4 子計畫中的 P1（關鍵路徑），完成後須以樣本驗證再接 P2–P4。

**Tech Stack:** Markdown（SKILL.md）、Python 3 stdlib（`difflib`、`datetime`、`json`、`unittest`）。無第三方相依。

**Repo / 工作位置：** `cosmate-ai-nexus`（Private，skills 的 source of truth）。所有檔案在 `skills/content-meme/`。commit 進 cosmate-ai-nexus。

**參考 spec：** `cosmate-sns-data/docs/superpowers/specs/2026-06-29-content-meme-套版產文流程-design.md`

---

## File Structure

```
cosmate-ai-nexus/skills/content-meme/
├── SKILL.md                         # 套版引擎指令（LLM 執行）— Task 4
├── scripts/
│   ├── variation_check.py           # 變動率量測（QC-變動率閘門）— Task 1
│   ├── dedup_check.py               # 防撞臉判斷（≤3 人設 / ≥7 天）— Task 2
│   └── emit_candidate_bundle.py     # 組裝+寫出 candidate bundle JSON — Task 3
└── tests/
    ├── test_variation_check.py      # Task 1
    ├── test_dedup_check.py          # Task 2
    └── test_emit_candidate_bundle.py# Task 3
```

**輸出契約（P1 → P4）：** content-meme 把 2-3 版套版稿寫成單一 JSON，落在 `~/.cosmate/meme_candidates/{idea_id}.json`。P4 的 Telegram bot 讀此目錄渲染並排卡。Schema 由 Task 3 定義。

**職責邊界：**
- `variation_check.py` — 純函式，輸入兩段文字、輸出變動率與是否在 15–25%。不碰 Notion。
- `dedup_check.py` — 純函式，輸入「該 idea 已關聯的貼文清單 + 目標人設 + 目標日期」、輸出可否產。不碰 Notion（查詢由 SKILL.md 用 MCP 做，結果餵進來）。
- `emit_candidate_bundle.py` — 純函式 + 檔案寫出，定義 bundle schema 與帳號路由。
- `SKILL.md` — 編排：讀 idea → 呼叫上述工具 → LLM 轉寫 → 寫 bundle。

---

## Task 1：variation_check.py（變動率量測閘門）

**Files:**
- Create: `cosmate-ai-nexus/skills/content-meme/scripts/variation_check.py`
- Test: `cosmate-ai-nexus/skills/content-meme/tests/test_variation_check.py`

- [ ] **Step 1：建立 skill 目錄骨架**

Run:
```bash
mkdir -p ~/Documents/Claude/cosmate-ai-nexus/skills/content-meme/scripts \
         ~/Documents/Claude/cosmate-ai-nexus/skills/content-meme/tests
```
Expected: 兩個目錄建立成功，無輸出。

- [ ] **Step 2：寫 failing test**

`tests/test_variation_check.py`：
```python
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from variation_check import variation_ratio, check_variation


class TestVariationCheck(unittest.TestCase):
    def test_identical_is_zero_variation(self):
        s = "A" * 100
        self.assertAlmostEqual(variation_ratio(s, s), 0.0, places=4)

    def test_completely_different_is_full_variation(self):
        self.assertAlmostEqual(variation_ratio("A" * 100, "B" * 100), 1.0, places=4)

    def test_twenty_percent_change_in_range(self):
        # 100 字中 20 字不同 → 變動率 0.20
        original = "A" * 80 + "B" * 20
        candidate = "A" * 80 + "C" * 20
        r = variation_ratio(original, candidate)
        self.assertAlmostEqual(r, 0.20, places=4)
        verdict = check_variation(original, candidate)
        self.assertTrue(verdict["in_range"])
        self.assertEqual(verdict["verdict"], "pass")

    def test_too_low_flags_too_low(self):
        original = "A" * 95 + "B" * 5
        candidate = "A" * 95 + "C" * 5  # 變動 0.05
        v = check_variation(original, candidate)
        self.assertFalse(v["in_range"])
        self.assertEqual(v["verdict"], "too_low")

    def test_too_high_flags_too_high(self):
        original = "A" * 60 + "B" * 40
        candidate = "A" * 60 + "C" * 40  # 變動 0.40
        v = check_variation(original, candidate)
        self.assertFalse(v["in_range"])
        self.assertEqual(v["verdict"], "too_high")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3：跑測試確認 FAIL**

Run:
```bash
cd ~/Documents/Claude/cosmate-ai-nexus/skills/content-meme
python3 -m unittest tests.test_variation_check -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'variation_check'`

- [ ] **Step 4：寫最小實作**

`scripts/variation_check.py`：
```python
"""變動率量測：以字元級相似度反推「改了多少」。中文逐字比對，免斷詞。

變動率 = 1 - difflib 相似度。0.0=一字不改，1.0=完全不同。
套版目標區間：0.15–0.25（spec D2）。
"""
import json
import sys
from difflib import SequenceMatcher


def variation_ratio(original: str, candidate: str) -> float:
    """回傳 0.0–1.0 的變動率（1 - 字元級相似度）。"""
    return 1.0 - SequenceMatcher(None, original, candidate).ratio()


def check_variation(original: str, candidate: str, lo: float = 0.15, hi: float = 0.25) -> dict:
    """判斷變動率是否落在 [lo, hi]。回傳 ratio / in_range / verdict。"""
    r = variation_ratio(original, candidate)
    if r < lo:
        verdict = "too_low"
    elif r > hi:
        verdict = "too_high"
    else:
        verdict = "pass"
    return {"ratio": round(r, 4), "in_range": lo <= r <= hi, "verdict": verdict}


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    # 用法: python3 variation_check.py <original.txt> <candidate.txt>
    if len(sys.argv) != 3:
        print("usage: variation_check.py <original.txt> <candidate.txt>", file=sys.stderr)
        sys.exit(2)
    result = check_variation(_read(sys.argv[1]), _read(sys.argv[2]))
    print(json.dumps(result, ensure_ascii=False))
```

- [ ] **Step 5：跑測試確認 PASS**

Run:
```bash
cd ~/Documents/Claude/cosmate-ai-nexus/skills/content-meme
python3 -m unittest tests.test_variation_check -v
```
Expected: PASS（5 個測試全過）

- [ ] **Step 6：commit**

```bash
cd ~/Documents/Claude/cosmate-ai-nexus
git add skills/content-meme/scripts/variation_check.py skills/content-meme/tests/test_variation_check.py
git commit -m "feat(content-meme): add variation_ratio gate for 15-25% transplant QC"
```

---

## Task 2：dedup_check.py（防撞臉判斷）

**Files:**
- Create: `cosmate-ai-nexus/skills/content-meme/scripts/dedup_check.py`
- Test: `cosmate-ai-nexus/skills/content-meme/tests/test_dedup_check.py`

防撞臉規則（spec §5.5 / D3 / D4）：對某 idea 要產給人設 P：(a) 該 idea 已關聯的「不同人設」數已達 3 且 P 不在其中 → 擋；(b) 已有「別的人設」貼文與目標日期間隔 < 7 天 → 擋。同一人設不計入撞臉。

- [ ] **Step 1：寫 failing test**

`tests/test_dedup_check.py`：
```python
import unittest
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dedup_check import check_dedup


class TestDedupCheck(unittest.TestCase):
    def test_empty_history_allowed(self):
        out = check_dedup([], "宅人Dadana", date(2026, 7, 1))
        self.assertTrue(out["allowed"])

    def test_same_persona_does_not_count(self):
        history = [{"persona": "宅人Dadana", "post_date": date(2026, 6, 30)}]
        out = check_dedup(history, "宅人Dadana", date(2026, 7, 1))
        self.assertTrue(out["allowed"])

    def test_third_distinct_persona_ok_fourth_blocked(self):
        history = [
            {"persona": "宅人Dadana", "post_date": date(2026, 6, 1)},
            {"persona": "社畜Amy", "post_date": date(2026, 6, 10)},
            {"persona": "交友中Kiki", "post_date": date(2026, 6, 20)},
        ]
        out = check_dedup(history, "動漫宅Olie.Huang", date(2026, 7, 5))
        self.assertFalse(out["allowed"])
        self.assertIn("人設上限", out["reason"])

    def test_cross_persona_within_7_days_blocked(self):
        history = [{"persona": "社畜Amy", "post_date": date(2026, 7, 1)}]
        out = check_dedup(history, "宅人Dadana", date(2026, 7, 4))  # 間隔 3 天
        self.assertFalse(out["allowed"])
        self.assertIn("間隔", out["reason"])

    def test_cross_persona_after_7_days_allowed(self):
        history = [{"persona": "社畜Amy", "post_date": date(2026, 7, 1)}]
        out = check_dedup(history, "宅人Dadana", date(2026, 7, 10))  # 間隔 9 天
        self.assertTrue(out["allowed"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2：跑測試確認 FAIL**

Run:
```bash
cd ~/Documents/Claude/cosmate-ai-nexus/skills/content-meme
python3 -m unittest tests.test_dedup_check -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'dedup_check'`

- [ ] **Step 3：寫最小實作**

`scripts/dedup_check.py`：
```python
"""防撞臉判斷：一筆 idea 最多 2-3 人設、跨人設發布間隔 ≥7 天（spec §5.5）。

純函式：已關聯貼文清單由呼叫端（SKILL.md 用 Notion MCP 查 Ideas.應用貼文）餵進來。
"""
from datetime import date


def check_dedup(
    linked_posts: list[dict],
    target_persona: str,
    target_date: date,
    max_personas: int = 3,
    min_gap_days: int = 7,
) -> dict:
    """
    linked_posts: [{"persona": str, "post_date": datetime.date}, ...] 該 idea 已關聯的貼文
    回傳 {"allowed": bool, "reason": str}
    """
    personas = {p["persona"] for p in linked_posts}
    if target_persona not in personas and len(personas) >= max_personas:
        return {"allowed": False, "reason": f"已達 {max_personas} 人設上限"}

    for p in linked_posts:
        if p["persona"] == target_persona:
            continue  # 同人設不計撞臉
        gap = abs((target_date - p["post_date"]).days)
        if gap < min_gap_days:
            return {
                "allowed": False,
                "reason": f"與 {p['persona']} 發布間隔 {gap} 天 < {min_gap_days} 天",
            }

    return {"allowed": True, "reason": "ok"}
```

- [ ] **Step 4：跑測試確認 PASS**

Run:
```bash
cd ~/Documents/Claude/cosmate-ai-nexus/skills/content-meme
python3 -m unittest tests.test_dedup_check -v
```
Expected: PASS（5 個測試全過）

- [ ] **Step 5：commit**

```bash
cd ~/Documents/Claude/cosmate-ai-nexus
git add skills/content-meme/scripts/dedup_check.py skills/content-meme/tests/test_dedup_check.py
git commit -m "feat(content-meme): add cross-persona dedup guard (<=3 personas, >=7 day gap)"
```

---

## Task 3：emit_candidate_bundle.py（輸出契約 P1→P4）

**Files:**
- Create: `cosmate-ai-nexus/skills/content-meme/scripts/emit_candidate_bundle.py`
- Test: `cosmate-ai-nexus/skills/content-meme/tests/test_emit_candidate_bundle.py`

定義 candidate bundle schema、帳號路由、寫出到 `~/.cosmate/meme_candidates/{idea_id}.json`。

帳號路由（沿用 threads-publisher 現制）：貼文人含「宅人Dadana」→ `@dadana0618`；含「動漫宅Olie.Huang」→ `@oliehuangmix`；其餘 → `@cosmatedaily`。

- [ ] **Step 1：寫 failing test**

`tests/test_emit_candidate_bundle.py`：
```python
import json
import unittest
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from emit_candidate_bundle import route_account, build_bundle, write_bundle


def _version(persona, variation=0.2):
    return {
        "persona": persona,
        "body": "套版正文……",
        "hashtags": ["#動漫", "#cosplay"],
        "variation": variation,
        "qc": {"variation": "pass", "identity": "pass", "zh_tw": "pass"},
    }


class TestRouteAccount(unittest.TestCase):
    def test_dadana(self):
        self.assertEqual(route_account("宅人Dadana"), "@dadana0618")

    def test_olie(self):
        self.assertEqual(route_account("動漫宅Olie.Huang"), "@oliehuangmix")

    def test_default(self):
        self.assertEqual(route_account("社畜Amy"), "@cosmatedaily")


class TestBuildBundle(unittest.TestCase):
    def test_build_attaches_account_route(self):
        b = build_bundle(
            idea_id="idea-1",
            source_url="https://threads.net/x",
            original_text="原文",
            versions=[_version("宅人Dadana"), _version("社畜Amy")],
        )
        accounts = {v["account"] for v in b["versions"]}
        self.assertEqual(accounts, {"@dadana0618", "@cosmatedaily"})

    def test_reject_fewer_than_two_versions(self):
        with self.assertRaises(ValueError):
            build_bundle("idea-1", "u", "原文", [_version("社畜Amy")])

    def test_reject_more_than_three_versions(self):
        with self.assertRaises(ValueError):
            build_bundle(
                "idea-1", "u", "原文",
                [_version("社畜Amy"), _version("宅人Dadana"),
                 _version("動漫宅Olie.Huang"), _version("交友中Kiki")],
            )

    def test_reject_missing_required_key(self):
        bad = {"persona": "社畜Amy"}  # 缺 body/hashtags/variation/qc
        with self.assertRaises(ValueError):
            build_bundle("idea-1", "u", "原文", [_version("宅人Dadana"), bad])


class TestWriteBundle(unittest.TestCase):
    def test_write_creates_file(self):
        b = build_bundle("idea-9", "u", "原文",
                         [_version("宅人Dadana"), _version("社畜Amy")])
        with tempfile.TemporaryDirectory() as d:
            path = write_bundle(b, out_dir=d)
            self.assertTrue(Path(path).exists())
            loaded = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(loaded["idea_id"], "idea-9")
            self.assertEqual(len(loaded["versions"]), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2：跑測試確認 FAIL**

Run:
```bash
cd ~/Documents/Claude/cosmate-ai-nexus/skills/content-meme
python3 -m unittest tests.test_emit_candidate_bundle -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'emit_candidate_bundle'`

- [ ] **Step 3：寫最小實作**

`scripts/emit_candidate_bundle.py`：
```python
"""組裝並寫出 candidate bundle JSON（content-meme → Telegram bot 的交接契約）。

Bundle schema:
{
  "idea_id": str,
  "source_url": str,
  "original_text": str,
  "versions": [
    {"persona": str, "account": str, "body": str,
     "hashtags": [str], "variation": float,
     "qc": {"variation": "pass"|"too_low"|"too_high", "identity": str, "zh_tw": str}}
  ]   # 2-3 個
}
"""
import json
import os
from pathlib import Path

DEFAULT_OUT_DIR = os.path.expanduser("~/.cosmate/meme_candidates")

_ACCOUNT_ROUTES = [
    ("宅人Dadana", "@dadana0618"),
    ("動漫宅Olie.Huang", "@oliehuangmix"),
]
_DEFAULT_ACCOUNT = "@cosmatedaily"

_REQUIRED_VERSION_KEYS = {"persona", "body", "hashtags", "variation", "qc"}


def route_account(persona: str) -> str:
    """依貼文人決定發布帳號（沿用 threads-publisher 路由）。"""
    for needle, account in _ACCOUNT_ROUTES:
        if needle in persona:
            return account
    return _DEFAULT_ACCOUNT


def _validate_version(v: dict) -> None:
    missing = _REQUIRED_VERSION_KEYS - set(v)
    if missing:
        raise ValueError(f"version 缺欄位: {sorted(missing)}")


def build_bundle(idea_id: str, source_url: str, original_text: str, versions: list[dict]) -> dict:
    if not (2 <= len(versions) <= 3):
        raise ValueError(f"versions 數量必須是 2-3，收到 {len(versions)}")
    out_versions = []
    for v in versions:
        _validate_version(v)
        out_versions.append({**v, "account": route_account(v["persona"])})
    return {
        "idea_id": idea_id,
        "source_url": source_url,
        "original_text": original_text,
        "versions": out_versions,
    }


def write_bundle(bundle: dict, out_dir: str = DEFAULT_OUT_DIR) -> str:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = Path(out_dir) / f"{bundle['idea_id']}.json"
    path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
```

- [ ] **Step 4：跑測試確認 PASS**

Run:
```bash
cd ~/Documents/Claude/cosmate-ai-nexus/skills/content-meme
python3 -m unittest tests.test_emit_candidate_bundle -v
```
Expected: PASS（全部測試過）

- [ ] **Step 5：跑全部測試確認三支工具一起綠**

Run:
```bash
cd ~/Documents/Claude/cosmate-ai-nexus/skills/content-meme
python3 -m unittest discover -s tests -v
```
Expected: PASS（Task 1+2+3 共 ~14 個測試全綠）

- [ ] **Step 6：commit**

```bash
cd ~/Documents/Claude/cosmate-ai-nexus
git add skills/content-meme/scripts/emit_candidate_bundle.py skills/content-meme/tests/test_emit_candidate_bundle.py
git commit -m "feat(content-meme): add candidate bundle writer + account routing (P1->P4 contract)"
```

---

## Task 4：SKILL.md（套版引擎指令）

**Files:**
- Create: `cosmate-ai-nexus/skills/content-meme/SKILL.md`

這是 LLM 執行套版的指令文件，編排三支工具。無單元測試；驗證在 Task 5 用樣本跑。

- [ ] **Step 1：寫 SKILL.md（完整內容）**

`SKILL.md`：
````markdown
---
name: content-meme
description: AI 鴿舍 Threads「套版」產文工具。以市場已驗證的爆文原文為骨架，為 2-3 個人設各產一版高保真套版稿（變動率 15–25%），輸出 candidate bundle 供 Telegram 並排審核。與 content-gen（自由創作）分流：content-meme 是主力，有可套版素材時優先用。MANDATORY TRIGGERS：「套版」「套這篇」「meme 一下」「content-meme」「拿這篇爆文套」「幫 X 套版」「這篇可以套版嗎」。也適用於鴿王說「這篇爆文我想讓 Dadana 發一版」「把這篇改成我們的人設」。
---

# content-meme：套版產文引擎

## 用途
把「自由創作」改為「套版」：爆文骨架照抄、只換人設皮（變動 15–25%）。骨架已驗證會紅 → 方向不歪；血肉來自真實原文 → 不空泛。解決 content-gen 的「方向錯」與「內容假」兩大症狀。

## 進場條件（只挑符合全部的 Ideas DB 列）
- `Priority` = High｜可寫
- `Slack note` ≠ 空（= 有完整原文 = 可套版；這是「可套版」的推導依據，不另設欄位）
- `貼文人` 含目標人設（2-3 人設短名單之一）
- 防撞臉檢查通過（見下）

缺完整原文（Slack note 空）的素材，**不可挑用**。

## 執行流程
1. **載入原文**：讀 Ideas DB 該列的 `Slack note`（發文者原始文字，一字不差）。
2. **載入人設**：讀目標人設的 Content Pillar `Description`（口吻）+ 該人設近 3-5 篇已發貼文（校準）。**人設真理之源 = Pillar Description，不硬編碼。**
3. **防撞臉**：用 Notion MCP 查該 idea 的 `應用貼文` relation → 取每筆的「貼文人 + Post date」→ 餵進 `scripts/dedup_check.py` 的 `check_dedup(linked_posts, 目標人設, 目標日期)`。回 `allowed=False` 就跳過該人設或排到 ≥7 天後。
4. **結構解析**：把原文拆成骨架 — Hook 句型 / 段落序與功能 / 金句 / 互動結尾型 / 節奏。
5. **套版換皮**（為短名單每個人設各做一次，見下方配方）。
6. **套版 QC**（每版逐項過，見下方清單；變動率用 `scripts/variation_check.py` 客觀量測）。
7. **輸出 bundle**：把 2-3 版用 `scripts/emit_candidate_bundle.py` 的 `build_bundle()` + `write_bundle()` 寫成 `~/.cosmate/meme_candidates/{idea_id}.json`，交給 Telegram bot（P4）渲染並排審核卡。**content-meme 到此為止，不直接寫 Posts DB；選中版由 Telegram bot 在鴿王點選後才寫入。**

## ★ 15–25% 換皮配方（心臟）
| 保留 75-85%（骨架照抄） | 替換 15-25%（換人設皮） |
|---|---|
| 開頭 Hook 的句型與鉤法 | Hook 裡的專有名詞 / 情境 → 換進人設世界 |
| 段落數、每段功能、順序 | 主角第一人稱身份 → 換成該人設 |
| 金句 / 爆點句的結構 | 品牌或產品名 → 換掉或移除（避業配感） |
| 列表 / 蓋樓 / 問答的格式 | 結尾互動 CTA → 改成人設語氣 |
| 整體節奏與長度 | Hashtags → 人設 / 主題標籤 |

口吻僅做**輕微**調整（非重寫），骨架忠實優先。

## 套版 QC（逐項過才可輸出）
**新增核心：**
- **QC-保真**：骨架與原文對齊（段落數 / Hook型 / 結尾型一致）。
- **QC-變動率**：用 `variation_check.py` 量測，必須 `verdict == "pass"`（落在 0.15–0.25）。`too_low` → 抄太死有侵權/撞臉風險，加大換皮；`too_high` → 失去套版意義，拉回骨架。
- **QC-身份**：第一人稱設定不違反人設身份（動漫宅 Olie 不冒出不符身份的經歷）。
- **QC-撞臉**：與同 idea 其他人設版本、及該人設近期貼文，措辭不過度雷同。

**沿用舊 QC（發布契約，不能丟）：**
- 正體中文零簡體。
- 禁用詞 + 高頻錯字（查 anti-patterns 不二錯 DB；高頻錯字前 5：貼文/對準/不帶廣告感/口碑/行銷）。
- 業配合規（真人經歷不提產品名）。
- **heading 5 段結構完整**（下游 telegram-bot fetchPostContent 抓內文靠此，不二錯 #063）：## Hook / ## 正文 / ## Hashtags / ## 互動 Hook / ## 備註。
- 字數限制（依 Format）。

## 與其他 skill 的關係
- ⬆️ 上游：`grab-idea`（源 1，Slack 人工發現）+ 每日爬取自動升級（源 2，A 型爆款）→ Ideas DB。
- ⬇️ 下游：Telegram bot（P4）讀 candidate bundle 渲染審核卡 → 鴿王點人設 → 寫 Posts DB → 發布。
- ↔️ 同層：`content-gen`（自由創作）為罕用備援，僅「無爆文可套」時退回。

## 注意事項
- 變動率不靠目測，一律 `variation_check.py` 出數字。
- 防撞臉不靠記憶，一律 `dedup_check.py` 判斷。
- bundle 是 P1↔P4 唯一契約，schema 改動需同步通知 P4。
````

- [ ] **Step 2：結構 lint（確認 SKILL.md 自洽且引用的工具都存在）**

Run:
```bash
cd ~/Documents/Claude/cosmate-ai-nexus/skills/content-meme
test -f scripts/variation_check.py && test -f scripts/dedup_check.py && test -f scripts/emit_candidate_bundle.py && \
grep -q "name: content-meme" SKILL.md && \
grep -q "variation_check.py" SKILL.md && \
grep -q "dedup_check.py" SKILL.md && \
grep -q "emit_candidate_bundle.py" SKILL.md && \
echo "SKILL.md lint OK"
```
Expected: `SKILL.md lint OK`

- [ ] **Step 3：commit**

```bash
cd ~/Documents/Claude/cosmate-ai-nexus
git add skills/content-meme/SKILL.md
git commit -m "feat(content-meme): add SKILL.md transplant engine instructions"
```

---

## Task 5：樣本驗證（spec §7 第 1 步）

**Files:**
- Create: `cosmate-ai-nexus/skills/content-meme/tests/SAMPLE_VALIDATION.md`（驗證紀錄）

用 3-5 篇近期 A 型爆款手動跑一遍 content-meme，確認套版品質。**這是 P1 的驗收關，過了才動 P2-P4。**

- [ ] **Step 1：取樣本**

從 `cosmate-sns-data/data/per_topic/` 既有爬取結果挑 3-5 篇 `Type=A` 的正體中文貼文（含完整原文）。記錄每篇的原文與 source URL。

Run:
```bash
ls ~/Documents/Claude/cosmate-sns-data/data/per_topic/
```
Expected: 看到 anime / love / cosplay 等 JSON；從中挑 A 型樣本。

- [ ] **Step 2：對每篇樣本，為 2 個人設各跑一次套版**

依 SKILL.md 流程手動產出。每版完成後用工具量測：
```bash
cd ~/Documents/Claude/cosmate-ai-nexus/skills/content-meme
# 把原文存 orig.txt、套版稿存 cand.txt
python3 scripts/variation_check.py /tmp/orig.txt /tmp/cand.txt
```
Expected: 每版 `{"verdict": "pass"}`（變動率 0.15–0.25）。

- [ ] **Step 3：填驗證 checklist**

`tests/SAMPLE_VALIDATION.md`，每篇每版逐項打勾：
```markdown
# content-meme 樣本驗證紀錄（2026-06-29）

| 樣本 | 人設 | 變動率 | QC-保真 | QC-身份 | 零簡體 | heading 5 段 | 通過 |
|------|------|--------|---------|---------|--------|--------------|------|
| 樣本1 | Dadana | 0.xx | ✅/❌ | ✅/❌ | ✅/❌ | ✅/❌ | ✅/❌ |
| 樣本1 | Amy    |      |        |        |       |             |      |
| ...   |        |      |        |        |       |             |      |

## 結論
- 變動率落在 15-25% 的比例：__ / __
- 骨架忠實但不撞臉：是 / 否
- 發現需調整 SKILL.md 之處：（列出）
```

- [ ] **Step 4：驗收判斷**

- 若 ≥80% 的版本 QC 全過、且鴿王主觀認可品質 → P1 通過，可開 P2/P3。
- 若不過 → 回頭調 SKILL.md 換皮配方或 QC，重跑 Step 2-3。**不要帶著未驗證的 P1 往下接 P2-P4。**

- [ ] **Step 5：commit 驗證紀錄**

```bash
cd ~/Documents/Claude/cosmate-ai-nexus
git add skills/content-meme/tests/SAMPLE_VALIDATION.md
git commit -m "test(content-meme): record sample validation on A-type viral posts"
```

---

## Self-Review 檢查（撰寫者已跑）

- **Spec coverage**：D1 套版→Task4 SKILL.md；D2 變動率15-25%→Task1+QC；D3/D4 防撞臉→Task2；D5/D6 進場條件→Task4 進場條件；D7 新 skill→全部；D10 預寫2-3版+bundle→Task3+Task4 流程6；D11 可套版推導→Task4 進場條件（Slack note 非空）；D12 不直發→Task4 流程6註記。D8/D9 屬 P2/P3/P4 範圍，本計畫不涵蓋（已於 Architecture 標明）。
- **Placeholder scan**：無 TBD/TODO；所有 code step 附完整程式碼。
- **Type consistency**：`variation_ratio`/`check_variation`/`check_dedup`/`route_account`/`build_bundle`/`write_bundle` 在測試與實作、SKILL.md 引用處名稱一致；bundle schema 在 Task3 定義、Task4 引用一致。
