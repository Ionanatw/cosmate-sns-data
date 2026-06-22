#!/usr/bin/env python3
"""
create_auto_post_db.py — 一次性 setup 腳本：在 Notion 建 Auto Post DB

跑完拿到的 database_id 要存到：
  1. 本機 .env (project root)         NOTION_AUTO_POST_DB_ID=<id>
  2. GitHub Secrets (auto-post 流程)  NOTION_AUTO_POST_DB_ID
  3. Telegram bot .env (VPS)          NOTION_AUTO_POST_DB_ID

用法：
  python3 scripts/create_auto_post_db.py --parent-page-id <page-id> --dry-run
  python3 scripts/create_auto_post_db.py --parent-page-id <page-id>

parent-page-id 取得方式：在 Notion 開一個空白 page 當作 DB 容器頁，URL 末段的 32 字元 UUID
就是 page_id（記得 share 給 integration）。

環境變數：
  NOTION_TOKEN — 必要（讀自 env 或 .env）
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    import certifi
    _CA_FILE = certifi.where()
except ImportError:
    _CA_FILE = None

PROJECT_DIR = Path(__file__).resolve().parent.parent
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


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


def load_notion_token() -> str | None:
    env_local = _load_dotenv(PROJECT_DIR / ".env")
    return os.environ.get("NOTION_TOKEN") or env_local.get("NOTION_TOKEN")


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
        print(f"❌ Notion {method} {path} → HTTP {e.code}: {body[:400]}", file=sys.stderr)
        return None


# ── DB schema ───────────────────────────────────────────────────────────
# 命名約定：
#   - 中文欄名（跟既有 Posts DB / Trending Signals DB 風格一致，方便人在 Notion 上讀）
#   - select option 值用程式對齊的 snake_case / 英文 key（topic / window / status）

PROPERTIES = {
    "原文標題":          {"title": {}},
    "原文 URL":          {"url": {}},
    "原作者帳號":         {"rich_text": {}},
    "主題": {
        "select": {
            "options": [
                {"name": "anime",    "color": "blue"},
                {"name": "love",     "color": "pink"},
                {"name": "beyblade", "color": "orange"},
                {"name": "zodiac",   "color": "purple"},
                {"name": "mbti",     "color": "green"},
            ]
        }
    },
    "時間窗": {
        "select": {
            "options": [
                {"name": "recent_2d",      "color": "yellow"},
                {"name": "historical_30d", "color": "gray"},
            ]
        }
    },
    "原文內容":           {"rich_text": {}},
    "改寫內容":           {"rich_text": {}},
    "改寫 diff 字數":     {"number": {"format": "number"}},
    "熱度分數":           {"number": {"format": "number"}},
    "掃描日":             {"date": {}},
    "審核狀態": {
        "select": {
            "options": [
                {"name": "pending_review", "color": "yellow"},
                {"name": "approved",       "color": "blue"},
                {"name": "scheduled",      "color": "purple"},
                {"name": "posted",         "color": "green"},
                {"name": "rejected",       "color": "red"},
            ]
        }
    },
    "Post date":          {"date": {}},
    "貼文人": {
        # 跟既有 Posts DB「貼文人」一致用 multi_select + canonical poster 名
        "multi_select": {
            "options": [
                {"name": "動漫宅Olie.Huang", "color": "blue"},
            ]
        }
    },
    "Threads Post ID":    {"rich_text": {}},
    "Permalink":          {"url": {}},
    "Telegram message id": {"number": {"format": "number"}},
}


def build_payload(parent_page_id: str) -> dict:
    return {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "icon":   {"type": "emoji",   "emoji": "🤖"},
        "title":  [{"type": "text", "text": {"content": "Auto Post DB"}}],
        "description": [{"type": "text", "text": {
            "content": "OLIE 半自動發文工作流的候選文池（issue #8 Phase 1）。"
        }}],
        "properties": PROPERTIES,
    }


def main():
    parser = argparse.ArgumentParser(description="一次性 setup: 建立 Auto Post DB")
    parser.add_argument(
        "--parent-page-id", required=True,
        help="Notion parent page id（32 字元 UUID，記得把 page share 給 integration）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只印 payload 不送 API",
    )
    args = parser.parse_args()

    page_id = args.parent_page_id.replace("-", "").strip()
    if len(page_id) != 32:
        sys.exit(f"❌ parent-page-id 看起來不像 Notion UUID（去 dash 後應 32 字元，實際 {len(page_id)}）")

    payload = build_payload(page_id)

    if args.dry_run:
        print("─" * 60)
        print("DRY RUN — payload that would be sent to POST /v1/databases:")
        print("─" * 60)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("─" * 60)
        print(f"properties count: {len(PROPERTIES)}")
        return

    token = load_notion_token()
    if not token:
        sys.exit("❌ 找不到 NOTION_TOKEN（env 或 .env 都沒有）")

    print(f"▶ 建立 Auto Post DB（parent page {page_id[:8]}...）")
    result = notion_request("POST", "/databases", token, payload)
    if not result:
        sys.exit("❌ 建立失敗（看上面的 HTTP error）")

    db_id = result.get("id", "").replace("-", "")
    db_url = result.get("url", "")

    print()
    print("✅ Auto Post DB 建好了")
    print(f"   database_id: {db_id}")
    print(f"   url:         {db_url}")
    print()
    print("把 database_id 存到這三個地方：")
    print(f"  1. {PROJECT_DIR}/.env             NOTION_AUTO_POST_DB_ID={db_id}")
    print( "  2. GitHub Secrets                  NOTION_AUTO_POST_DB_ID")
    print( "  3. Telegram bot VPS .env           NOTION_AUTO_POST_DB_ID")


if __name__ == "__main__":
    main()
