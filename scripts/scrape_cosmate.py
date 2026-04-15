#!/usr/bin/env python3
"""
抓取 @cosmatedaily 近 N 天的貼文與 insights（官方 Threads Graph API）。
輸出格式與 Apify scraper 相容，可直接被 analyze_by_topic.py 讀取。

Token 來源：/Users/ionachen/Documents/Claude/project/.env.threads
  - THREADS_USERID_COSMATE
  - THREADS_TOKEN_COSMATE

用法：
  python3 scripts/scrape_cosmate.py          # 近 30 天
  python3 scripts/scrape_cosmate.py --days 7 # 近 7 天
"""
import json, sys, os, ssl, argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen

try:
    import certifi
    _CA_FILE = certifi.where()
except ImportError:
    _CA_FILE = None

PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
ENV_FILE = Path("/Users/ionachen/Documents/Claude/project/.env.threads")
API_BASE = "https://graph.threads.net/v1.0"
TZ_TPE = timezone(timedelta(hours=8))


def load_env():
    """先讀環境變數（CI/雲端用），否則 fallback 到 .env.threads（本機用）"""
    keys = ("THREADS_USERID_COSMATE", "THREADS_TOKEN_COSMATE", "THREADS_USERNAME_COSMATE")
    env = {k: os.environ[k] for k in keys if os.environ.get(k)}
    if all(k in env for k in keys[:2]):  # token + userid 齊 → 用 env
        return env
    # fallback: 讀檔
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                k = k.strip()
                if k not in env:  # env 變數優先
                    env[k] = v.strip().strip('"').strip("'")
    return env


def fetch_json(url):
    ctx = ssl.create_default_context(cafile=_CA_FILE) if _CA_FILE else ssl.create_default_context()
    with urlopen(url, timeout=60, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_posts(user_id, token, since_ts):
    """分頁抓取所有貼文，直到 timestamp 小於 since_ts"""
    posts = []
    fields = "id,text,timestamp,permalink,shortcode,media_type"
    url = f"{API_BASE}/{user_id}/threads?fields={fields}&limit=25&access_token={token}"
    while url:
        data = fetch_json(url)
        batch = data.get("data", [])
        if not batch:
            break
        # 檢查時間戳，過舊就停
        hit_cutoff = False
        for p in batch:
            ts_str = p.get("timestamp", "")
            if ts_str:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts < since_ts:
                    hit_cutoff = True
                    break
            posts.append(p)
        if hit_cutoff:
            break
        url = data.get("paging", {}).get("next")
    return posts


def fetch_insights(post_id, token):
    """抓單篇 insights：views/likes/replies/reposts/quotes/shares"""
    url = f"{API_BASE}/{post_id}/insights?metric=views,likes,replies,reposts,quotes,shares&access_token={token}"
    try:
        data = fetch_json(url)
        return {m["name"]: m["values"][0]["value"] for m in data.get("data", [])}
    except Exception as e:
        print(f"    ⚠️  insights failed for {post_id}: {e}")
        return {}


def to_apify_format(post, metrics, username):
    """轉成 analyze_by_topic.py 可讀的格式（模仿 Apify 結構）"""
    ts_str = post.get("timestamp", "")
    ts_unix = 0
    if ts_str:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        ts_unix = int(dt.timestamp())
    return {
        "thread": {
            "username": username,
            "url": post.get("permalink", ""),
            "postUrl": post.get("permalink", ""),
            "code": post.get("shortcode", ""),
            "postCode": post.get("shortcode", ""),
            "text": post.get("text", "") or "",
            "captionText": post.get("text", "") or "",
            "like_count": metrics.get("likes", 0),
            "likeCount": metrics.get("likes", 0),
            "reply_count": metrics.get("replies", 0),
            "directReplyCount": metrics.get("replies", 0),
            "repostCount": metrics.get("reposts", 0),
            "reshareCount": metrics.get("shares", 0),
            "published_on": ts_unix,
            "takenAt": ts_unix,
            # 額外官方 metrics（analyze.py 不用，但保留以供 render 顯示）
            "views": metrics.get("views", 0),
            "quotes": metrics.get("quotes", 0),
        },
        "replies": [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    env = load_env()
    user_id = env.get("THREADS_USERID_COSMATE")
    token = env.get("THREADS_TOKEN_COSMATE")
    username = env.get("THREADS_USERNAME_COSMATE", "cosmatedaily")
    if not user_id or not token:
        sys.exit("❌ 缺 THREADS_USERID_COSMATE / THREADS_TOKEN_COSMATE")

    since = datetime.now(tz=timezone.utc) - timedelta(days=args.days)
    print(f"📡 抓 @{username} 近 {args.days} 天貼文（since {since.strftime('%Y-%m-%d')}）")
    posts = fetch_posts(user_id, token, since)
    print(f"  回傳 {len(posts)} 篇")

    # 逐篇抓 insights
    out = []
    for i, p in enumerate(posts, 1):
        metrics = fetch_insights(p["id"], token)
        print(f"  [{i}/{len(posts)}] {p.get('timestamp','')[:10]} · "
              f"views={metrics.get('views','?')} likes={metrics.get('likes','?')}")
        out.append(to_apify_format(p, metrics, username))

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(TZ_TPE).strftime("%Y-%m-%d_%H%M%S")
    out_path = RAW_DIR / f"cosmate_{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ {out_path} ({len(out)} threads)")


if __name__ == "__main__":
    main()
