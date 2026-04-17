#!/usr/bin/env python3
"""
Threads 單一主題分析器 — anime / love / cosplay 各自獨立統計

不做 keyword re-filter，純粹按 raw 檔名前綴判斷主題（信任 scrape_multi_topic.py 的分類）。
輸出 data/per_topic/{topic}.json，給 index.html 三 tab 版面內嵌使用。

用法：
  python3 scripts/analyze_by_topic.py --topic anime
  python3 scripts/analyze_by_topic.py --topic love
  python3 scripts/analyze_by_topic.py --topic cosplay
  python3 scripts/analyze_by_topic.py --all          # 跑全部三個
"""

import json, argparse, re
from pathlib import Path
from datetime import datetime, timedelta

# 重用 analyze.py 的純函式
from analyze import (
    _add_post, classify_posts, time_analysis,
    RAW_DIR, TZ_TPE, TYPE_INFO,
)

PROJECT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_DIR / "data" / "per_topic"

# 主題 → raw 檔名前綴的對應
# anime 同時吃 anime_ 和 anime_hot_（既有兩種 scrape）
TOPIC_FILE_PREFIXES = {
    "anime": ["anime_"],
    "love": ["love_"],
    "cosplay": ["cosplay_"],
    "cosmate": ["cosmate_"],
}

# 主題 → 語言過濾（zh-tw = 只留繁體中文為主的貼文）
TOPIC_LANG_FILTER = {
    "anime": "zh-tw",
    "love": "zh-tw",
    "cosplay": "zh-tw",
}

# 簡體獨有字（繁體不會出現），命中即視為簡中
SIMPLIFIED_ONLY = set(
    "们这国发说时间问题还过给从将见长书头东车动电风开关样应当对难条无边觉买习义谁"
    "话间应该没办继续应该实样区让进听给写发现几条业务运营产业数据网络计算机软"
)


def is_zh_tw(text):
    """繁中啟發式：CJK 佔比 >= 30% 且不含簡體獨有字"""
    if not text:
        return False
    cjk = re.findall(r'[\u4e00-\u9fff]', text)
    stripped = re.sub(r'\s', '', text)
    if not stripped:
        return False
    cjk_ratio = len(cjk) / len(stripped)
    if cjk_ratio < 0.3 or len(cjk) < 8:
        return False
    if any(c in SIMPLIFIED_ONLY for c in text):
        return False
    return True


