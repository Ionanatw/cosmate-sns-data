#!/bin/bash
# Threads 多主題貼文爬蟲（口吻訓練用）
# 涵蓋動漫、日常、感情、職場、美食、旅行、追星等主題
# 每個主題獨立跑一次 Apify，避免單次超時
#
# 用法：
#   export APIFY_TOKEN=your_token
#   bash scripts/scrape_multi_topic.sh
#   # 或指定單一主題：
#   bash scripts/scrape_multi_topic.sh anime

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RAW_DIR="$PROJECT_DIR/data/raw"
mkdir -p "$RAW_DIR"

# Apify token
if [ -z "${APIFY_TOKEN:-}" ]; then
  if [ -f "$PROJECT_DIR/.env" ]; then
    source "$PROJECT_DIR/.env"
  fi
fi
if [ -z "${APIFY_TOKEN:-}" ]; then
  echo "ERROR: APIFY_TOKEN not set"
  exit 1
fi

ACTOR="logical_scrapers~threads-post-scraper"
API_URL="https://api.apify.com/v2/acts/${ACTOR}/run-sync-get-dataset-items"
TIMEOUT=300
MAX_POSTS="${MAX_POSTS:-150}"
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)

# ── 主題定義 ──
# 每個主題 = 一組搜尋關鍵字，產出獨立 JSON
declare -A TOPICS

TOPICS[anime]="動漫 anime 咒術迴戰 芙莉蓮 黃泉使者 魔法帽的工作室 鬼滅之刃 進擊的巨人 排球少年 我推的孩子 葬送的芙莉蓮 spy family MAPPA 動畫瘋"
TOPICS[daily]="日常 碎碎念 今天 好累 下班 放假 週末 早安 晚安 失眠 發呆 無聊"
TOPICS[love]="交友軟體 曖昧 暈船 分手 單身 脫單 約會 告白 前任 戀愛"
TOPICS[work]="上班 職場 同事 老闆 加班 面試 離職 薪水 work 社畜 轉職"
TOPICS[food]="美食 好吃 餐廳 咖啡 甜點 火鍋 拉麵 早午餐 foodie 小吃"
TOPICS[travel]="旅行 日本 韓國 東京 大阪 京都 機票 出國 自由行 住宿"
TOPICS[idol]="追星 演唱會 偶像 kpop BTS BLACKPINK 五月天 周杰倫 應援 見面會"
TOPICS[cosplay]="cosplay coser cos服 漫展 同人 漫博 CWT FF 場次 出角"
TOPICS[mood]="焦慮 壓力 崩潰 好煩 不想 心累 emo 低潮 療癒 正能量"
TOPICS[hot]="爆紅 笑死 傻眼 誇張 離譜 好扯 影片 迷因 meme 梗圖"

# 指定單一主題或跑全部
if [ -n "${1:-}" ]; then
  SELECTED_TOPICS=("$1")
else
  SELECTED_TOPICS=(anime daily love work food travel idol cosplay mood hot)
fi

echo "=== Threads 多主題爬蟲（口吻訓練用）==="
echo "Time: $(date)"
echo "Max posts per topic: $MAX_POSTS"
echo "Topics: ${SELECTED_TOPICS[*]}"
echo ""

TOTAL_THREADS=0
TOTAL_REPLIES=0

for TOPIC in "${SELECTED_TOPICS[@]}"; do
  if [ -z "${TOPICS[$TOPIC]:-}" ]; then
    echo "⚠️  Unknown topic: $TOPIC (skipping)"
    continue
  fi

  KEYWORDS="${TOPICS[$TOPIC]}"
  OUTPUT_FILE="$RAW_DIR/${TOPIC}_${TIMESTAMP}.json"

  echo "────────────────────────────────"
  echo "📌 Topic: $TOPIC"
  echo "   Keywords: $KEYWORDS"

  # Build startUrls
  START_URLS=""
  for KEYWORD in $KEYWORDS; do
    ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$KEYWORD'))")
    if [ -n "$START_URLS" ]; then
      START_URLS="$START_URLS,"
    fi
    START_URLS="${START_URLS}{\"url\":\"https://www.threads.com/search?q=${ENCODED}&serp_type=default\"}"
  done

  PAYLOAD="{\"startUrls\":[${START_URLS}],\"maxPosts\":${MAX_POSTS}}"

  HTTP_CODE=$(curl -s -w "%{http_code}" -o "$OUTPUT_FILE" \
    -X POST "${API_URL}?token=${APIFY_TOKEN}&timeout=${TIMEOUT}" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")

  if [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "201" ]; then
    echo "   ❌ HTTP $HTTP_CODE — skipping"
    rm -f "$OUTPUT_FILE"
    continue
  fi

  # Count results
  RESULT=$(python3 -c "
import json
with open('$OUTPUT_FILE') as f:
    data = json.load(f)
if isinstance(data, list):
    threads = len(data)
    replies = sum(len(item.get('replies', [])) for item in data)
    print(f'{threads},{replies}')
else:
    print('0,0')
" 2>/dev/null || echo "0,0")

  T_COUNT=$(echo "$RESULT" | cut -d, -f1)
  R_COUNT=$(echo "$RESULT" | cut -d, -f2)
  TOTAL_THREADS=$((TOTAL_THREADS + T_COUNT))
  TOTAL_REPLIES=$((TOTAL_REPLIES + R_COUNT))

  echo "   ✅ $T_COUNT threads, $R_COUNT replies → $OUTPUT_FILE"
  echo ""
done

echo "════════════════════════════════"
echo "Total: $TOTAL_THREADS threads, $TOTAL_REPLIES replies"
echo ""
echo "Next: python3 scripts/extract_training_corpus.py"
