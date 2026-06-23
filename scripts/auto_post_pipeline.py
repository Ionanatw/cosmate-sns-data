#!/usr/bin/env python3
"""
auto_post_pipeline.py — OLIE 半自動發文 pipeline（issue #8 PR2）

從 data/raw/auto/*.json 挑 candidates → Claude 改寫 → 寫 Auto Post DB

用法：
  python3 scripts/auto_post_pipeline.py                  # 全跑 (pick → rewrite → sync)
  python3 scripts/auto_post_pipeline.py --top-n 5        # 挑 5 篇（default 3）
  python3 scripts/auto_post_pipeline.py --dry-run        # 不寫 Notion，print 改寫結果
  python3 scripts/auto_post_pipeline.py --pick-only      # 只挑不改寫不寫
  python3 scripts/auto_post_pipeline.py --persona-only   # 只印 OLIE persona system prompt

環境變數（從 env / .env / .env.threads 合併）：
  NOTION_TOKEN              必要
  NOTION_AUTO_POST_DB_ID    必要（除非 --persona-only 或 --pick-only）
  ANTHROPIC_API_KEY         必要（除非 --pick-only / --persona-only）
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "scripts" / "lib"))

from kana_check import find_kana_chars, has_kana  # noqa: E402
from notion_lib import (  # noqa: E402
    build_auto_post_props,
    create_page,
    fetch_recent_origin_urls,
    load_secrets,
)
from persona_loader import OLIE_PERSONA_PAGE_ID, fetch_olie_persona  # noqa: E402
from text_lang import is_zh_tw  # noqa: E402
from topics_auto import TIME_WINDOWS  # noqa: E402

RAW_AUTO_DIR = PROJECT_DIR / "data" / "raw" / "auto"
TZ_TPE = timezone(timedelta(hours=8))

# Threads scraper 把 UI 上的「翻譯」按鈕文字吃進貼文末尾，要清掉
_TRANSLATE_TAIL_RE = re.compile(r"\s+翻譯\s*$")

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"

try:
    import certifi
    _CA_FILE = certifi.where()
except ImportError:
    _CA_FILE = None


# ── stage 1: find latest batch of raw files ────────────────────

def find_latest_batch_files(raw_dir: Path) -> list[Path]:
    """找最新一輪 scraper 跑出的所有檔案（同一個 timestamp suffix）。"""
    files = list(raw_dir.glob("*.json"))
    if not files:
        return []
    latest = max(files, key=lambda p: p.stat().st_mtime)
    # 檔名: {topic}_{window}_{YYYY-MM-DD}_{HHMMSS}.json
    # ts = 末兩個 _-segment
    parts = latest.stem.split("_")
    if len(parts) < 4:
        return [latest]
    ts = "_".join(parts[-2:])
    return sorted(raw_dir.glob(f"*_{ts}.json"))


def parse_topic_window(path: Path) -> tuple[str | None, str | None]:
    """{topic}_{window}_{ts}.json → (topic, window)。window 名固定列表，反查。"""
    stem = path.stem
    for window in TIME_WINDOWS:
        marker = f"_{window}_"
        if marker in stem:
            return stem.split(marker)[0], window
    return None, None


# ── stage 2: load posts + pick ─────────────────────────────────

def load_posts(files: list[Path]) -> list[dict]:
    """載入所有 raw 檔，attach topic/window/engagement 後扁平化。"""
    out = []
    for f in files:
        topic, window = parse_topic_window(f)
        if not topic:
            continue
        try:
            data = json.load(open(f))
        except (OSError, json.JSONDecodeError) as e:
            print(f"  ⚠️  讀 {f.name} 失敗: {e}", file=sys.stderr)
            continue
        for item in data:
            thread = item.get("thread", {})
            text = (thread.get("text") or "").strip()
            text = _TRANSLATE_TAIL_RE.sub("", text).strip()
            if not text:
                continue
            engagement = (
                int(thread.get("like_count", 0) or 0)
                + int(thread.get("reply_count", 0) or 0) * 3
                + int(thread.get("repostCount", 0) or 0) * 2
                + int(thread.get("reshareCount", 0) or 0) * 2
            )
            out.append({
                "topic": topic,
                "window": window,
                "url": thread.get("url", "") or "",
                "post_id": thread.get("code", "") or "",
                "author": thread.get("username", "") or "",
                "text": text,
                "engagement": engagement,
            })
    return out


def pick_candidates(posts: list[dict], top_n: int, exclude_urls: set[str]) -> list[dict]:
    """按 engagement 排 → 跨 topic 平衡挑 N 篇（第一輪 each topic 至多 1 篇）。"""
    pool = [p for p in posts if p["url"] and p["url"] not in exclude_urls]
    pool.sort(key=lambda p: -p["engagement"])

    picked = []
    used_topics = set()
    # round 1: 每 topic 至多 1 篇
    for p in pool:
        if len(picked) >= top_n:
            break
        if p["topic"] in used_topics:
            continue
        picked.append(p)
        used_topics.add(p["topic"])
    # round 2: 補滿，不管 topic
    if len(picked) < top_n:
        for p in pool:
            if len(picked) >= top_n:
                break
            if p in picked:
                continue
            picked.append(p)
    return picked


# ── stage 3: rewrite via Claude ────────────────────────────────

REWRITE_USER_TEMPLATE = """你要把一篇 Threads 爆紅原文，用 OLIE 人設口吻改寫。

