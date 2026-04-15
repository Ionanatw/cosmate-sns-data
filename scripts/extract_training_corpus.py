#!/usr/bin/env python3
"""
Threads 口吻訓練語料萃取器
讀取 data/raw/ 所有 JSON，萃取純文字，分主題輸出

輸出格式：
  - data/corpus/all.jsonl          全部語料（JSONL，每行一則）
  - data/corpus/by_topic/          按主題分類
  - data/corpus/high_engagement.jsonl  高互動語料（P75 以上）
  - data/corpus/stats.txt          統計摘要

用法：
  python3 scripts/extract_training_corpus.py
  python3 scripts/extract_training_corpus.py --min-likes 50 --min-length 10
"""

import json, os, re, argparse, statistics
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter

PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
CORPUS_DIR = PROJECT_DIR / "data" / "corpus"
TOPIC_DIR = CORPUS_DIR / "by_topic"

TZ_TPE = timezone(timedelta(hours=8))


def detect_language(text):
    """粗略判斷語言"""
    cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    cantonese_markers = ['咁', '嘅', '喺', '唔', '嗎', '㗎', '嘢', '冇', '佢', '嗰', '攰', '揀']
    cant_count = sum(1 for m in cantonese_markers if m in text)

    if cant_count >= 2:
        return 'cantonese'
    elif cjk > len(text) * 0.2:
        return 'mandarin'
    elif re.search(r'[a-zA-Z]{3,}', text):
        return 'english'
    return 'mixed'


def detect_topic_from_filename(filename):
    """從檔名推斷主題"""
    name = filename.lower().replace('.json', '')
    known_topics = ['anime', 'daily', 'love', 'work', 'food', 'travel',
                    'idol', 'cosplay', 'mood', 'hot', 'apify']
    for topic in known_topics:
        if topic in name:
            return topic if topic != 'apify' else 'dating'
    return 'unknown'


def classify_tone(text):
    """分類口吻風格"""
    tones = []

    # 碎碎念（短句、日常感）
    if len(text) < 80 and not text.startswith('【'):
        tones.append('碎碎念')

    # 吐槽/抱怨
    complaint_words = ['好煩', '煩死', '有夠', '傻眼', '離譜', '笑死', '媽蛋',
                       '崩潰', '好累', '好攰', '搞唔掂', '好扯']
    if any(w in text for w in complaint_words):
        tones.append('吐槽')

    # 推坑/推薦
    recommend_words = ['一定要看', '推薦', '好看', '必看', '漏掉就虧', '拜託',
                       '超好吃', '超推', '太神']
    if any(w in text for w in recommend_words):
        tones.append('推坑')

    # 驚呼/發現
    if text.count('！') >= 3 or text.count('!') >= 3:
        tones.append('驚呼')

    # 感性/心情
    emo_words = ['寂寞', '空虛', '心累', '低潮', '焦慮', '失落', 'emo',
                 '眼淚', '好想', '好難過']
    if any(w in text for w in emo_words):
        tones.append('感性')

    # 資訊分享
    if text.startswith('【') or '分享' in text or '消息' in text:
        tones.append('資訊')

    # 故事/經歷
    story_words = ['今年', '之前', '前陣子', '昨天', '剛剛', '最近', '上次',
                   '結果', '後來', '才發現']
    if any(w in text for w in story_words) and len(text) > 60:
        tones.append('故事')

    # 疑問/求助
    if text.count('？') >= 2 or text.count('?') >= 2:
        tones.append('疑問')

    if not tones:
        tones.append('一般')

    return tones


