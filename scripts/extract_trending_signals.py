#!/usr/bin/env python3
"""
extract_trending_signals.py — 從 data/per_topic/*.json 萃取「爆文公式」寫入 Notion Trending Signals DB

對齊 Notion 「❤️‍🔥 Trending Signals DB」(82c8d3ba-db4c-4558-8859-0ae5d7f4ac0b) schema：
  - 原文標題  (title)        ← Claude 產出的摘要標題
  - 萃取公式  (rich_text)    ← 「情境 + 爆點 + 收尾」結構，末尾附 — Source: <URL> 作為 dedupe 錨點
  - 主題分類  (select)        ← 動漫 / 交友 / Cosplay / 其他
  - 適用人設  (multi_select)  ← Olie / Dadana / Kiki（不含 Amy）
  - 熱度時間戳 (date)         ← 爬到的時間（today）
  - status   (select)         ← pending（給鴿王人工 review）
  - is_evergreen (checkbox)   ← Claude 判斷長青 / 時效

用法：
  python3 scripts/extract_trending_signals.py                     # 預設：anime/love/cosplay 各取 top 5
  python3 scripts/extract_trending_signals.py --top-n 3
  python3 scripts/extract_trending_signals.py --topics anime
  python3 scripts/extract_trending_signals.py --dry-run           # 只印不寫
  python3 scripts/extract_trending_signals.py --expire-only       # 只跑過期掃除

環境變數：
  NOTION_TOKEN         — Notion integration token（必要，除非 --dry-run）
  ANTHROPIC_API_KEY    — Claude API key（必要，除非 --expire-only）

Dedupe 策略：
  不修改 DB schema。每筆萃取公式末尾附 `\n\n— Source: <post-permalink>`，
  寫入前用 rich_text.contains(permalink_path) 查重。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import certifi
    _CA_FILE = certifi.where()
except ImportError:
    _CA_FILE = None

PROJECT_DIR = Path(__file__).resolve().parent.parent
PER_TOPIC_DIR = PROJECT_DIR / "data" / "per_topic"

TZ_GMT8 = timezone(timedelta(hours=8))

TRENDING_DB_ID = "82c8d3badb4c455888590ae5d7f4ac0b"

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

TOPIC_TO_CATEGORY = {
    "anime": "動漫",
    "love": "交友",
    "cosplay": "Cosplay",
}

DEFAULT_PERSONAS = {
    "動漫": ["Olie", "Dadana"],
    "交友": ["Kiki", "Dadana"],
    "Cosplay": ["Olie", "Dadana"],
    "其他": ["Olie", "Dadana", "Kiki"],
}

VALID_PERSONAS = {"Olie", "Dadana", "Kiki"}
VALID_CATEGORIES = {"動漫", "交友", "Cosplay", "其他"}

EVERGREEN_KEEP_DAYS = 7
SOURCE_MARKER = "— Source: "


# ── env loading ──────────────────────────────────────────

def _load_dotenv(path: Path) -> dict:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def load_secrets() -> dict:
    env_local = _load_dotenv(PROJECT_DIR / ".env")
    # .env.threads 路徑：先試 $HOME，再 fallback ionachen（CI / 舊機器相容）
    env_threads = _load_dotenv(Path.home() / "Documents/Claude/project/.env.threads")
    if not env_threads:
        env_threads = _load_dotenv(Path("/Users/ionachen/Documents/Claude/project/.env.threads"))
    merged = {**env_local, **env_threads}
    return {
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY") or merged.get("ANTHROPIC_API_KEY"),
        "NOTION_TOKEN": os.environ.get("NOTION_TOKEN") or merged.get("NOTION_TOKEN"),
    }


# ── Notion helpers ───────────────────────────────────────

def notion_request(method: str, path: str, token: str, payload=None):
    url = f"{NOTION_API}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    ctx = ssl.create_default_context(cafile=_CA_FILE) if _CA_FILE else ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  ❌ Notion {method} {path} → HTTP {e.code}: {body[:200]}", file=sys.stderr)
        return None


def extract_post_key(url: str) -> str:
    """Threads URL → 取 /post/XXXX 或末段作為穩定 dedupe key。"""
    if not url:
        return ""
    m = re.search(r"/post/([^/?#]+)", url)
    if m:
        return f"/post/{m.group(1)}"
    return url.split("?", 1)[0].rstrip("/")


def query_existing_by_source(token: str, post_key: str) -> bool:
    """檢查 DB 是否已有同一篇 source（用 萃取公式 rich_text contains 比對）。"""
    if not post_key:
        return False
    payload = {
        "filter": {
            "property": "萃取公式",
            "rich_text": {"contains": post_key},
        },
        "page_size": 1,
    }
    r = notion_request("POST", f"/databases/{TRENDING_DB_ID}/query", token, payload)
    if r is None:
        return True  # 保守：API 失敗時當作存在，避免重複寫
    return bool(r.get("results"))


def build_page_props(title: str, formula: str, category: str, personas: list, evergreen: bool, today_iso: str, permalink: str = "") -> dict:
    props = {
        "原文標題": {"title": [{"text": {"content": title[:120]}}]},
        "萃取公式": {"rich_text": [{"text": {"content": formula[:1900]}}]},
        "主題分類": {"select": {"name": category}},
        "適用人設": {"multi_select": [{"name": p} for p in personas]},
        "熱度時間戳": {"date": {"start": today_iso}},
        "status": {"select": {"name": "pending"}},
        "is_evergreen": {"checkbox": bool(evergreen)},
    }
    if permalink:
        props["網址"] = {"url": permalink}
    return props


def build_body_children(post_text: str) -> list:
    """把原文塞進 page body，超過 1900 字切成多個 paragraph block。"""
    text = (post_text or "").strip()
    if not text:
        return []
    CHUNK = 1900
    chunks = [text[i:i + CHUNK] for i in range(0, len(text), CHUNK)]
    return [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": c}}]},
        }
        for c in chunks
    ]


def create_signal_page(token: str, props: dict, children: list | None = None):
    payload = {"parent": {"database_id": TRENDING_DB_ID}, "properties": props}
    if children:
        payload["children"] = children
    return notion_request("POST", "/pages", token, payload)


# ── Claude extraction ────────────────────────────────────

def call_claude(api_key: str, prompt: str) -> dict | None:
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 800,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        ANTHROPIC_URL, data=body, method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    ctx = ssl.create_default_context(cafile=_CA_FILE) if _CA_FILE else ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"    ❌ Claude API 失敗: {e}", file=sys.stderr)
        return None
    try:
        text = result["content"][0]["text"].strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("\n", 1)[0]
            if text.startswith("json"):
                text = text[4:].lstrip()
        return json.loads(text)
    except Exception as e:
        print(f"    ⚠️  解析 Claude 回應失敗: {e}", file=sys.stderr)
        return None


def build_extraction_prompt(category: str, post: dict) -> str:
    text = (post.get("text") or "").strip()
    author = post.get("author") or ""
    likes = post.get("likes", 0)
    comments = post.get("comments", 0)
    reposts = post.get("reposts", 0)
    shares = post.get("shares", 0)
    p_type = post.get("primary_type") or "?"

    return f"""你是台灣 Threads 社群爆文公式分析師，幫 AI 鴿舍把以下爆文反推成「可重複使用的公式」。

