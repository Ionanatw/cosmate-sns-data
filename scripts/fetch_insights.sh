#!/bin/bash
# Threads Insights Fetcher
# 用法: ./fetch_insights.sh [天數] [帳號代碼]
# 例如: ./fetch_insights.sh 14 cosmate
#       ./fetch_insights.sh 7 olie
#       ./fetch_insights.sh 3 dadana
#       ./fetch_insights.sh 7 all   ← 全帳號週報

set -euo pipefail

# Fix Python SSL certificate issue (macOS + Python 3.13)
_CERT_FILE=$(python3 -c "import certifi; print(certifi.where())" 2>/dev/null || true)
[ -n "$_CERT_FILE" ] && export SSL_CERT_FILE="$_CERT_FILE"

# 載入 Token（本機有 .env.threads 才 source；GHA 環境由 workflow env: 提供）
_ENV_THREADS="/Users/ionachen/Documents/Claude/project/.env.threads"
[ -f "$_ENV_THREADS" ] && source "$_ENV_THREADS"

DAYS="${1:-14}"
ACCOUNT="${2:-cosmate}"

# 確保 DAYS 是正整數（防止 shell injection 進 Python code block）
if ! [[ "$DAYS" =~ ^[0-9]+$ ]]; then
  echo "❌ DAYS 必須是正整數: $DAYS"
  exit 1
fi

# 解析 --sync-notion flag
SYNC_NOTION=0
for arg in "$@"; do
  [ "$arg" = "--sync-notion" ] && SYNC_NOTION=1
done

# 可擴充帳號清單（後續加帳號只改這裡）
ALL_ACCOUNTS=("cosmate" "olie" "dadana" "kiki" "amy")

