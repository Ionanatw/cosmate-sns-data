#!/usr/bin/env python3
"""
對每個主題的 top_posts 跑一次 Claude 分析，產出洞察文字（公式、操作要點、隱藏發現）。
輸出注入 data/per_topic/{topic}.json 的 ai_insight 欄位，讓 render_index.py 讀取。

用法：
  python3 scripts/ai_analyze.py              # 全部四主題
  python3 scripts/ai_analyze.py anime love   # 指定主題

環境變數：
  ANTHROPIC_API_KEY（從 .env 讀，或 export 設定）
"""
import json, sys, os, ssl, urllib.request
from pathlib import Path

try:
    import certifi
    _CA_FILE = certifi.where()
except ImportError:
    _CA_FILE = None

PROJECT_DIR = Path(__file__).resolve().parent.parent
PER_TOPIC_DIR = PROJECT_DIR / "data" / "per_topic"
MODEL = "claude-sonnet-4-5-20250929"  # 性價比好、速度快
API_URL = "https://api.anthropic.com/v1/messages"

TOPIC_CTX = {
    "anime": "動漫貼文（咒術迴戰、芙莉蓮、鬼滅等番）",
    "love": "交友 / 戀愛貼文（交友軟體、曖昧、脫單等）",
    "cosplay": "Cosplay 圈貼文（coser、漫展 CWT FF ACOSTA 等）",
    "cosmate": "@cosmatedaily 官方帳號自家貼文（Cosmate App 相關）",
}


def load_env():
    """優先 env var，fallback .env 檔"""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    env_file = PROJECT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY"):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                return v
    return None


def build_prompt(topic, data):
    """把主題 + top posts 組成分析 prompt"""
    top_posts = data.get("top_posts", [])[:15]
    posts_text = "\n".join(
        f"- @{p['author']} | ❤️{p['likes']} 💬{p['comments']} 🔁{p['reposts']} ✈️{p['shares']} | Type {p['primary_type']}"
        f" | 留言率 {p['comment_rate']:.1f}% | {p['text'][:100].replace(chr(10),' ')}"
        for p in top_posts
    )
    type_counts = data.get("type_counts", {})
    thresholds = data.get("thresholds", {})

    ctx = TOPIC_CTX.get(topic, topic)

    return f"""你是 Threads 社群分析師。下面是「{ctx}」近 30 天 Top 15 貼文：

{posts_text}

分類分布（依百分位門檻）：A={type_counts.get('A',0)} B={type_counts.get('B',0)} C={type_counts.get('C',0)} D={type_counts.get('D',0)} E={type_counts.get('E',0)} X={type_counts.get('X',0)}
P90 門檻：❤️≥{thresholds.get('likes_p90',0):.0f} 💬≥{thresholds.get('comments_p90',0):.0f}

Type 意義：
- A 全能爆款（各指標 P90+）
- B 私域擴散（轉發/分享高，內容被私傳）
- C 戰場議論（留言率高，觸發討論）
- D 靜默共鳴（按讚多但不留言）
- E 穩定互動（平均水準）
- X 長尾低互動

請產出 JSON 格式分析（**直接回 JSON，不要 markdown 包裝**）：

{{
  "headline": "一句話總結本週此主題的關鍵現象（≤30 字）",
  "patterns": [
    {{
      "name": "公式命名（≤10字，例：情緒療癒型）",
      "trigger_type": "Type B/C/D",
      "desc": "30-50 字說明這類貼文的共同特徵",
      "examples": [
        {{"author": "@xxx", "text": "貼文片段（≤40字）", "metric": "關鍵數字（例：🔁1576 / CR 167%）"}},
        {{"author": "@yyy", "text": "...", "metric": "..."}}
      ],
      "actionable": "操作要點（≤60字，如何模仿這類內容）"
    }}
  ],
  "hidden_finding": "一段 40-80 字的隱藏洞察（跨貼文的共同 pattern，非顯而易見）"
}}

要求：
1. 3 個 patterns，聚焦前三種出現頻率最高的 Type（排除 X）
2. examples 從實際 Top 15 抽取，不要編造
3. actionable 要能直接應用（給鴿舍貼文素材）
4. hidden_finding 要「讀了會有 aha moment」
5. 用繁體中文；不含「根據資料」「綜上所述」這類空話
"""


def call_claude(api_key, prompt):
    """呼叫 Claude API，回傳 JSON dict（失敗回 None）"""
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL, data=body, method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    ctx = ssl.create_default_context(cafile=_CA_FILE) if _CA_FILE else ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"    ❌ API 呼叫失敗: {e}")
        return None

    try:
        text = result["content"][0]["text"].strip()
        # 去掉 markdown 包裝（如 ```json ... ```）
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("\n", 1)[0].rstrip("`").rstrip()
            if text.startswith("json"):
                text = text[4:].lstrip()
        return json.loads(text)
    except Exception as e:
        print(f"    ⚠️  解析 AI 回應失敗: {e}")
        print(f"    回應原文: {result}")
        return None


def analyze_topic(topic, api_key):
    path = PER_TOPIC_DIR / f"{topic}.json"
    if not path.exists():
        print(f"  ⚠️  {topic}: 找不到 {path}，跳過")
        return False

    data = json.load(open(path, encoding="utf-8"))
    if not data.get("top_posts"):
        print(f"  ⚠️  {topic}: top_posts 為空，跳過")
        return False

    print(f"  🤖 {topic}: 呼叫 Claude 分析中...")
    prompt = build_prompt(topic, data)
    insight = call_claude(api_key, prompt)
    if not insight:
        return False

    data["ai_insight"] = insight
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"    ✅ {insight.get('headline','(未命名)')[:40]}")
    return True


def main():
    topics = sys.argv[1:] or list(TOPIC_CTX.keys())

    api_key = load_env()
    if not api_key:
        sys.exit("❌ ANTHROPIC_API_KEY 未設定（請檢查 .env 或 export）")

    print(f"=== AI 分析 {len(topics)} 主題 ===")
    ok, fail = 0, 0
    for t in topics:
        if analyze_topic(t, api_key):
            ok += 1
        else:
            fail += 1

    print(f"\n═══ 完成：{ok} 成功 / {fail} 失敗 ═══")
    if fail > 0:
        print("（AI 分析失敗不影響主 pipeline — HTML 會跳過 AI 區塊）")


if __name__ == "__main__":
    main()
