#!/usr/bin/env python3
"""
make_fixtures.py — 產生 smoke test 用的合成 raw fixtures

寫出 data/raw/{topic}_fixture.json（Apify-like 格式，analyze_by_topic.py 直接可吃）。
時間戳取「現在往回推」動態產生，避免固定日期超出 --days 視窗導致全被過濾。
文字為繁體中文且 CJK 佔比夠高，可通過 is_zh_tw 過濾。

用法：python3 tests/make_fixtures.py
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RAW_DIR = REPO / "data" / "raw"
TZ_TPE = timezone(timedelta(hours=8))

TOPIC_TEXTS = {
    "anime": [
        "今天追完芙莉蓮最新一集，結尾的演出真的太動人，後勁好強大家有同感嗎",
        "新番清單整理好了，這季想追的作品多到看不完，推薦留言交流一下",
        "咒術迴戰這話的作畫品質誇張地好，製作組真的拿出全力了",
        "終於把積了半年的漫畫看完，熬夜也值得，劇情鋪陳完全沒有冷場",
        "公仔開箱：等了三個月的限定版終於到貨，塗裝細節比官圖還漂亮",
        "動畫瘋今天更新的那部大家看了嗎，彈幕笑點密度超高",
        "重溫了十年前的經典作品，畫面雖然舊但故事完全不過時",
        "這季黑馬作品討論度好低，可是劇本紮實到我想替它宣傳",
        "漫畫店店員推薦的冷門短篇集意外地好看，短短一冊看完直接淚崩",
        "看完劇場版走出影廳腿是軟的，特效跟配樂都是頂級水準",
        "角色生日應援！入坑五年還是最喜歡這個角色，沒有之一",
        "畫了三週的同人圖終於完稿，第一次嘗試厚塗風格請大家鞭小力一點",
    ],
    "love": [
        "交友軟體聊了兩週的對象今天第一次見面，比照片本人還可愛，整個暈船",
        "曖昧期最痛苦的就是猜來猜去，到底要不要直接告白，大家給點意見",
        "脫單滿一個月的心得：穩定的安全感比心動更重要",
        "約會選餐廳真的是一門學問，氣氛好又不會太貴的口袋名單求分享",
        "單身第三年，朋友都說我標準太高，但我只是不想將就而已",
        "戀愛腦真的要不得，明明對方已讀不回還替他找理由",
        "告白被拒絕了，難過三天之後反而覺得鬆一口氣，至少不用再猜了",
        "遠距離戀愛快兩年，每天睡前通話是我們的儀式感",
        "朋友介紹的相親對象意外聊得來，原來緣分真的會突然出現",
        "分手半年後第一次覺得一個人也很好，把時間還給自己的感覺真棒",
        "曖昧對象突然已讀不回三天，後來才知道他手機掉進水裡，虛驚一場",
        "戀愛中的儀式感不用花大錢，睡前一句晚安就足夠",
    ],
    "cosplay": [
        "CWT 出本命角色的照片終於修完圖，攝影師大大把光影拍得太美",
        "第一次自製道具武器，保麗龍加環氧土做了兩週，成品比想像中還原",
        "FF 場次穿全套鎧甲走了一整天，雙腿已死但收到好多合照邀請好開心",
        "假髮造型卡關三天，瀏海怎麼剪都不對，最後求助前輩一刀解決",
        "委託的 cos 服今天到貨，刺繡細節完全還原原作設定集，值得等三個月",
        "場次遇到同擔的 coser 互相認出本命，當場聊了一小時太快樂",
        "新手請教：室內棚拍跟外景拍攝大家比較推哪一種，預算有限只能選一",
        "妝前妝後對比圖，角色妝真的可以換一張臉，自己都認不出來",
        "ACOSTA 的攝影企劃終於公開成品，雨中場景拍出了原作名場面的氛圍",
        "整理了五年來的 cos 紀錄，從淘寶套裝到全自製，感謝當年沒放棄的自己",
        "道具組好朋友幫我 3D 列印的法杖零件今天組裝完成，重量比預期輕好多",
        "下個場次要出冷門角色，雖然可能沒人認得，但愛就是要勇敢出",
    ],
}


def make_post(topic, idx, text, now):
    dt = now - timedelta(hours=6 * idx + 3)
    likes = [5200, 3100, 1800, 950, 720, 540, 430, 320, 260, 180, 120, 60][idx]
    comments = [410, 95, 230, 18, 60, 45, 12, 80, 25, 9, 30, 4][idx]
    reposts = [88, 40, 12, 5, 0, 22, 0, 3, 7, 0, 1, 0][idx]
    shares = [120, 35, 20, 8, 2, 15, 1, 6, 4, 0, 2, 0][idx]
    return {
        "thread": {
            "username": f"{topic}_user_{idx:02d}",
            "url": f"https://www.threads.net/@{topic}_user_{idx:02d}/post/fixture{idx:04d}",
            "postUrl": f"https://www.threads.net/@{topic}_user_{idx:02d}/post/fixture{idx:04d}",
            "code": f"{topic}fixture{idx:04d}",
            "postCode": f"{topic}fixture{idx:04d}",
            "text": text,
            "captionText": text,
            "like_count": likes,
            "likeCount": likes,
            "reply_count": comments,
            "directReplyCount": comments,
            "repostCount": reposts,
            "reshareCount": shares,
            "published_on": int(dt.timestamp()),
            "takenAt": int(dt.timestamp()),
        },
        "replies": [],
    }


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(TZ_TPE)
    for topic, texts in TOPIC_TEXTS.items():
        items = [make_post(topic, i, t, now) for i, t in enumerate(texts)]
        out = RAW_DIR / f"{topic}_fixture.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"✅ {out.relative_to(REPO)}: {len(items)} 筆")


if __name__ == "__main__":
    main()
