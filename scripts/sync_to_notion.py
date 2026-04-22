#!/usr/bin/env python3
"""
sync_to_notion.py — Threads Insights → Notion DB upsert

用法：
  python3 sync_to_notion.py \
    --tmpdir /tmp/threads_insights_cosmate_12345 \
    --account cosmate \
    --token ntn_xxx \
    --db-id 74babecebd5c410e9cd25fb6a7fb3565

邏輯：
  - 讀取 $TMPDIR/posts.json 和 $TMPDIR/insight_{mid}.json
  - 對每篇貼文：query Notion DB by Post ID
    - 存在 → PATCH（更新 6 項指標 + Last Synced）
    - 不存在 → POST（新增完整列）
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta

import urllib.request
import urllib.error

# GMT+8
TZ_GMT8 = timezone(timedelta(hours=8))


def notion_request(method, path, token, payload=None):
    url = f"https://api.notion.com/v1{path}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Notion-Version", "2022-06-28")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  ❌ Notion API {method} {path} → HTTP {e.code}: {body[:200]}", file=sys.stderr)
        return None


def query_by_post_id(db_id, token, post_id):
    """Query Notion DB for a page with matching Post ID (title)."""
    payload = {
        "filter": {
            "property": "Post ID",
            "title": {"equals": post_id}
        }
    }
    result = notion_request("POST", f"/databases/{db_id}/query", token, payload)
    if result and result.get("results"):
        return result["results"][0]["id"]
    return None


def build_page_properties(post_id, account, post_date_iso, text_preview, permalink, metrics):
    """Build Notion page properties dict from post data."""
    now_iso = datetime.now(TZ_GMT8).strftime("%Y-%m-%dT%H:%M:%S+08:00")

    props = {
        "Post ID": {"title": [{"text": {"content": post_id}}]},
        "Account": {"select": {"name": account}},
        "Text Preview": {"rich_text": [{"text": {"content": text_preview[:80]}}]},
        "Last Synced": {"date": {"start": now_iso}},
    }

    if post_date_iso:
        props["Post Date"] = {"date": {"start": post_date_iso}}

    if permalink:
        props["Permalink"] = {"url": permalink}

    for field, metric_key in [
        ("Views",   "views"),
        ("Likes",   "likes"),
        ("Replies", "replies"),
        ("Reposts", "reposts"),
        ("Quotes",  "quotes"),
        ("Shares",  "shares"),
    ]:
        val = metrics.get(metric_key)
        if isinstance(val, (int, float)):
            props[field] = {"number": val}

    return props


# ── Posts DB helpers ─────────────────────────────────────────

ACCOUNT_TO_POSTER = {
    "cosmate": "CosMate小編",
    "olie":    "動漫宅Olie.Huang",
    "dadana":  "宅人Dadana",
    "kiki":    "交友中的Kiki",
}

POSTS_DB_METRICS_MAP = [
    ("瀏覽數", "views"),
    ("讚",     "likes"),
    ("留言",   "replies"),
    ("轉發",   "reposts"),
    ("小飛機", "shares"),
    ("引用",   "quotes"),
]


def query_posts_db_by_post_id(posts_db_id, token, post_id):
    """以 Threads Post ID 為 unique key 查詢 Posts DB。"""
    if not post_id:
        raise ValueError("post_id is required for upsert lookup")
    payload = {
        "filter": {
            "property": "Threads Post ID",
            "rich_text": {
                "equals": str(post_id)  # Threads API 有時回 int
            }
        }
    }
    response = notion_request("POST", f"/databases/{posts_db_id}/query", token, payload)
    # 區分「查無」vs「API error」— error 向上拋，不能吞掉
    if response is None:
        raise RuntimeError(f"Notion API error during upsert lookup for post_id={post_id}")
    results = response.get("results", [])
    return results[0] if results else None


def query_posts_db_by_link(posts_db_id, token, permalink):
    """DEPRECATED: 已由 query_posts_db_by_post_id 取代。保留供參考，勿使用。"""
    raise DeprecationWarning(
        "query_posts_db_by_link is deprecated. Use query_posts_db_by_post_id instead."
    )


def build_posts_db_update_props(metrics):
    """Build properties for updating metrics on an existing Posts DB entry."""
    props = {}
    for field, key in POSTS_DB_METRICS_MAP:
        val = metrics.get(key)
        if isinstance(val, (int, float)):
            props[field] = {"number": val}
    return props


def build_posts_db_new_entry_props(post_id, account, post_date_iso, text_preview, permalink, metrics):
    """Build properties for creating a new Posts DB entry."""
    props = {
        "Headline": {"title": [{"text": {"content": (text_preview or "")[:50]}}]},
        "Platform": {"multi_select": [{"name": "Threads"}]},
        "Format": {"select": {"name": "Post"}},
        "Status": {"status": {"name": "Posted"}},
        "來源": {"select": {"name": "✍️ 人工"}},
    }
    poster = ACCOUNT_TO_POSTER.get(account)
    if poster:
        props["貼文人"] = {"multi_select": [{"name": poster}]}
    if permalink:
        props["Link"] = {"url": permalink}
    if post_date_iso:
        props["Post date"] = {"date": {"start": post_date_iso}}
    props["Threads Post ID"] = {"rich_text": [{"text": {"content": str(post_id)}}]}
    for field, key in POSTS_DB_METRICS_MAP:
        val = metrics.get(key)
        if isinstance(val, (int, float)):
            props[field] = {"number": val}
    return props


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tmpdir",  required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--token",   required=True)
    parser.add_argument("--db-id",   required=True)
    parser.add_argument("--posts-db-id", default="", help="Posts DB ID for dual-write")
    args = parser.parse_args()

    posts_path = os.path.join(args.tmpdir, "posts.json")
    if not os.path.exists(posts_path):
        print(f"  ⚠️  posts.json not found in {args.tmpdir}, skipping sync.", file=sys.stderr)
        return

    posts = json.load(open(posts_path))
    inserted = updated = skipped = 0
    posts_inserted = posts_updated = 0

    for post in posts:
        mid = post["id"]
        text = (post.get("text") or "").replace("\n", " ")
        permalink = post.get("permalink", "")
        timestamp = post.get("timestamp", "")  # e.g. "2026-04-08T12:34:56+0000"

        # Parse ISO timestamp → date string for Notion
        post_date_iso = None
        if timestamp:
            try:
                # Threads returns UTC timestamps like "2026-04-08T12:34:56+0000"
                ts = timestamp.replace("+0000", "+00:00")
                dt_utc = datetime.fromisoformat(ts)
                dt_gmt8 = dt_utc.astimezone(TZ_GMT8)
                post_date_iso = dt_gmt8.strftime("%Y-%m-%dT%H:%M:%S+08:00")
            except Exception:
                post_date_iso = timestamp[:10]  # fallback to date only

        # Load insights
        insight_path = os.path.join(args.tmpdir, f"insight_{mid}.json")
        metrics = {}
        if os.path.exists(insight_path):
            try:
                data = json.load(open(insight_path))
                metrics = {
                    m["name"]: m["values"][0]["value"]
                    for m in data.get("data", [])
                    if m.get("values")
                }
            except Exception:
                pass

        props = build_page_properties(mid, args.account, post_date_iso, text, permalink, metrics)

        existing_page_id = query_by_post_id(args.db_id, args.token, mid)

        if existing_page_id:
            result = notion_request("PATCH", f"/pages/{existing_page_id}", args.token, {"properties": props})
            if result:
                updated += 1
                print(f"  🔄 updated  {mid[:12]}… ({text[:30]})")
            else:
                skipped += 1
        else:
            payload = {
                "parent": {"database_id": args.db_id},
                "properties": props,
            }
            result = notion_request("POST", "/pages", args.token, payload)
            if result:
                inserted += 1
                print(f"  ✅ inserted {mid[:12]}… ({text[:30]})")
            else:
                skipped += 1

        # ── Posts DB sync ──
        if args.posts_db_id and mid:
            try:
                existing = query_posts_db_by_post_id(args.posts_db_id, args.token, mid)
                if existing:
                    existing_page_id = existing["id"]
                    update_props = build_posts_db_update_props(metrics)
                    if update_props:
                        r = notion_request("PATCH", f"/pages/{existing_page_id}", args.token, {"properties": update_props})
                        if r:
                            posts_updated += 1
                            print(f"  📝 Posts DB updated  ({text[:30]})")
                else:
                    new_props = build_posts_db_new_entry_props(mid, args.account, post_date_iso, text, permalink, metrics)
                    r = notion_request("POST", "/pages", args.token, {
                        "parent": {"database_id": args.posts_db_id},
                        "properties": new_props,
                    })
                    if r:
                        posts_inserted += 1
                        print(f"  📝 Posts DB created  ({text[:30]})")
            except (ValueError, RuntimeError) as e:
                print(f"  ⚠️  Posts DB upsert skipped for post_id={mid}: {e}", file=sys.stderr)
                skipped += 1

    print(f"\n  📊 @{args.account}: inserted={inserted}, updated={updated}, skipped={skipped}")
    if args.posts_db_id:
        print(f"  📆 Posts DB: created={posts_inserted}, updated={posts_updated}")


if __name__ == "__main__":
    main()