從以下三種改寫力道**自動選一種**（看原文長相判斷）：

【方式 A — 微調換值】（最輕）
- 適用：原文已是 viral 結構（短梗、list 對比、結尾問句），有明顯可替換的「梗點」
- 做法：完整結構＋所有資料保留，只換 1-2 個關鍵元素

【方式 B — 散文化＋口吻轉換】（中等）
- 適用：原文是 listicle（編號 1234 點）或正式報告風
- 做法：拿掉編號變散文、合併段落、注入 OLIE 口吻詞、保留所有事實（人事時地物數字），不抄正式結論段

【方式 C — 換 framework】（最重）
- 適用：原文是教學文/學術文（用「重點/識別/覺察/原則」這種名詞化）
- 做法：丟掉教學語氣，重新用 Threads 流行 framework 包裝（「N 個特質」「N 個信號」「N 個徵兆」「N 個 red flag」「N 個跡象」），只保留核心 insight

──────────────────
範例（讓你 calibrate 三種力道）：

【方式 A 範例】
原文：
我的部門星座組成
老闆：處女座
我 ：處女座
組員：處女座
組員：金牛座
有什麼要注意的嗎

改寫：
我的部門星座組成
老闆：處女座
我 ：處女座
組員：處女座
組員：水瓶座
有什麼要注意的嗎

（只動了「金牛座 → 水瓶座」一個字）

【方式 B 範例】
原文：
給予萊爾富極大的肯定
1.所有流程照規矩來
幾點發號碼牌幾點開箱
幾點購買輕輕楚楚
2.沒有任何黑箱作業
沒有認識店員優先拿
沒有同仁親戚優先拿
要買就乖乖排隊
人數滿了就是滿了
3.排隊提供茶葉蛋、杯水與咖啡
而且無限提供
4.探詢每個排隊客人身體狀況
給予這間公司超高肯定
辛苦萊爾富的員工與主管

已屌打其他賣陀螺的通路了
萊爾富利用這波陀螺販賣行銷
真的非常成功
台灣其他企業真的可以多學學
抓住臺灣民眾的心
創造雙贏～

改寫：
說真的 萊爾富這波賣陀螺直接封神
流程清清楚楚 幾點發號碼牌幾點開賣全部寫好

沒有黑箱沒有員工親友先拿 要買就乖乖排

人數到了就是到了 沒有例外
最離譜的是排隊還提供茶葉蛋、水跟咖啡

而且無限續

排個隊被當貴賓招待是什麼概念
還會一個一個問你身體狀況

我排玩具排到被關心身體 這劇情也太溫馨
其他通路真的可以學一下

萊爾富靠這波直接圈了一堆死忠鐵粉

（改動：拿掉編號 1234、丟掉正式結論段「台灣企業可以學」、注入 OLIE 口吻「直接封神/沒有例外/最離譜的是/圈了一堆死忠鐵粉」、所有事實保留）

【方式 C 範例】
原文：
只要妳能學會以下關於「社交心理學」的三個重點，也能找到有趣的好男人
1️⃣ 識別「高級社交技巧」與「真實人格」的差異
高超的接梗能力、恰到好處的眼神互動與情緒價值，本質上是一種「社交技能（Social Skills）」
2️⃣ 重新解讀直男的「回 Email 式溝通」
影片中把老實男形容成「在回公事 Email」
3️⃣ 提升自我覺察：妳在關係中追求的是「刺激」還是「穩定」？

改寫：
如果你正在聊的對象有這 5 個特質
別開心 大概率是海王

1. 接梗能力 100 分
不是天賦 是練習量
你不是測試樣本只有 1

