"""
topics_auto.py — Auto Post 流程的主題定義（issue #8）

跟 scrape_playwright_topics.TOPIC_TARGETS（weekly/daily 流程）刻意分開，
讓 Auto Post 流程能獨立調整關鍵字而不影響市場熱榜報告。

格式遵循 scrape_threads.py --targets 規範：
  "hashtag:xxx" → Threads hashtag 頁
  "keyword:xxx" → Threads 關鍵字搜尋
"""

TOPIC_TARGETS_AUTO = {
    "anime": [
        "hashtag:動漫", "hashtag:漫畫",
        "keyword:動畫瘋", "keyword:新番", "keyword:咒術迴戰", "keyword:芙莉蓮",
        "keyword:黃泉使者", "keyword:MAPPA", "keyword:骨頭社",
        "keyword:公仔開箱",
    ],
    "love": [
        "hashtag:交友軟體", "hashtag:交友APP",
        "keyword:曖昧", "keyword:暈船", "keyword:脫單",
        "keyword:約會", "keyword:告白", "keyword:單身", "keyword:戀愛",
    ],
    "beyblade": [
        "hashtag:戰鬥陀螺",
        "keyword:戰鬥陀螺", "keyword:beyblade", "keyword:陀螺老師",
    ],
    "zodiac": [
        "hashtag:星座",
        "keyword:十二星座", "keyword:星座運勢", "keyword:今日運勢",
        "keyword:上升星座", "keyword:月亮星座",
    ],
    "mbti": [
        "hashtag:MBTI",
        "keyword:MBTI", "keyword:INFJ", "keyword:INTJ", "keyword:ENFP",
        "keyword:MBTI 性格",
    ],
}

# (lo_days, hi_days) — lo ≤ age_days < hi
TIME_WINDOWS = {
    "recent_2d":      (0, 2),
    "historical_30d": (2, 30),
}