# ──────────────────────────────────────────
# 單帳號抓取函式
# 輸入: fetch_single <account> <days> <summary_file|"">
# ──────────────────────────────────────────
fetch_single() {
  local ACCT="$1"
  local DAYS="$2"
  local SUMMARY_FILE="${3:-}"

  # 帳號路由
  local TOKEN USER_ID USERNAME
  case "$ACCT" in
    cosmate)
      TOKEN="${THREADS_TOKEN_COSMATE}"
      USER_ID="${THREADS_USERID_COSMATE}"
      USERNAME="${THREADS_USERNAME_COSMATE}"
      ;;
    olie)
      TOKEN="${THREADS_TOKEN_OLIE}"
      USER_ID="${THREADS_USERID_OLIE}"
      USERNAME="${THREADS_USERNAME_OLIE}"
      ;;
    dadana)
      TOKEN="${THREADS_TOKEN_DADANA}"
      USER_ID="${THREADS_USERID_DADANA}"
      USERNAME="${THREADS_USERNAME_DADANA}"
      ;;
    kiki)
      TOKEN="${THREADS_TOKEN_KIKI}"
      USER_ID="${THREADS_USERID_KIKI}"
      USERNAME="${THREADS_USERNAME_KIKI}"
      ;;
    amy)
      TOKEN="${THREADS_TOKEN_AMY}"
      USER_ID="${THREADS_USERID_AMY}"
      USERNAME="${THREADS_USERNAME_AMY}"
      ;;
    *)
      echo "❌ 未知帳號: $ACCT (可用: cosmate, olie, dadana, kiki, amy, all)"
      return 1
      ;;
  esac

  local SINCE
  SINCE=$(python3 -c "import time; print(int(time.time()) - ${DAYS} * 86400)")
  local TMPDIR="/tmp/threads_insights_${ACCT}_$$"
  mkdir -p "$TMPDIR"

  # Step 1: 抓貼文（含分頁）
  local ALL_POSTS="[]"
  local URL="https://graph.threads.net/v1.0/${USER_ID}/threads?fields=id,text,timestamp,permalink&since=${SINCE}&limit=50&access_token=${TOKEN}"

  for i in $(seq 1 10); do
    local RESULT
    RESULT=$(curl -s "$URL")

    # 檢查 token 是否有效
    if echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); e=d.get('error'); sys.exit(0 if e else 1)" 2>/dev/null; then
      local ERROR_MSG
      ERROR_MSG=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['error']['message'])" 2>/dev/null || echo "未知錯誤")
      echo "⚠️ @${USERNAME} token 過期或無效，跳過（${ERROR_MSG}）"
      rm -rf "$TMPDIR"
      return 1
    fi

    local NEXT
    NEXT=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('paging',{}).get('next',''))" 2>/dev/null || echo "")
    ALL_POSTS=$(python3 -c "
import sys, json
old = json.loads(sys.argv[1])
new = json.loads(sys.argv[2]).get('data', [])
old.extend(new)
print(json.dumps(old))
" "$ALL_POSTS" "$RESULT")

    if [ -z "$NEXT" ]; then break; fi
    URL="$NEXT"
  done

  echo "$ALL_POSTS" > "$TMPDIR/posts.json"

  # Step 2: 逐篇抓 insights
  python3 -c "
import json
posts = json.load(open('$TMPDIR/posts.json'))
for p in posts:
    print(p['id'])
" | while read -r MID; do
    curl -s "https://graph.threads.net/v1.0/${MID}/insights?metric=views,likes,replies,reposts,quotes,shares&access_token=${TOKEN}" > "$TMPDIR/insight_${MID}.json"
  done

  # Step 3: 整合輸出，並將小計寫入 summary_file（若有提供）
  python3 -c "
import json, sys

tmpdir = '$TMPDIR'
username = '$USERNAME'
days = $DAYS
summary_file = '$SUMMARY_FILE'

posts = json.load(open(f'{tmpdir}/posts.json'))

print(f'📊 @{username} 近 {days} 天貼文數據（共 {len(posts)} 篇）')
print('━' * 75)

total_views = 0
total_likes = 0
total_replies = 0

for i, post in enumerate(posts, 1):
    mid = post['id']
    text = (post.get('text','') or '')[:60].replace('\n',' ')
    ts = post.get('timestamp','')[:10]
    link = post.get('permalink','')

    try:
        insights = json.load(open(f'{tmpdir}/insight_{mid}.json'))
        metrics = {m['name']: m['values'][0]['value'] for m in insights.get('data',[])}
    except:
        metrics = {}

    views   = metrics.get('views', '?')
    likes   = metrics.get('likes', '?')
    replies = metrics.get('replies', '?')
    reposts = metrics.get('reposts', '?')
    quotes  = metrics.get('quotes', '?')
    shares  = metrics.get('shares', '?')

    if isinstance(views, int): total_views += views
    if isinstance(likes, int): total_likes += likes
    if isinstance(replies, int): total_replies += replies

    print(f'#{i}  📅 {ts}')
    if len(post.get('text','') or '') > 60:
        print(f'    {text}...')
    else:
        print(f'    {text}')
    print(f'    👁 {views}  ❤️ {likes}  💬 {replies}  🔁 {reposts}  📝 {quotes}  ✈️ {shares}')
    print(f'    🔗 {link}')
    print()

print('━' * 75)
print(f'📈 小計 @{username}：👁 {total_views:,}  ❤️ {total_likes:,}  💬 {total_replies:,}')
print()

# 寫入合計暫存（all 模式用）
if summary_file:
    import os
    try:
        existing = json.load(open(summary_file)) if os.path.exists(summary_file) else {'views':0,'likes':0,'replies':0}
    except:
        existing = {'views':0,'likes':0,'replies':0}
    existing['views'] += total_views
    existing['likes'] += total_likes
    existing['replies'] += total_replies
    json.dump(existing, open(summary_file,'w'))
"

  # Notion 同步（--sync-notion 旗標）
  if [ "$SYNC_NOTION" = "1" ]; then
    echo "  ⬆️  同步到 Notion DB..."
    python3 "$(dirname "$0")/sync_to_notion.py" \
      --tmpdir "$TMPDIR" \
      --account "$ACCT" \
      --token "$NOTION_TOKEN" \
      --db-id "$NOTION_THREADS_DB_ID" \
      --posts-db-id "${NOTION_POSTS_DB_ID:-}"
  fi

  # 清理暫存
  rm -rf "$TMPDIR"
}

# ──────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────
case "$ACCOUNT" in
  all)
    SUMMARY_FILE="/tmp/threads_all_summary_$$.json"
    echo "🌐 全帳號週報 — 近 ${DAYS} 天"
    echo "════════════════════════════════════════════════════════════════════════════"
    echo ""

    _OK=0
    for ACC in "${ALL_ACCOUNTS[@]}"; do
      fetch_single "$ACC" "$DAYS" "$SUMMARY_FILE" && _OK=$((_OK+1)) || true
    done
    if [ "$_OK" -eq 0 ]; then
      echo "❌ 所有帳號 token 均失效，Notion 未更新"
      exit 1
    fi

    # 全帳號合計
    echo "════════════════════════════════════════════════════════════════════════════"
    if [ -f "$SUMMARY_FILE" ]; then
      python3 -c "
import json
d = json.load(open('$SUMMARY_FILE'))
print(f'📈 全帳號合計：👁 {d[\"views\"]:,}  ❤️ {d[\"likes\"]:,}  💬 {d[\"replies\"]:,}')
print('👁=觀看  ❤️=愛心  💬=回覆  🔁=轉發  📝=引用  ✈️=分享')
"
      rm -f "$SUMMARY_FILE"
    fi
    ;;

  cosmate|olie|dadana|kiki|amy)
    fetch_single "$ACCOUNT" "$DAYS" ""
    echo "👁=觀看  ❤️=愛心  💬=回覆  🔁=轉發  📝=引用  ✈️=分享"
    ;;

  *)
    echo "❌ 未知帳號: $ACCOUNT (可用: cosmate, olie, dadana, kiki, all)"
    exit 1
    ;;
esac
