"""
notion_lib.py — Notion API helpers + Auto Post DB CRUD（issue #8 PR2）

抽出 extract_trending_signals.py / create_auto_post_db.py 重複的 helpers，
新 PR2+ 的 script 直接 import 用。既有檔暫不動（避免擴大 PR scope）。
"""
from __future__ import annotations

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

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


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
    """讀順序：env var > .env > .env.threads（CI / 舊機器相容）。"""
    env_local = _load_dotenv(PROJECT_DIR / ".env")
    env_threads = _load_dotenv(Path.home() / "Documents/Claude/project/.env.threads")
    if not env_threads:
        env_threads = _load_dotenv(Path("/Users/ionachen/Documents/Claude/project/.env.threads"))
    merged = {**env_local, **env_threads}

    keys = [
        "ANTHROPIC_API_KEY",
        "NOTION_TOKEN",
        "NOTION_AUTO_POST_DB_ID",
        "NOTION_POSTS_DB_ID",
    ]
    return {k: os.environ.get(k) or merged.get(k) for k in keys}


# ── Notion API ───────────────────────────────────────────

def _ctx():
    return ssl.create_default_context(cafile=_CA_FILE) if _CA_FILE else ssl.create_default_context()


def notion_request(method: str, path: str, token: str, payload=None, *, silent: bool = False):
    """送一個 Notion API call。失敗回 None 並印 HTTP error（除非 silent=True）。"""
    url = f"{NOTION_API}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60, context=_ctx()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if not silent:
            body = e.read().decode("utf-8", errors="replace")
            print(f"  ❌ Notion {method} {path} → HTTP {e.code}: {body[:300]}", file=sys.stderr)
        return None


def query_db(db_id: str, token: str, filter_=None, page_size: int = 100) -> list[dict]:
    """查 DB pages（自動分頁，回所有結果）。"""
    results = []
    cursor = None
    while True:
        payload = {"page_size": page_size}
        if filter_:
            payload["filter"] = filter_
        if cursor:
            payload["start_cursor"] = cursor
        resp = notion_request("POST", f"/databases/{db_id}/query", token, payload)
        if not resp:
            break
        results.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return results


def create_page(db_id: str, token: str, properties: dict, children=None) -> dict | None:
    """在 DB 建一頁。"""
    payload = {
        "parent": {"database_id": db_id},
        "properties": properties,
    }
    if children:
        payload["children"] = children
    return notion_request("POST", "/pages", token, payload)


# ── Auto Post DB 特定 helpers ────────────────────────────

OLIE_POSTER = "動漫宅Olie.Huang"  # 跟 Posts DB「貼文人」canonical 一致


def fetch_recent_origin_urls(db_id: str, token: str, days: int = 30) -> set[str]:
    """查 Auto Post DB 過去 N 天的 原文 URL（給去重用）。"""
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone(timedelta(hours=8))) - timedelta(days=days)).date().isoformat()
    pages = query_db(db_id, token, filter_={
        "property": "掃描日",
        "date": {"on_or_after": cutoff},
    })
    urls = set()
    for p in pages:
        url = p.get("properties", {}).get("原文 URL", {}).get("url")
        if url:
            urls.add(url)
    return urls


def build_auto_post_props(*, title: str, original_url: str, author: str, topic: str,
                           window: str, original_text: str, rewritten_text: str,
                           engagement: int, today_iso: str, post_id: str = "") -> dict:
    """把 candidate + rewrite 結果組成 Auto Post DB 的 properties dict。

    對齊 PR1.5 / DB id 3876fedce91a802eaf49c86eba7cd72c 的 16 個欄位。
    PR2 階段只填 12 個 — Permalink/Post date/Telegram message id 等到下游 PR 才填。
    """
    diff = abs(len(rewritten_text) - len(original_text))
    # Notion rich_text 單個 segment 上限 2000 字元，留些 margin
    truncate = lambda s, n=1900: s[:n]  # noqa: E731
    return {
        "原文標題":          {"title": [{"text": {"content": truncate(title, 90)}}]},
        "原文 URL":          {"url": original_url or None},
        "原作者帳號":         {"rich_text": [{"text": {"content": author[:200]}}]},
        "主題":              {"select": {"name": topic}},
        "時間窗":            {"select": {"name": window}},
        "原文內容":           {"rich_text": [{"text": {"content": truncate(original_text)}}]},
        "改寫內容":           {"rich_text": [{"text": {"content": truncate(rewritten_text)}}]},
        "改寫 diff 字數":     {"number": diff},
        "熱度分數":           {"number": engagement},
        "掃描日":             {"date": {"start": today_iso}},
        "審核狀態":           {"select": {"name": "pending_review"}},
        "貼文人":             {"multi_select": [{"name": OLIE_POSTER}]},
        "Threads Post ID":   {"rich_text": [{"text": {"content": post_id}}]} if post_id else {"rich_text": []},
    }
