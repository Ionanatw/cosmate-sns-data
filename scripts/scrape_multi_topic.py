#!/usr/bin/env python3
"""
Threads 多主題貼文爬蟲（口吻訓練用）
透過 Apify Threads scraper 爬取多主題貼文

用法：
  python3 scripts/scrape_multi_topic.py                    # 全部主題
  python3 scripts/scrape_multi_topic.py anime cosplay food # 指定主題
  python3 scripts/scrape_multi_topic.py --max-posts 50     # 自訂數量
"""

import json, sys, os, time, argparse
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.parse import quote

PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"

TOPICS = {
    "anime": "動漫 anime 咒術迴戰 芙莉蓮 黃泉使者 魔法帽的工作室 鬼滅之刃 排球少年 我推的孩子 MAPPA 動畫瘋 新番",
    "daily": "日常 碎碎念 今天 好累 下班 放假 週末 早安 晚安 失眠 無聊",
    "love": "交友軟體 曖昧 暈船 分手 單身 脫單 約會 告白 前任 戀愛",
    "work": "上班 職場 同事 老闆 加班 面試 離職 薪水 社畜 轉職",
    "food": "美食 好吃 餐廳 咖啡 甜點 火鍋 拉麵 早午餐 小吃 吃到飽",
    "travel": "旅行 日本 韓國 東京 大阪 京都 機票 出國 自由行",
    "idol": "追星 演唱會 偶像 kpop 五月天 周杰倫 應援 見面會 音樂祭",
    "cosplay": "cosplay coser cos服 漫展 同人 漫博 CWT FF 場次 出角 痛包",
    "mood": "焦慮 壓力 崩潰 好煩 心累 emo 低潮 療癒 正能量 內耗",
    "hot": "爆紅 笑死 傻眼 誇張 離譜 好扯 迷因 meme 梗圖",
}

ACTOR = "logical_scrapers~threads-post-scraper"
API_URL = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items"


def run_scrape(topic, keywords, token, max_posts, timeout):
    """對單一主題跑 Apify 爬蟲"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output_file = RAW_DIR / f"{topic}_{timestamp}.json"

    # Build startUrls
    start_urls = []
    for kw in keywords.split():
        encoded = quote(kw)
        start_urls.append({"url": f"https://www.threads.com/search?q={encoded}&serp_type=default"})

    payload = json.dumps({"startUrls": start_urls, "maxPosts": max_posts}).encode("utf-8")

    url = f"{API_URL}?token={token}&timeout={timeout}"
    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with urlopen(req, timeout=timeout + 30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return 0, 0

    if not isinstance(data, list):
        print(f"  ❌ Unexpected format")
        return 0, 0

    # Save
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    threads = len(data)
    replies = sum(len(item.get("replies", [])) for item in data)
    print(f"  ✅ {threads} threads, {replies} replies → {output_file.name}")
    return threads, replies


def main():
    parser = argparse.ArgumentParser(description="Threads 多主題爬蟲")
    parser.add_argument("topics", nargs="*", help="指定主題（預設全部）")
    parser.add_argument("--max-posts", type=int, default=80, help="每主題最大貼文數")
    parser.add_argument("--timeout", type=int, default=300, help="API timeout (秒)")
    args = parser.parse_args()

    # Token
    token = os.environ.get("APIFY_TOKEN", "")
    if not token:
        env_file = PROJECT_DIR / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("APIFY_TOKEN="):
                    token = line.split("=", 1)[1].strip()
    if not token:
        print("ERROR: APIFY_TOKEN not set")
        sys.exit(1)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    selected = args.topics if args.topics else list(TOPICS.keys())
    print(f"=== Threads 多主題爬蟲（口吻訓練用）===")
    print(f"Topics: {', '.join(selected)}")
    print(f"Max posts per topic: {args.max_posts}")
    print()

    total_t, total_r = 0, 0
    for topic in selected:
        if topic not in TOPICS:
            print(f"⚠️  Unknown topic: {topic}")
            continue
        print(f"📌 {topic}: {TOPICS[topic][:60]}...")
        t, r = run_scrape(topic, TOPICS[topic], token, args.max_posts, args.timeout)
        total_t += t
        total_r += r
        if t > 0:
            time.sleep(2)  # Rate limiting between topics

    print(f"\n═══════════════════")
    print(f"Total: {total_t} threads, {total_r} replies")
    print(f"\nNext: python3 scripts/extract_training_corpus.py --min-length 10 --exclude-english")


if __name__ == "__main__":
    main()