def load_all_posts():
    """讀取所有 raw JSON"""
    posts = []
    seen_texts = set()

    for fpath in sorted(RAW_DIR.glob("*.json")):
        topic = detect_topic_from_filename(fpath.name)

        with open(fpath, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue

        if not isinstance(data, list):
            continue

        for item in data:
            thread = item.get("thread", item)
            _add(thread, posts, seen_texts, topic, "thread")
            for reply in item.get("replies", []):
                _add(reply, posts, seen_texts, topic, "reply")

    return posts


def _add(raw, posts, seen_texts, topic, post_type):
    """解析單則貼文"""
    text = raw.get("text") or raw.get("captionText") or raw.get("caption", "")
    if not text or len(text.strip()) < 6:
        return

    text = text.strip()

    # 去重（用前 50 字元 + 長度）
    dedup_key = text[:50] + str(len(text))
    if dedup_key in seen_texts:
        return
    seen_texts.add(dedup_key)

    likes = int(raw.get("like_count") or raw.get("likeCount") or 0)
    comments = int(raw.get("reply_count") or raw.get("directReplyCount") or 0)
    username = raw.get("username", "")

    ts = raw.get("published_on") or raw.get("takenAt", 0)
    dt = datetime.fromtimestamp(ts, tz=TZ_TPE).isoformat() if ts else None

    posts.append({
        "text": text,
        "author": username,
        "likes": likes,
        "comments": comments,
        "topic": topic,
        "post_type": post_type,
        "language": detect_language(text),
        "tones": classify_tone(text),
        "char_count": len(text),
        "datetime": dt,
    })


def save_jsonl(posts, filepath):
    """存成 JSONL"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for p in posts:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")


def save_plain_text(posts, filepath):
    """存成純文字（每則用分隔線隔開），適合直接餵入 prompt"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for p in posts:
            f.write(p["text"] + "\n")
            f.write("---\n")


def main():
    parser = argparse.ArgumentParser(description="Threads 口吻訓練語料萃取器")
    parser.add_argument("--min-likes", type=int, default=0, help="最低愛心數過濾")
    parser.add_argument("--min-length", type=int, default=10, help="最短字數過濾")
    parser.add_argument("--exclude-english", action="store_true", help="排除英文貼文")
    args = parser.parse_args()

    print("=== Threads 口吻訓練語料萃取器 ===")
    print(f"讀取 {RAW_DIR} ...")

    posts = load_all_posts()
    print(f"  原始貼文: {len(posts)} 則")

    # 過濾
    if args.min_likes > 0:
        posts = [p for p in posts if p["likes"] >= args.min_likes]
        print(f"  愛心 ≥ {args.min_likes}: {len(posts)} 則")

    if args.min_length > 0:
        posts = [p for p in posts if p["char_count"] >= args.min_length]
        print(f"  字數 ≥ {args.min_length}: {len(posts)} 則")

    if args.exclude_english:
        posts = [p for p in posts if p["language"] != "english"]
        print(f"  排除英文: {len(posts)} 則")

    if not posts:
        print("ERROR: 沒有符合條件的貼文")
        return

    # 排序
    posts.sort(key=lambda x: x["likes"], reverse=True)

    # ── 輸出 ──

    # 1. 全部語料 JSONL
    save_jsonl(posts, CORPUS_DIR / "all.jsonl")
    print(f"\n  ✅ {CORPUS_DIR / 'all.jsonl'} ({len(posts)} 則)")

    # 2. 純文字版（方便直接貼進 prompt）
    save_plain_text(posts, CORPUS_DIR / "all_text.txt")
    print(f"  ✅ {CORPUS_DIR / 'all_text.txt'}")

    # 3. 高互動語料（P75 以上）
    likes_list = [p["likes"] for p in posts]
    p75 = sorted(likes_list)[int(len(likes_list) * 0.75)] if likes_list else 0
    high_eng = [p for p in posts if p["likes"] >= max(p75, 1)]
    save_jsonl(high_eng, CORPUS_DIR / "high_engagement.jsonl")
    save_plain_text(high_eng, CORPUS_DIR / "high_engagement_text.txt")
    print(f"  ✅ {CORPUS_DIR / 'high_engagement.jsonl'} ({len(high_eng)} 則, likes ≥ {p75})")

    # 4. 按主題分類
    TOPIC_DIR.mkdir(parents=True, exist_ok=True)
    topics = set(p["topic"] for p in posts)
    for topic in sorted(topics):
        topic_posts = [p for p in posts if p["topic"] == topic]
        save_jsonl(topic_posts, TOPIC_DIR / f"{topic}.jsonl")
        save_plain_text(topic_posts, TOPIC_DIR / f"{topic}_text.txt")
        print(f"  ✅ by_topic/{topic}.jsonl ({len(topic_posts)} 則)")

    # 5. 按口吻分類
    tone_dir = CORPUS_DIR / "by_tone"
    tone_dir.mkdir(parents=True, exist_ok=True)
    all_tones = set()
    for p in posts:
        all_tones.update(p["tones"])
    for tone in sorted(all_tones):
        tone_posts = [p for p in posts if tone in p["tones"]]
        save_jsonl(tone_posts, tone_dir / f"{tone}.jsonl")
        save_plain_text(tone_posts, tone_dir / f"{tone}_text.txt")
        print(f"  ✅ by_tone/{tone}.jsonl ({len(tone_posts)} 則)")

    # 6. 統計摘要
    stats_lines = []
    stats_lines.append(f"Threads 口吻訓練語料統計")
    stats_lines.append(f"萃取時間: {datetime.now(TZ_TPE).strftime('%Y-%m-%d %H:%M')} GMT+8")
    stats_lines.append(f"")
    stats_lines.append(f"總則數: {len(posts)}")
    stats_lines.append(f"高互動 (P75+): {len(high_eng)}")
    stats_lines.append(f"P75 門檻: {p75} likes")
    stats_lines.append(f"")

    stats_lines.append(f"── 主題分佈 ──")
    for topic in sorted(topics):
        count = sum(1 for p in posts if p["topic"] == topic)
        stats_lines.append(f"  {topic}: {count}")

    stats_lines.append(f"")
    stats_lines.append(f"── 語言分佈 ──")
    lang_counts = Counter(p["language"] for p in posts)
    for lang, count in lang_counts.most_common():
        stats_lines.append(f"  {lang}: {count}")

    stats_lines.append(f"")
    stats_lines.append(f"── 口吻分佈 ──")
    tone_counts = Counter()
    for p in posts:
        tone_counts.update(p["tones"])
    for tone, count in tone_counts.most_common():
        stats_lines.append(f"  {tone}: {count}")

    stats_lines.append(f"")
    stats_lines.append(f"── 貼文類型 ──")
    type_counts = Counter(p["post_type"] for p in posts)
    for t, count in type_counts.most_common():
        stats_lines.append(f"  {t}: {count}")

    stats_lines.append(f"")
    stats_lines.append(f"── 字數分佈 ──")
    char_counts = [p["char_count"] for p in posts]
    if char_counts:
        stats_lines.append(f"  最短: {min(char_counts)}")
        stats_lines.append(f"  最長: {max(char_counts)}")
        stats_lines.append(f"  中位數: {statistics.median(char_counts):.0f}")
        stats_lines.append(f"  平均: {statistics.mean(char_counts):.0f}")

    stats_text = "\n".join(stats_lines)
    with open(CORPUS_DIR / "stats.txt", "w", encoding="utf-8") as f:
        f.write(stats_text)
    print(f"\n{stats_text}")


if __name__ == "__main__":
    main()