def load_topic_posts(topic):
    """讀取單一主題的 raw 檔案，產出統一格式的 posts list（去重）"""
    prefixes = TOPIC_FILE_PREFIXES[topic]
    posts = []
    seen = set()
    files_used = []

    for fpath in sorted(RAW_DIR.glob("*.json")):
        if not any(fpath.name.startswith(p) for p in prefixes):
            continue
        try:
            data = json.load(open(fpath, encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  SKIP (invalid JSON): {fpath.name}")
            continue
        if not isinstance(data, list):
            continue

        files_used.append(fpath.name)
        for item in data:
            thread = item.get("thread", item)
            _add_post(thread, posts, seen, fpath.name)
            for reply in item.get("replies", []):
                _add_post(reply, posts, seen, fpath.name)

    return posts, files_used


def post_to_dict(p):
    """把 post dict 轉成 JSON 可序列化格式（datetime → ISO 字串）"""
    return {
        "author": p["author"],
        "url": p["url"],
        "text": p["text"],
        "likes": p["likes"],
        "comments": p["comments"],
        "reposts": p["reposts"],
        "shares": p["shares"],
        "total_engagement": p["total_engagement"],
        "primary_type": p["primary_type"],
        "types": p["types"],
        "comment_rate": round(p["comment_rate"], 2),
        "share_rate": round(p["share_rate"], 2),
        "dt": p["dt"].isoformat() if p["dt"] else None,
        "hour": p["hour"],
        "weekday": p["weekday"],
        "source": p["source"],
    }


def filter_by_days(posts, days):
    """保留近 N 天內且有時間戳的貼文"""
    cutoff = datetime.now(TZ_TPE) - timedelta(days=days)
    return [p for p in posts if p["dt"] and p["dt"] >= cutoff]


def analyze_topic(topic, days=30):
    """跑單一主題分析，回傳結構化 dict"""
    print(f"\n── 主題: {topic} ──")
    all_posts, files_used = load_topic_posts(topic)
    print(f"  讀取檔案: {files_used}")
    print(f"  載入貼文 (原始): {len(all_posts)} 篇")

    # 語言過濾（cosplay 只留繁中）
    lang_filter = TOPIC_LANG_FILTER.get(topic)
    if lang_filter == "zh-tw":
        before = len(all_posts)
        all_posts = [p for p in all_posts if is_zh_tw(p["text"])]
        print(f"  zh-tw 過濾: {before} → {len(all_posts)} 篇")

    # 主報告：近 N 天（預設 30）
    posts = filter_by_days(all_posts, days)
    print(f"  近 {days} 天: {len(posts)} 篇")

    # 進階區塊：近 7 天
    posts_7d = filter_by_days(all_posts, 7)
    print(f"  近 7 天: {len(posts_7d)} 篇")

    if not posts:
        print(f"  ⚠️  {topic} 近 {days} 天無資料")
        return None

    posts, thresholds, percentiles = classify_posts(posts)
    hourly, daily = time_analysis(posts)

    # 近 7 天 top（獨立跑分類，不影響主表格）
    if posts_7d:
        posts_7d, _, _ = classify_posts(posts_7d)
        top_7d = sorted(posts_7d, key=lambda x: x["total_engagement"], reverse=True)[:10]
    else:
        top_7d = []

    # Date range
    dates = [p["dt"] for p in posts if p["dt"]]
    date_range = {
        "from": min(dates).isoformat() if dates else None,
        "to": max(dates).isoformat() if dates else None,
    }

    # Top posts by total_engagement (前 30 名)
    top_posts = sorted(posts, key=lambda x: x["total_engagement"], reverse=True)[:30]

    # 各 type 排行（每 type 前 10）
    by_type = {}
    for t in ["A", "B", "C", "D", "E", "X"]:
        type_posts = sorted(
            [p for p in posts if t in p["types"]],
            key=lambda x: x["total_engagement"],
            reverse=True,
        )[:10]
        by_type[t] = [post_to_dict(p) for p in type_posts]

    type_counts = {t: sum(1 for p in posts if t in p["types"]) for t in ["A", "B", "C", "D", "E", "X"]}

    result = {
        "topic": topic,
        "days_window": days,
        "total_posts": len(posts),
        "total_posts_7d": len(posts_7d),
        "files_used": files_used,
        "date_range": date_range,
        "thresholds": {k: round(v, 2) for k, v in thresholds.items()},
        "percentiles": {
            m: {p: round(v, 2) for p, v in vals.items()}
            for m, vals in percentiles.items()
        },
        "type_counts": type_counts,
        "type_info": TYPE_INFO,
        "hourly": {str(h): {"count": d["count"], "avg_engagement": round(d["avg_engagement"], 1)}
                   for h, d in hourly.items()},
        "daily": {d: {"count": v["count"], "avg_engagement": round(v["avg_engagement"], 1)}
                  for d, v in daily.items()},
        "top_posts": [post_to_dict(p) for p in top_posts],
        "top_posts_7d": [post_to_dict(p) for p in top_7d],
        "by_type": by_type,
    }

    print(f"  分類分布: {type_counts}")
    print(f"  Top 1: @{top_posts[0]['author']} | {top_posts[0]['total_engagement']:,} 互動")
    return result


def save_result(topic, result):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{topic}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  → {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", choices=list(TOPIC_FILE_PREFIXES.keys()))
    parser.add_argument("--all", action="store_true", help="跑全部三個主題")
    parser.add_argument("--days", type=int, default=30, help="主報告時間窗（預設 30 天）")
    args = parser.parse_args()

    if not args.topic and not args.all:
        parser.error("需指定 --topic 或 --all")

    targets = list(TOPIC_FILE_PREFIXES.keys()) if args.all else [args.topic]

    for topic in targets:
        result = analyze_topic(topic, days=args.days)
        if result:
            save_result(topic, result)

    print("\n✅ 完成")


if __name__ == "__main__":
    main()
