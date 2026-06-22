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

REWRITE_USER_TEMPLATE = """請逆向工程以下原文，用你的人設語氣重寫一篇結構相似的貼文。

規則：
1. 保留原文的段落數（換行位置可微調，但段落總數一致）
2. 保留原文的 emoji 數量（可以換成 OLIE 風格的 emoji）
3. 保留原文的 hashtag，除非該 hashtag 完全不適合 OLIE 人設
4. 字數跟原文上下浮動 20% 內
5. 絕對不能含日文假名（平假名、片假名）— 改用繁體中文或日文漢字
6. 直接輸出純文字貼文，不要 Markdown code block，不要加任何說明文字

原文主題：{topic} / 時間窗：{window}
原文：
---
{original}
---

請只輸出改寫後的貼文內容。"""


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
