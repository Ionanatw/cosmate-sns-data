#!/usr/bin/env python3
"""
backfill_trending_signal_urls.py — 回補 Trending Signals DB 舊 row 缺的「網址」欄

策略：從「萃取公式」末尾的 `— Source: /post/<id>` 抽出 post_key，
組成 `https://www.threads.com{post_key}` PATCH 進「網址」。

Threads 會自動把 /post/<id> redirect 到 /@<author>/post/<id>，所以這個 URL 點得到。

用法：
  python3 scripts/backfill_trending_signal_urls.py --dry-run
  python3 scripts/backfill_trending_signal_urls.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import urllib.request
from pathlib import Path

try:
    import certifi
    _CA = certifi.where()
except ImportError:
    _CA = None

TRENDING_DB_ID = "82c8d3badb4c455888590ae5d7f4ac0b"
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
THREADS_BASE = "https://www.threads.com"

SOURCE_RE = re.compile(r"—\s*Source:\s*(/post/[A-Za-z0-9_-]+)")


def load_env():
    tok = os.environ.get("NOTION_TOKEN")
    if not tok:
        env_path = Path("/Users/ionachen/Documents/Claude/project/.env.threads")
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("NOTION_TOKEN="):
                    tok = line.split("=", 1)[1]
                    break
    if not tok:
        sys.exit("❌ NOTION_TOKEN 未設定")
    return tok


def notion_request(method: str, path: str, token: str, payload: dict | None = None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{NOTION_API}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    ctx = ssl.create_default_context(cafile=_CA) if _CA else ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  ❌ HTTP {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ❌ {e}", file=sys.stderr)
        return None


def iter_rows(token: str):
    cursor = None
    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        r = notion_request("POST", f"/databases/{TRENDING_DB_ID}/query", token, payload)
        if r is None:
            return
        for row in r["results"]:
            yield row
        if not r.get("has_more"):
            return
        cursor = r.get("next_cursor")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只印不寫")
    args = ap.parse_args()

    token = load_env()
    total = patched = skipped_has_url = skipped_no_marker = failed = 0
    skipped_titles = []

    for row in iter_rows(token):
        total += 1
        props = row["properties"]
        title = "".join(t.get("plain_text", "") for t in props.get("原文標題", {}).get("title", []))[:50]

        if props.get("網址", {}).get("url"):
            skipped_has_url += 1
            continue

        formula = "".join(t.get("plain_text", "") for t in props.get("萃取公式", {}).get("rich_text", []))
        m = SOURCE_RE.search(formula)
        if not m:
            skipped_no_marker += 1
            skipped_titles.append(title)
            continue

        post_key = m.group(1)
        url = f"{THREADS_BASE}{post_key}"

        if args.dry_run:
            print(f"  [dry-run] {title[:40]:40s} ← {url}")
            patched += 1
            continue

        result = notion_request("PATCH", f"/pages/{row['id']}", token, {"properties": {"網址": {"url": url}}})
        if result:
            print(f"  ✅ {title[:40]:40s} ← {url}")
            patched += 1
        else:
            failed += 1

    print("\n═══ 結算 ═══")
    print(f"總 row             : {total}")
    print(f"已有網址（跳過）   : {skipped_has_url}")
    print(f"成功{'(dry-run)' if args.dry_run else '回補'}    : {patched}")
    print(f"無 Source marker  : {skipped_no_marker}")
    if skipped_titles:
        print("無 marker 的 row：")
        for t in skipped_titles:
            print(f"  - {t}")
    if failed:
        print(f"失敗              : {failed}")


if __name__ == "__main__":
    main()
