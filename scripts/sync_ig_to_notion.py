#!/usr/bin/env python3
"""
sync_ig_to_notion.py — Instagram Insights → Posts DB upsert

寫入 Posts DB（與 Threads 貼文共用），用 Platform 欄位區分。
欄位名稱對齊 Posts DB 現有結構（中文欄位名）。

用法：
  python3 sync_ig_to_notion.py \
    --tmpdir /tmp/ig_insights_cosmate_12345 \
    --account cosmate \
    --token ntn_xxx \
    --db-id 2106fedce91a81389a54c223533d481b
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta

import urllib.request
import urllib.error

TZ_GMT8 = timezone(timedelta(hours=8))

ACCOUNT_TO_POSTER = {
    "cosmate": "CosMate小編",
    "olie":    "動漫宅Olie.Huang",
    "dadana":  "宅人Dadana",
    "kiki":    "交友中的Kiki",
}

# Posts DB 欄位 → IG metrics key
POSTS_DB_METRICS_MAP = [
    ("瀏覽數", "views"),      # VIDEO/REEL=plays; IMAGE/CAROUSEL=impressions（在 _convert_metrics 統一）
    ("讚",     "likes"),
    ("留言",   "comments"),
    ("轉發",   None),         # IG 沒有轉發概念
    ("小飛機", "shares"),
    ("引用",   None),         # IG 沒有引用概念
    ("Reach",  "reach"),
    ("Saved",  "saved"),
    ("互動次數", "total_interactions"),
    ("平均觀看秒數", "ig_reels_avg_watch_time"),
    ("總觀看時間(分)", "ig_reels_video_view_total_time"),
]


def _convert_metrics(metrics):
    """Convert raw API values to display-friendly units."""
    # IMAGE/CAROUSEL 用 impressions；統一進 views 讓兩平台共用「瀏覽數」欄位
    if "views" not in metrics and "impressions" in metrics:
        metrics["views"] = metrics.pop("impressions")
    # avg watch time: ms → seconds (rounded to 1 decimal)
    if "ig_reels_avg_watch_time" in metrics:
        metrics["ig_reels_avg_watch_time"] = round(metrics["ig_reels_avg_watch_time"] / 1000, 1)
    # total watch time: ms → minutes (rounded to 1 decimal)
    if "ig_reels_video_view_total_time" in metrics:
        metrics["ig_reels_video_view_total_time"] = round(metrics["ig_reels_video_view_total_time"] / 1000 / 60, 1)
    return metrics


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


def query_by_link(db_id, token, permalink):
    """Query Posts DB for a page with matching Link (URL) field."""
    clean_url = permalink.split("?")[0]
    payload = {
        "filter": {
            "property": "Link",
            "url": {"contains": clean_url}
        }
    }
    result = notion_request("POST", f"/databases/{db_id}/query", token, payload)
    if result and result.get("results"):
        return result["results"][0]["id"]
    return None


def build_update_props(metrics):
    """Build properties for updating metrics on an existing Posts DB entry."""
    props = {}
    for field, key in POSTS_DB_METRICS_MAP:
        if key is None:
            continue
        val = metrics.get(key)
        if isinstance(val, (int, float)):
            props[field] = {"number": val}
    return props


def build_new_entry_props(account, post_date_iso, text_preview, permalink, media_type, metrics):
    """Build properties for creating a new Posts DB entry."""
    props = {
        "Headline": {"title": [{"text": {"content": (text_preview or "")[:50]}}]},
        "Platform": {"multi_select": [{"name": "Instagram"}]},
        "Format": {"select": {"name": "Reel" if media_type in ("VIDEO", "REEL") else "Post"}},
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

    if media_type:
        props["Media Type"] = {"select": {"name": media_type}}

    for field, key in POSTS_DB_METRICS_MAP:
        if key is None:
            continue
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
    args = parser.parse_args()

    posts_path = os.path.join(args.tmpdir, "posts.json")
    if not os.path.exists(posts_path):
        print(f"  ⚠️  posts.json not found in {args.tmpdir}, skipping sync.", file=sys.stderr)
        return

    posts = json.load(open(posts_path))
    inserted = updated = skipped = 0

    for post in posts:
        mid = post["id"]
        caption = (post.get("caption") or "").replace("\n", " ")
        permalink = post.get("permalink", "")
        timestamp = post.get("timestamp", "")
        media_type = post.get("media_type", "IMAGE")
        likes = post.get("like_count", 0)
        comments = post.get("comments_count", 0)

        post_date_iso = None
        if timestamp:
            try:
                ts = timestamp.replace("+0000", "+00:00").replace("Z", "+00:00")
                dt_utc = datetime.fromisoformat(ts)
                dt_gmt8 = dt_utc.astimezone(TZ_GMT8)
                post_date_iso = dt_gmt8.strftime("%Y-%m-%dT%H:%M:%S+08:00")
            except Exception:
                post_date_iso = timestamp[:10]

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

        # Use insights likes/comments if available, fall back to media endpoint
        if "likes" not in metrics:
            metrics["likes"] = likes
        if "comments" not in metrics:
            metrics["comments"] = comments

        # Convert units (ms → seconds/minutes)
        metrics = _convert_metrics(metrics)

        # Check if already exists by permalink
        existing_page_id = query_by_link(args.db_id, args.token, permalink) if permalink else None

        if existing_page_id:
            update_props = build_update_props(metrics)
            if update_props:
                result = notion_request("PATCH", f"/pages/{existing_page_id}", args.token, {"properties": update_props})
                if result:
                    updated += 1
                    url = result.get("url", "")
                    print(f"  🔄 updated  ({caption[:30]}) → {url}")
                else:
                    skipped += 1
        else:
            props = build_new_entry_props(
                args.account, post_date_iso, caption, permalink, media_type, metrics
            )
            result = notion_request("POST", "/pages", args.token, {
                "parent": {"database_id": args.db_id},
                "icon": {"type": "emoji", "emoji": "▶️"},
                "properties": props,
            })
            if result:
                inserted += 1
                url = result.get("url", "")
                print(f"  ✅ inserted ({caption[:30]}) → {url}")
            else:
                skipped += 1

    print(f"\n  📸 IG @{args.account}: inserted={inserted}, updated={updated}, skipped={skipped}")


if __name__ == "__main__":
    main()