2. 眼神交流節奏完美
這個叫 SOP
不叫真心

3. 你說什麼他都接得住
因為他接過很多人說過的話
這在後端叫 cache hit

4. 細節都記得 但具體計畫永遠在「改天」
時間永遠在未來

5. 凌晨還在線
他閒 或他這時間正好都在聊

聊得來 ≠ 適合
聊技巧跟人品 是兩個 process 別搞錯

（改動：把教學風「3 個重點」換成警告風「5 個特質」framework，丟掉學術名詞化詞彙，注入 OLIE 工程師梗，核心 insight「社交技巧 ≠ 真心」保留）

──────────────────
通則（三種方式都要遵守）：
- 絕對不能含日文假名（平假名、片假名）— 改用繁體中文或日文漢字
- 保留 hashtag（除非該 hashtag 完全不適合 OLIE 人設）
- 不要 Markdown code block 包，直接輸出貼文純文字
- ⚠️ 絕對只輸出改寫後的貼文本身，不要附加任何說明：
  - 不要寫「（改動：...）」「（保留原樣，因為...）」
  - 不要寫括號裡的 meta-comment
  - 不要標註你用了哪種方式
  - 如果原文已經完美不需要改寫，那就用方式 A 換 1-2 個字就好（不要「保留原樣」這個選項）

現在改寫這篇：

主題：{topic} / 時間窗：{window}
原文：
---
{original}
---

