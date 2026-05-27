#!/usr/bin/env python3
"""
notify_pending_signals.py — 查 Notion Trending Signals DB 的 pending 訊號，推 Telegram 提醒。

對齊「❤️‍🔥 Trending Signals DB」(82c8d3ba-db4c-4558-8859-0ae5d7f4ac0b) — 撈 status=pending，
依主題分類排序，組訊息＋附 Notion DB URL，推到 Telegram bot。

環境變數：
  NOTION_TOKEN
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID

用法：
  python3 scripts/notify_pending_signals.py             # 真送
  python3 scripts/notify_pending_signals.py --dry-run   # 只印不送
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import certifi
    _CA_FILE = certifi.where()
except ImportError:
    _CA_FILE = None

PROJECT_DIR = Path(__file__).resolve().parent.parent

TRENDING_DB_ID = "82c8d3badb4c455888590ae5d7f4ac0b"
TRENDING_DB_URL = f"https://www.notion.so/{TRENDING_DB_ID}"

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

TELEGRAM_API = "https://api.telegram.org"

TOPIC_ORDER = ["動漫", "交友", "Cosplay", "其他"]
TOPIC_EMOJI = {"動漫": "🎬", "交友": "💞", "Cosplay": "🎭", "其他": "✨"}


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
    local = _load_dotenv(PROJECT_DIR / ".env")
    return {
        "NOTION_TOKEN": os.environ.get("NOTION_TOKEN") or local.get("NOTION_TOKEN"),
        "TELEGRAM_BOT_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN") or local.get("TELEGRAM_BOT_TOKEN"),
        "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID") or local.get("TELEGRAM_CHAT_ID"),
    }


def notion_query_pending(token: str) -> list:
    """撈所有 status=pending，照 熱度時間戳 desc 排序。"""
    url = f"{NOTION_API}/databases/{TRENDING_DB_ID}/query"
    payload = {
        "filter": {"property": "status", "select": {"equals": "pending"}},
        "sorts": [{"property": "熱度時間戳", "direction": "descending"}],
        "page_size": 100,
    }
    results = []
    cursor = None
    while True:
        body = dict(payload)
        if cursor:
            body["start_cursor"] = cursor
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Notion-Version", NOTION_VERSION)
        req.add_header("Content-Type", "application/json")
        ctx = ssl.create_default_context(cafile=_CA_FILE) if _CA_FILE else ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                r = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"❌ Notion query 失敗: HTTP {e.code} {e.read().decode()[:200]}", file=sys.stderr)
            return results
        results.extend(r.get("results", []))
        if not r.get("has_more"):
            break
        cursor = r.get("next_cursor")
    return results


def _plain_text(rich_text_list: list) -> str:
    return "".join(t.get("plain_text", "") for t in rich_text_list or [])


def extract_row(page: dict) -> dict:
    props = page.get("properties", {})
    title = _plain_text(props.get("原文標題", {}).get("title", []))
    category = (props.get("主題分類", {}).get("select") or {}).get("name", "其他")
    date = (props.get("熱度時間戳", {}).get("date") or {}).get("start", "")
    page_id = page.get("id", "").replace("-", "")
    page_url = f"https://www.notion.so/{page_id}"
    return {"title": title, "category": category, "date": date, "url": page_url}


def _escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_message(rows: list) -> str:
    if not rows:
        return (
            "🔔 <b>Trending Signals 週審提醒</b>\n\n"
            "本週沒有待審訊號 ✅\n\n"
            f"<a href=\"{TRENDING_DB_URL}\">📋 開 Notion DB</a>"
        )

    by_topic = {t: [] for t in TOPIC_ORDER}
    for r in rows:
        by_topic.setdefault(r["category"], []).append(r)

    lines = [
        f"🔔 <b>Trending Signals 週審提醒</b> ({len(rows)} 筆待審)",
        "",
        f"<a href=\"{TRENDING_DB_URL}\">📋 開 Notion DB 一張張審</a>",
        "",
    ]
    for topic in TOPIC_ORDER:
        items = by_topic.get(topic, [])
        if not items:
            continue
        emoji = TOPIC_EMOJI.get(topic, "•")
        lines.append(f"{emoji} <b>{_escape_html(topic)}</b> ({len(items)})")
        for it in items:
            title = _escape_html(it["title"][:80])
            lines.append(f"  • <a href=\"{it['url']}\">{title}</a>")
        lines.append("")

    lines.append("狀態調 <code>approved</code> 後會被 Telegram /gen 的 🔥 鈕讀到。")
    return "\n".join(lines).rstrip()


def send_telegram(bot_token: str, chat_id: str, text: str) -> bool:
    url = f"{TELEGRAM_API}/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    ctx = ssl.create_default_context(cafile=_CA_FILE) if _CA_FILE else ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            r = json.loads(resp.read().decode("utf-8"))
        if not r.get("ok"):
            print(f"❌ Telegram 回 not ok: {r}", file=sys.stderr)
            return False
        return True
    except urllib.error.HTTPError as e:
        print(f"❌ Telegram HTTP {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    secrets = load_secrets()
    if not secrets["NOTION_TOKEN"]:
        sys.exit("❌ NOTION_TOKEN 未設定")
    if not args.dry_run and (not secrets["TELEGRAM_BOT_TOKEN"] or not secrets["TELEGRAM_CHAT_ID"]):
        sys.exit("❌ TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 未設定（真送需要）")

    pages = notion_query_pending(secrets["NOTION_TOKEN"])
    rows = [extract_row(p) for p in pages]
    rows = [r for r in rows if r["title"]]  # 過濾空標題

    msg = build_message(rows)
    print("=== Telegram 訊息預覽 ===")
    print(msg)
    print("=========================")

    if args.dry_run:
        print(f"\n[dry-run] 共 {len(rows)} 筆待審，未送 Telegram")
        return

    ok = send_telegram(secrets["TELEGRAM_BOT_TOKEN"], secrets["TELEGRAM_CHAT_ID"], msg)
    if ok:
        print(f"\n✅ 已送 Telegram（{len(rows)} 筆待審）")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