主題分類：{category}（Trending Signals DB 限定 動漫 / 交友 / Cosplay / 其他）
原文作者：@{author}
互動數據：❤️ {likes} | 💬 {comments} | 🔁 {reposts} | ✈️ {shares} | Type {p_type}
原文：
\"\"\"{text}\"\"\"

請判斷是否值得做成「公式」並回傳 JSON（**直接回 JSON，不要 markdown 包裝**）：

{{
  "skip": false,
  "skip_reason": "若 skip=true 才填，否則空字串。下列情況應 skip：純廣告、純新聞轉述、無敘事結構、單純截圖梗無法複製、需要當下時事才成立",
  "title": "≤40 字的『原文摘要（爆文公式名）』格式，例：『交友配對慘案截圖＋一句神評論：對話反差製造共鳴轉發』",
  "formula": "嚴格用『情境：... → 爆點：... → 收尾：...』三段式結構，每段 30-60 字，可直接給其他人套用",
  "personas": ["Olie 或 Dadana 或 Kiki 的子集；不得包含 Amy；最多 3 個"],
  "evergreen": true 或 false（true = 公式不依附當下熱點，半年後仍能套；false = 需要時事/特定季節）
}}

要求：
1. 公式必須抽象到任何人都能套用，不能只是描述這篇貼文發生了什麼
2. personas 對齊主題：動漫優先 Olie/Dadana、交友優先 Kiki/Dadana、Cosplay 優先 Olie/Dadana
3. 若 skip=true，其餘欄位可填空字串 / 空陣列
4. 用繁體中文
"""


# ── Source selection ─────────────────────────────────────

def load_topic_data(topic: str) -> dict | None:
    path = PER_TOPIC_DIR / f"{topic}.json"
    if not path.exists():
        print(f"  ⚠️  {topic}: 找不到 {path}，跳過")
        return None
    return json.load(open(path, encoding="utf-8"))


def candidate_posts(data: dict, top_n: int) -> list:
    """優先 Type A 全能爆款，不足再用 by total_engagement top。"""
    seen_urls = set()
    out = []
    for p in data.get("by_type", {}).get("A", []):
        if p["url"] in seen_urls:
            continue
        out.append(p)
        seen_urls.add(p["url"])
        if len(out) >= top_n:
            return out
    for p in data.get("top_posts", []):
        if p["url"] in seen_urls:
            continue
        out.append(p)
        seen_urls.add(p["url"])
        if len(out) >= top_n:
            break
    return out


# ── Expiry sweeper ───────────────────────────────────────

def expire_old_signals(token: str, dry_run: bool = False) -> int:
    """掃 status != expired AND is_evergreen != true AND 熱度時間戳 < today - 7d，標 expired。"""
    cutoff = (datetime.now(TZ_GMT8) - timedelta(days=EVERGREEN_KEEP_DAYS)).date().isoformat()
    payload = {
        "filter": {
            "and": [
                {"property": "is_evergreen", "checkbox": {"equals": False}},
                {"property": "熱度時間戳", "date": {"before": cutoff}},
                {"property": "status", "select": {"does_not_equal": "expired"}},
            ]
        },
        "page_size": 100,
    }
    expired = 0
    cursor = None
    while True:
        if cursor:
            payload["start_cursor"] = cursor
        r = notion_request("POST", f"/databases/{TRENDING_DB_ID}/query", token, payload)
        if r is None:
            break
        for page in r.get("results", []):
            title_prop = page.get("properties", {}).get("原文標題", {})
            title = "".join(t["plain_text"] for t in title_prop.get("title", []))[:40]
            if dry_run:
                print(f"  🕐 [dry-run] 會標 expired: {title}")
            else:
                upd = notion_request(
                    "PATCH",
                    f"/pages/{page['id']}",
                    token,
                    {"properties": {"status": {"select": {"name": "expired"}}}},
                )
                if upd:
                    print(f"  🕐 expired: {title}")
                    expired += 1
        if not r.get("has_more"):
            break
        cursor = r.get("next_cursor")
    return expired


# ── Main ─────────────────────────────────────────────────

def process_topic(topic: str, top_n: int, secrets: dict, dry_run: bool, today_iso: str) -> tuple:
    category = TOPIC_TO_CATEGORY.get(topic, "其他")
    data = load_topic_data(topic)
    if not data:
        return 0, 0, 0

    candidates = candidate_posts(data, top_n * 2)  # 多撈一點，扣掉重複後夠 top_n
    if not candidates:
        print(f"  ⚠️  {topic}: 無候選貼文")
        return 0, 0, 0

    print(f"\n── {topic} → {category} （{len(candidates)} 候選, 目標 {top_n} 筆）──")

    inserted = skipped_dup = skipped_ai = 0
    for post in candidates:
        if inserted >= top_n:
            break
        url = post.get("url", "")
        post_key = extract_post_key(url)
        author = post.get("author", "?")
        preview = (post.get("text") or "")[:40].replace("\n", " ")

        if not dry_run and secrets.get("NOTION_TOKEN") and query_existing_by_source(secrets["NOTION_TOKEN"], post_key):
            print(f"  ⏭  dedupe @{author}: {preview}")
            skipped_dup += 1
            continue

        print(f"  🤖 @{author}: {preview}…")
        extraction = call_claude(secrets["ANTHROPIC_API_KEY"], build_extraction_prompt(category, post))
        if not extraction:
            skipped_ai += 1
            continue
        if extraction.get("skip"):
            print(f"    ⏭  Claude skip: {extraction.get('skip_reason','(no reason)')[:40]}")
            skipped_ai += 1
            continue

        title = (extraction.get("title") or "").strip() or preview[:30]
        formula_body = (extraction.get("formula") or "").strip()
        if not formula_body:
            print("    ⏭  公式為空")
            skipped_ai += 1
            continue
        formula = f"{formula_body}\n\n{SOURCE_MARKER}{post_key}"

        personas = [p for p in (extraction.get("personas") or []) if p in VALID_PERSONAS][:3]
        if not personas:
            personas = DEFAULT_PERSONAS[category]

        evergreen = bool(extraction.get("evergreen", False))
        props = build_page_props(title, formula, category, personas, evergreen, today_iso, permalink=url)
        children = build_body_children(post.get("text") or "")

        if dry_run:
            print(f"    [dry-run] would create: {title}")
            print(f"               公式: {formula_body[:60]}…")
            print(f"               personas={personas} evergreen={evergreen}")
            print(f"               網址: {url}")
            print(f"               body blocks: {len(children)}")
            inserted += 1
            continue

        page = create_signal_page(secrets["NOTION_TOKEN"], props, children=children)
        if page:
            print(f"    ✅ created: {title}")
            inserted += 1
        else:
            print("    ⚠️  寫入失敗")

    return inserted, skipped_dup, skipped_ai


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", nargs="+", default=["anime", "love", "cosplay"])
    ap.add_argument("--top-n", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--expire-only", action="store_true", help="只跑 7 天過期掃除")
    ap.add_argument("--no-expire", action="store_true", help="不跑過期掃除")
    args = ap.parse_args()

    secrets = load_secrets()
    if not args.dry_run and not secrets["NOTION_TOKEN"]:
        sys.exit("❌ NOTION_TOKEN 未設定（env var 或 .env）")
    if not args.expire_only and not secrets["ANTHROPIC_API_KEY"]:
        sys.exit("❌ ANTHROPIC_API_KEY 未設定")

    today_iso = datetime.now(TZ_GMT8).date().isoformat()

    if args.expire_only:
        print(f"=== 過期掃除（cutoff: 早於 {EVERGREEN_KEEP_DAYS} 天 + is_evergreen=No）===")
        n = expire_old_signals(secrets["NOTION_TOKEN"], dry_run=args.dry_run)
        print(f"\n═══ 完成：{n} 筆標為 expired ═══")
        return

    print(f"=== 萃取 Trending Signals — {today_iso} | top-n={args.top_n} | dry-run={args.dry_run} ===")

    totals = {"ins": 0, "dup": 0, "ai": 0}
    for topic in args.topics:
        ins, dup, ai = process_topic(topic, args.top_n, secrets, args.dry_run, today_iso)
        totals["ins"] += ins
        totals["dup"] += dup
        totals["ai"] += ai

    print(f"\n═══ 萃取完成：寫入 {totals['ins']} | dedupe 跳過 {totals['dup']} | AI/skip 跳過 {totals['ai']} ═══")

    if not args.no_expire and not args.dry_run and secrets.get("NOTION_TOKEN"):
        print("\n=== 順手掃過期 ===")
        n = expire_old_signals(secrets["NOTION_TOKEN"], dry_run=False)
        print(f"═══ {n} 筆標 expired ═══")


if __name__ == "__main__":
    main()