只輸出改寫後的貼文內容。"""


def _ctx():
    return ssl.create_default_context(cafile=_CA_FILE) if _CA_FILE else ssl.create_default_context()


def call_claude(system_prompt: str, user_msg: str, api_key: str,
                model: str = ANTHROPIC_MODEL, max_tokens: int = 1024) -> str:
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_msg}],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(ANTHROPIC_URL, data=data, method="POST")
    req.add_header("x-api-key", api_key)
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120, context=_ctx()) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return (body.get("content", [{}])[0].get("text", "") or "").strip()
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        print(f"  ❌ Anthropic HTTP {e.code}: {msg[:300]}", file=sys.stderr)
        return ""
    except urllib.error.URLError as e:
        print(f"  ❌ Anthropic URL error: {e}", file=sys.stderr)
        return ""


def rewrite_one(candidate: dict, system_prompt: str, api_key: str) -> dict:
    user_msg = REWRITE_USER_TEMPLATE.format(
        topic=candidate["topic"],
        window=candidate["window"],
        original=candidate["text"],
    )
    rewritten = call_claude(system_prompt, user_msg, api_key)
    if not rewritten:
        return {"ok": False, "reason": "Claude API 回空字串", "rewritten": "", "candidate": candidate}
    if has_kana(rewritten):
        hit = find_kana_chars(rewritten)[:5]
        return {
            "ok": False,
            "reason": f"含日文假名: {''.join(hit)}",
            "rewritten": rewritten,
            "candidate": candidate,
        }
    return {"ok": True, "rewritten": rewritten, "candidate": candidate}


# ── stage 4: sync to Notion ────────────────────────────────────

def sync_to_notion(rewrite_results: list[dict], db_id: str, token: str, dry_run: bool) -> list[str]:
    today = datetime.now(TZ_TPE).date().isoformat()
    page_ids = []
    for r in rewrite_results:
        c = r["candidate"]
        if not r["ok"]:
            print(f"  ⏭  跳過 {c['topic']}/{c['window']}: {r['reason']}")
            continue
        # 標題：取改寫後前 80 字（headline 給 Notion list view 看）
        title = (r["rewritten"].splitlines()[0] if r["rewritten"] else c["text"])[:80]
        props = build_auto_post_props(
            title=title,
            original_url=c["url"],
            author=f"@{c['author']}" if c["author"] else "",
            topic=c["topic"],
            window=c["window"],
            original_text=c["text"],
            rewritten_text=r["rewritten"],
            engagement=c["engagement"],
            today_iso=today,
            post_id=c["post_id"],
        )
        if dry_run:
            print(f"  📋 [dry-run] would create: {c['topic']}/{c['window']} {c['url'][:60]}")
            print(f"      title: {title}")
            print(f"      rewritten ({len(r['rewritten'])} 字):")
            for line in r["rewritten"].splitlines():
                print(f"        {line}")
            continue
        result = create_page(db_id, token, props)
        if result:
            page_ids.append(result["id"])
            print(f"  ✅ 寫入: {result.get('url', result['id'])}")
        else:
            print(f"  ❌ 寫入失敗: {c['url']}")
    return page_ids


# ── main ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OLIE 半自動發文 pipeline")
    parser.add_argument("--top-n", type=int, default=3, help="挑幾篇 candidates（default 3）")
    parser.add_argument("--dry-run", action="store_true", help="改寫但不寫 Notion，print 結果")
    parser.add_argument("--pick-only", action="store_true", help="只挑不改寫不寫")
    parser.add_argument("--persona-only", action="store_true", help="只印 OLIE persona system prompt")
    parser.add_argument("--raw-dir", default=str(RAW_AUTO_DIR), help="raw 檔目錄")
    args = parser.parse_args()

    secrets = load_secrets()
    if not secrets.get("NOTION_TOKEN"):
        sys.exit("❌ NOTION_TOKEN 缺（檢查 env / .env）")

    # 早出：只看 persona
    if args.persona_only:
        prompt, source = fetch_olie_persona(secrets["NOTION_TOKEN"])
        print("─" * 60)
        print(f"OLIE persona system prompt ({len(prompt)} 字，source={source}):")
        print("─" * 60)
        print(prompt)
        if source == "fallback":
            print("─" * 60)
            print(f"⚠️  用了 inline fallback — 把 Notion page {OLIE_PERSONA_PAGE_ID[:8]}... share 給 integration 才能讀完整版")
        return

    # 1. find raw
    raw_dir = Path(args.raw_dir)
    files = find_latest_batch_files(raw_dir)
    if not files:
        sys.exit(f"❌ {raw_dir} 沒檔案 — 先跑：python3 scripts/scrape_auto_topics.py")
    print(f"📂 載入 {len(files)} 個 raw 檔（最新一輪）")
    for f in files:
        topic, window = parse_topic_window(f)
        print(f"   {topic}/{window} ← {f.name}")

    # 2. load posts + zh-TW 過濾（OLIE 受眾是繁中讀者，英文/簡中原文改寫變再創作沒意義）
    all_posts = load_posts(files)
    before = len(all_posts)
    all_posts = [p for p in all_posts if is_zh_tw(p["text"])]
    print(f"   total {before} 篇 → zh-TW 過濾後 {len(all_posts)} 篇")

    # 3. dedupe — 查 Auto Post DB 30 天內已用的原文 URL
    db_id = secrets.get("NOTION_AUTO_POST_DB_ID")
    if not db_id:
        sys.exit("❌ NOTION_AUTO_POST_DB_ID 缺（檢查 env / .env）")
    exclude = fetch_recent_origin_urls(db_id, secrets["NOTION_TOKEN"])
    print(f"🚫 排除 30 天內已用的 {len(exclude)} 個 URL")

    # 4. pick
    picked = pick_candidates(all_posts, args.top_n, exclude)
    print(f"🎯 挑出 {len(picked)} 篇 candidates")
    for c in picked:
        preview = c["text"].replace("\n", " ")[:60]
        print(f"   - [{c['topic']:8} {c['window']:14}] eng={c['engagement']:>5}  {preview}")

    if args.pick_only or not picked:
        return

    # 5. load persona
    api_key = secrets.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("❌ ANTHROPIC_API_KEY 缺")
    print("📖 載入 OLIE persona...")
    system_prompt, source = fetch_olie_persona(secrets["NOTION_TOKEN"])
    print(f"   persona {len(system_prompt)} 字（source={source}）")
    if source == "fallback":
        print("   ⚠️  Notion page 載不到，用 inline fallback（人設較簡略）")

    # 6. rewrite
    print("✍️  改寫中...")
    rewrites = []
    for c in picked:
        result = rewrite_one(c, system_prompt, api_key)
        rewrites.append(result)
        mark = "✅" if result["ok"] else "❌"
        info = f"{len(result.get('rewritten', ''))} 字" if result["ok"] else result["reason"]
        print(f"   {mark} {c['topic']}/{c['window']} → {info}")

    # 7. sync
    print("💾 同步 Auto Post DB" + ("（dry-run）" if args.dry_run else "") + "...")
    page_ids = sync_to_notion(rewrites, db_id, secrets["NOTION_TOKEN"], args.dry_run)

    ok_count = sum(1 for r in rewrites if r["ok"])
    print(f"\n═══ 完成 ═══")
    print(f"  候選     {len(picked)} 篇")
    print(f"  改寫通過 {ok_count} 篇")
    if not args.dry_run:
        print(f"  寫入 DB  {len(page_ids)} 篇")


if __name__ == "__main__":
    main()
