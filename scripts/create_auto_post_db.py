#!/usr/bin/env python3
"""
create_auto_post_db.py — 一次性 setup 腳本：在 Notion 建 Auto Post DB / 補 schema

兩個 mode：
  create  — 在 parent page 底下建一顆全新 DB
  patch   — 對既有空殼 DB（只有預設 title 欄）補上 16 個 properties

跑完拿到的 database_id 要存到：
  1. 本機 .env (project root)         NOTION_AUTO_POST_DB_ID=<id>
  2. GitHub Secrets (auto-post 流程)  NOTION_AUTO_POST_DB_ID
  3. Telegram bot .env (VPS)          NOTION_AUTO_POST_DB_ID

用法：
  # 從零建（建議用這個，最乾淨）
  python3 scripts/create_auto_post_db.py --parent-page-id <page-id> [--dry-run]

  # 既有空殼 DB（你在 Notion UI 建好的）→ 補 schema 進去
  python3 scripts/create_auto_post_db.py --patch-existing <db-id> [--dry-run]

parent-page-id / db-id 取得方式：Notion URL 末段 32 字元 UUID（記得 share 給 integration）。

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


def build_create_payload(parent_page_id: str) -> dict:
    return {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "icon":   {"type": "emoji",   "emoji": "🤖"},
        "title":  [{"type": "text", "text": {"content": "Auto Post DB"}}],
        "description": [{"type": "text", "text": {
            "content": "OLIE 半自動發文工作流的候選文池（issue #8 Phase 1）。"
        }}],
        "properties": PROPERTIES,
    }


def find_existing_title_prop(db: dict) -> str | None:
    """既有 DB 一定有一個 title type 的 property（Notion 強制），找出其 name 用來 rename。"""
    for name, prop in db.get("properties", {}).items():
        if prop.get("type") == "title":
            return name
    return None


def build_patch_payload(existing_title_name: str) -> dict:
    """既有空殼 DB 補 schema：rename 既有 title 欄為「原文標題」+ 加其他 15 個 properties。

    Notion API: PATCH /v1/databases/{id} properties 是 additive
      - { "舊名": { "name": "新名" } }   → rename
      - { "新欄位": { "rich_text": {} } } → add new
      - { "舊欄位": null }                 → delete
    """
    props = {}
    if existing_title_name and existing_title_name != "原文標題":
        props[existing_title_name] = {"name": "原文標題"}
    for name, config in PROPERTIES.items():
        if name == "原文標題":
            continue  # 用 rename 處理，不另外 add
        props[name] = config
    return {"properties": props}


def print_db_info(db_id: str, db_url: str, source: str):
    print()
    print(f"✅ Auto Post DB {source}")
    print(f"   database_id: {db_id}")
    if db_url:
        print(f"   url:         {db_url}")
    print()
    print("把 database_id 存到這三個地方：")
    print(f"  1. {PROJECT_DIR}/.env             NOTION_AUTO_POST_DB_ID={db_id}")
    print( "  2. GitHub Secrets                  NOTION_AUTO_POST_DB_ID")
    print( "  3. Telegram bot VPS .env           NOTION_AUTO_POST_DB_ID")


def normalize_id(raw: str, label: str) -> str:
    cleaned = raw.replace("-", "").strip()
    if len(cleaned) != 32:
        sys.exit(f"❌ {label} 不像 Notion UUID（去 dash 後應 32 字元，實際 {len(cleaned)}）")
    return cleaned


def run_create(parent_page_id: str, dry_run: bool, token: str | None):
    payload = build_create_payload(parent_page_id)
    if dry_run:
        print("─" * 60)
        print("DRY RUN — POST /v1/databases payload:")
        print("─" * 60)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("─" * 60)
        print(f"properties count: {len(PROPERTIES)}")
        return

    if not token:
        sys.exit("❌ 找不到 NOTION_TOKEN（env 或 .env 都沒有）")
    print(f"▶ 建立 Auto Post DB（parent page {parent_page_id[:8]}...）")
    result = notion_request("POST", "/databases", token, payload)
    if not result:
        sys.exit("❌ 建立失敗（看上面的 HTTP error）")
    db_id = result.get("id", "").replace("-", "")
    print_db_info(db_id, result.get("url", ""), "建好了")


def run_patch(db_id: str, dry_run: bool, token: str | None):
    if not token:
        sys.exit("❌ 找不到 NOTION_TOKEN（env 或 .env 都沒有）")

    print(f"▶ 讀取既有 DB schema（{db_id[:8]}...）")
    existing = notion_request("GET", f"/databases/{db_id}", token)
    if not existing:
        sys.exit("❌ 讀取失敗（看上面的 HTTP error）")
    existing_props = list(existing.get("properties", {}).keys())
    title_name = find_existing_title_prop(existing)
    print(f"  既有 {len(existing_props)} 個 properties: {existing_props}")
    print(f"  既有 title 欄: {title_name!r}")

    payload = build_patch_payload(title_name or "")
    rename_count = sum(1 for v in payload["properties"].values() if "name" in v and "type" not in v)
    add_count = len(payload["properties"]) - rename_count

    if dry_run:
        print("─" * 60)
        print(f"DRY RUN — PATCH /v1/databases/{db_id[:8]}... payload:")
        print("─" * 60)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("─" * 60)
        print(f"plan: rename {rename_count} + add {add_count}")
        return

    print(f"▶ PATCH schema（rename {rename_count} + add {add_count}）")
    result = notion_request("PATCH", f"/databases/{db_id}", token, payload)
    if not result:
        sys.exit("❌ patch 失敗（看上面的 HTTP error）")
    final_props = list(result.get("properties", {}).keys())
    print(f"  patch 後 {len(final_props)} 個 properties")
    print_db_info(db_id, result.get("url", ""), "schema 補完了")


def main():
    parser = argparse.ArgumentParser(description="一次性 setup: 建立 / 補 schema Auto Post DB")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--parent-page-id",
        help="從零建：在指定的 parent page 底下建新 DB",
    )
    mode.add_argument(
        "--patch-existing",
        help="補 schema：對既有空殼 DB 加 properties + rename 預設 title 欄",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只印 payload 不送 API",
    )
    args = parser.parse_args()

    token = load_notion_token()

    if args.parent_page_id:
        page_id = normalize_id(args.parent_page_id, "parent-page-id")
        run_create(page_id, args.dry_run, token)
    else:
        db_id = normalize_id(args.patch_existing, "patch-existing")
        run_patch(db_id, args.dry_run, token)


if __name__ == "__main__":
    main()
