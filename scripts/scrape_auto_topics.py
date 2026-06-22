#!/usr/bin/env python3
"""
scrape_auto_topics.py — Auto Post 流程的多主題爬蟲（issue #8 PR1）

對每個主題跑 Playwright 爬蟲，按貼文 timestamp 切成「近 2 天」「3-30 天歷史熱門」
兩堆，分別寫到 data/raw/auto/{topic}_{window}_{timestamp}.json。

跟 scrape_playwright_topics.py 的差別：
  - topic 清單來自 scripts/lib/topics_auto.py（多了 beyblade/zodiac/mbti）
  - 輸出按時間窗分檔（recent_2d / historical_30d）
  - 輸出位置 data/raw/auto/（與 weekly/daily 流程隔離）

用法：
  python3 scripts/scrape_auto_topics.py                # 5 個主題全跑
  python3 scripts/scrape_auto_topics.py anime mbti     # 指定主題
  python3 scripts/scrape_auto_topics.py --scroll 16    # 加深爬量挖歷史
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "scripts" / "lib"))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))

from topics_auto import TIME_WINDOWS, TOPIC_TARGETS_AUTO  # noqa: E402
from scrape_playwright_topics import (  # noqa: E402
    _resolve_scrape_threads,
    convert_to_apify_format,
    resolve_cookies_file,
)

RAW_AUTO_DIR = PROJECT_DIR / "data" / "raw" / "auto"
TZ_TPE = timezone(timedelta(hours=8))
SCRAPE_THREADS = _resolve_scrape_threads()


def scrape_topic(topic, cookies_file, scroll):
    """跑底層 scraper，回傳含 timestamp 的原始 posts list（未轉 Apify 格式）"""
    targets = TOPIC_TARGETS_AUTO[topic]
    targets_arg = ",".join(targets)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        tmp_output = tf.name

    cmd = [
        "python3", str(SCRAPE_THREADS),
        "--targets", targets_arg,
        "--output", tmp_output,
        "--scroll", str(scroll),
        "--cookies-file", str(cookies_file),
    ]
    print(f"\n▶ 爬取 {topic}（{len(targets)} 個搜尋目標，scroll={scroll}）")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"  ❌ scrape_threads 失敗（exit {result.returncode}）")
        try:
            os.unlink(tmp_output)
        except OSError:
            pass
        return []

    try:
        data = json.load(open(tmp_output))
    finally:
        os.unlink(tmp_output)
    return data.get("posts", [])


def split_by_window(posts):
    """按 timestamp 把貼文切成 TIME_WINDOWS 中的桶。

    沒有 timestamp 或解析失敗的丟 recent_2d（保守視為新）。
    超過最大窗（30 天）的整個丟掉。
    """
    now = datetime.now(TZ_TPE)
    buckets = {w: [] for w in TIME_WINDOWS}
    for p in posts:
        ts_str = p.get("timestamp", "")
        if not ts_str:
            buckets["recent_2d"].append(p)
            continue
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(TZ_TPE)
        except (ValueError, TypeError):
            buckets["recent_2d"].append(p)
            continue
        age_days = (now - dt).total_seconds() / 86400
        for window, (lo, hi) in TIME_WINDOWS.items():
            if lo <= age_days < hi:
                buckets[window].append(p)
                break
    return buckets


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auto Post 多主題爬蟲（時間窗切桶）")
    parser.add_argument(
        "topics", nargs="*", default=list(TOPIC_TARGETS_AUTO.keys()),
        help="指定主題（預設 5 個全跑）",
    )
    parser.add_argument(
        "--scroll", type=int, default=12,
        help="每搜尋目標捲動次數，越多越能挖到 30 天前的歷史貼文（default 12）",
    )
    args = parser.parse_args()

    unknown = [t for t in args.topics if t not in TOPIC_TARGETS_AUTO]
    if unknown:
        sys.exit(f"❌ 未知主題: {unknown}。可選: {list(TOPIC_TARGETS_AUTO.keys())}")

    if not SCRAPE_THREADS:
        sys.exit("❌ 找不到 scrape_threads.py（vendor copy 或 upstream 都沒命中）")

    cookies_file = resolve_cookies_file()
    if not cookies_file:
        sys.exit(
            "❌ 找不到 cookies file。請先跑：\n"
            f"   python3 {SCRAPE_THREADS} --dump-cookies ~/.cosmate/threads_cookies.json"
        )
    print(f"🍪 cookies: {cookies_file}")
    print(f"📂 output : {RAW_AUTO_DIR}")

    RAW_AUTO_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(TZ_TPE).strftime("%Y-%m-%d_%H%M%S")

    summary = []
    for topic in args.topics:
        posts = scrape_topic(topic, cookies_file, scroll=args.scroll)
        if not posts:
            print(f"  ⚠️  {topic}: 0 筆，跳過")
            continue

        buckets = split_by_window(posts)
        for window, bucket_posts in buckets.items():
            if not bucket_posts:
                print(f"  ⏭  {topic}/{window}: 0 筆")
                continue
            items = convert_to_apify_format(bucket_posts)
            if not items:
                continue
            out_path = RAW_AUTO_DIR / f"{topic}_{window}_{ts}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            print(f"  ✅ {topic}/{window}: {len(items)} 筆 → {out_path.name}")
            summary.append((topic, window, len(items)))

    print("\n═══ 完成 ═══")
    for topic, window, n in summary:
        print(f"  {topic:10} {window:15} {n:>4} 筆")
    print("  " + "─" * 32)
    print(f"  總計 {sum(n for _, _, n in summary):>4} 筆")


if __name__ == "__main__":
    main()
