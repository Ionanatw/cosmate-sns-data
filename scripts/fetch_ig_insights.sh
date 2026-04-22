#!/bin/bash
# Instagram Insights Fetcher
# 用法: ./fetch_ig_insights.sh [天數] [帳號代碼]
# 例如: ./fetch_ig_insights.sh 14 cosmate
#       ./fetch_ig_insights.sh 7 all   ← 全帳號
#
# 需要在 .env.instagram 設定 IG_TOKEN_xxx / IG_USERID_xxx / IG_USERNAME_xxx

set -euo pipefail

# Fix Python SSL certificate issue (macOS + Python 3.13)
_CERT_FILE=$(python3 -c "import certifi; print(certifi.where())" 2>/dev/null || true)
[ -n "$_CERT_FILE" ] && export SSL_CERT_FILE="$_CERT_FILE"

# 載入 Token（本機有 .env.instagram 才 source；GHA 環境由 workflow env: 提供）
_ENV_IG="/Users/ionachen/Documents/Claude/project/.env.instagram"
[ -f "$_ENV_IG" ] && source "$_ENV_IG"

DAYS="${1:-14}"
ACCOUNT="${2:-cosmate}"

# 解析 --sync-notion flag
SYNC_NOTION=0
for arg in "$@"; do
  [ "$arg" = "--sync-notion" ] && SYNC_NOTION=1
done

# 可擴充帳號清單
ALL_ACCOUNTS=("cosmate")
# 未來加帳號：ALL_ACCOUNTS=("cosmate" "olie" "dadana" "kiki")

# ──────────────────────────────────────────
# 單帳號抓取函式
# ──────────────────────────────────────────
fetch_single() {
  local ACCT="$1"
  local DAYS="$2"
  local SUMMARY_FILE="${3:-}"

  # 帳號路由
  local TOKEN IG_USER_ID USERNAME
  case "$ACCT" in
    cosmate)
      TOKEN="${IG_TOKEN_COSMATE}"
      IG_USER_ID="${IG_USERID_COSMATE}"
      USERNAME="${IG_USERNAME_COSMATE:-cosmatedaily}"
      ;;
    # 未來擴充：
    # olie)
    #   TOKEN="${IG_TOKEN_OLIE}"
    #   IG_USER_ID="${IG_USERID_OLIE}"
    #   USERNAME="${IG_USERNAME_OLIE:-oliehuangmix}"
    #   ;;
    # dadana)
    #   TOKEN="${IG_TOKEN_DADANA}"
    #   IG_USER_ID="${IG_USERID_DADANA}"
    #   USERNAME="${IG_USERNAME_DADANA:-dadana0618}"
    #   ;;
    # kiki)
    #   TOKEN="${IG_TOKEN_KIKI}"
    #   IG_USER_ID="${IG_USERID_KIKI}"
    #   USERNAME="${IG_USERNAME_KIKI:-kikique.224}"
    #   ;;
    *)
      echo "❌ 未知帳號: $ACCT (目前可用: cosmate, all)"
      return 1
      ;;
  esac

  local SINCE
  SINCE=$(python3 -c "from datetime import datetime, timedelta; print((datetime.now() - timedelta(days=${DAYS})).strftime('%Y-%m-%dT00:00:00'))")
  local TMPDIR="/tmp/ig_insights_${ACCT}_$$"
  mkdir -p "$TMPDIR"

  # Step 1: 抓貼文（含分頁）
  local ALL_POSTS="[]"
  local URL="https://graph.facebook.com/v19.0/${IG_USER_ID}/media?fields=id,caption,timestamp,permalink,media_type,like_count,comments_count,media_url,thumbnail_url&limit=50&access_token=${TOKEN}"

  for i in $(seq 1 10); do
    local RESULT
    RESULT=$(curl -s "$URL")

    # 檢查 token 是否有效
    if echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); e=d.get('error'); sys.exit(0 if e else 1)" 2>/dev/null; then
      local ERROR_MSG
      ERROR_MSG=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['error']['message'])" 2>/dev/null || echo "未知錯誤")
      echo "⚠️ @${USERNAME} IG token 過期或無效，跳過（${ERROR_MSG}）"
      rm -rf "$TMPDIR"
      return 0
    fi

    local NEXT
    NEXT=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('paging',{}).get('next',''))" 2>/dev/null || echo "")

    # 過濾日期範圍內的貼文
    ALL_POSTS=$(python3 -c "
import sys, json
from datetime import datetime

since_str = sys.argv[1]
old = json.loads(sys.argv[2])
new_data = json.loads(sys.argv[3]).get('data', [])

since_dt = datetime.fromisoformat(since_str)

for p in new_data:
    ts = p.get('timestamp', '')
    try:
        post_dt = datetime.fromisoformat(ts.replace('+0000', '+00:00').replace('Z', '+00:00'))
        post_naive = post_dt.replace(tzinfo=None)
        if post_naive >= since_dt:
            old.append(p)
    except:
        old.append(p)

print(json.dumps(old))
" "$SINCE" "$ALL_POSTS" "$RESULT")

    if [ -z "$NEXT" ]; then break; fi
    URL="$NEXT"
  done

  echo "$ALL_POSTS" > "$TMPDIR/posts.json"

  local POST_COUNT
  POST_COUNT=$(python3 -c "import json; print(len(json.load(open('$TMPDIR/posts.json'))))")

  # Step 2: 逐篇抓 insights
  # IG insights metrics 依 media_type 不同：
  # IMAGE/CAROUSEL: impressions, reach, saved, shares
  # VIDEO/REEL: impressions, reach, saved, shares, plays, video_views
  python3 -c "
import json
posts = json.load(open('$TMPDIR/posts.json'))
for p in posts:
    mid = p['id']
    mtype = p.get('media_type', 'IMAGE')
    print(f'{mid}|{mtype}')
" | while IFS='|' read -r MID MTYPE; do
    if [ "$MTYPE" = "VIDEO" ] || [ "$MTYPE" = "REEL" ]; then
      METRICS="views,reach,saved,shares,likes,comments,total_interactions,ig_reels_avg_watch_time,ig_reels_video_view_total_time"
    elif [ "$MTYPE" = "CAROUSEL_ALBUM" ]; then
      METRICS="impressions,reach,saved,shares,likes,comments,total_interactions"
    else
      METRICS="impressions,reach,saved,shares,likes,comments,total_interactions"
    fi
    curl -s "https://graph.facebook.com/v19.0/${MID}/insights?metric=${METRICS}&access_token=${TOKEN}" > "$TMPDIR/insight_${MID}.json"
  done

  # Step 3: 整合輸出
  python3 -c "
import json, sys

tmpdir = '$TMPDIR'
username = '$USERNAME'
days = $DAYS
summary_file = '$SUMMARY_FILE'

posts = json.load(open(f'{tmpdir}/posts.json'))

print(f'📸 @{username} IG 近 {days} 天貼文數據（共 {len(posts)} 篇）')
print('━' * 75)

total_views = 0
total_reach = 0
total_likes = 0
total_comments = 0
total_saved = 0
total_shares = 0

for i, post in enumerate(posts, 1):
    mid = post['id']
    caption = (post.get('caption','') or '')[:60].replace('\n',' ')
    ts = post.get('timestamp','')[:10]
    link = post.get('permalink','')
    mtype = post.get('media_type','IMAGE')
    likes = post.get('like_count', 0)
    comments = post.get('comments_count', 0)

    # Load insights
    try:
        insights = json.load(open(f'{tmpdir}/insight_{mid}.json'))
        metrics = {m['name']: m['values'][0]['value'] for m in insights.get('data',[])}
    except:
        metrics = {}

    views       = metrics.get('views', metrics.get('impressions', '?'))
    reach       = metrics.get('reach', '?')
    saved       = metrics.get('saved', '?')
    shares      = metrics.get('shares', '?')

    if isinstance(views, int): total_views += views
    if isinstance(reach, int): total_reach += reach
    total_likes += likes
    total_comments += comments
    if isinstance(saved, int): total_saved += saved
    if isinstance(shares, int): total_shares += shares

    type_icon = {'IMAGE': '🖼', 'VIDEO': '🎬', 'CAROUSEL_ALBUM': '📂', 'REEL': '🎞'}.get(mtype, '📌')

    print(f'#{i}  📅 {ts}  {type_icon} {mtype}')
    if len(post.get('caption','') or '') > 60:
        print(f'    {caption}...')
    else:
        print(f'    {caption}')
    print(f'    👁 {views}  📢 {reach}  ❤️ {likes}  💬 {comments}  🔖 {saved}  ✈️ {shares}')
    print(f'    🔗 {link}')
    print()

print('━' * 75)
print(f'📈 小計 @{username}：👁 {total_views:,}  📢 {total_reach:,}  ❤️ {total_likes:,}  💬 {total_comments:,}  🔖 {total_saved:,}  ✈️ {total_shares:,}')
print()

# 寫入合計暫存（all 模式用）
if summary_file:
    import os
    try:
        existing = json.load(open(summary_file)) if os.path.exists(summary_file) else {}
    except:
        existing = {}
    for k, v in [('views', total_views), ('reach', total_reach),
                 ('likes', total_likes), ('comments', total_comments),
                 ('saved', total_saved), ('shares', total_shares)]:
        existing[k] = existing.get(k, 0) + v
    json.dump(existing, open(summary_file, 'w'))
"

  # Notion 同步
  if [ "$SYNC_NOTION" = "1" ]; then
    echo "  ⬆️  同步到 Notion DB..."
    python3 "$(dirname "$0")/sync_ig_to_notion.py" \
      --tmpdir "$TMPDIR" \
      --account "$ACCT" \
      --token "$NOTION_TOKEN" \
      --db-id "$NOTION_POSTS_DB_ID"
  fi

  # 清理暫存
  rm -rf "$TMPDIR"
}

# ──────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────
# 載入 Notion 設定（本機有 .env.threads 才 source；GHA 環境由 workflow env: 提供）
_ENV_THREADS2="/Users/ionachen/Documents/Claude/project/.env.threads"
[ -f "$_ENV_THREADS2" ] && source "$_ENV_THREADS2"

case "$ACCOUNT" in
  all)
    SUMMARY_FILE="/tmp/ig_all_summary_$$.json"
    echo "🌐 IG 全帳號報告 — 近 ${DAYS} 天"
    echo "════════════════════════════════════════════════════════════════════════════"
    echo ""

    for ACC in "${ALL_ACCOUNTS[@]}"; do
      fetch_single "$ACC" "$DAYS" "$SUMMARY_FILE" || true
    done

    echo "════════════════════════════════════════════════════════════════════════════"
    if [ -f "$SUMMARY_FILE" ]; then
      python3 -c "
import json
d = json.load(open('$SUMMARY_FILE'))
print(f'📈 IG 全帳號合計：👁 {d.get(\"views\",0):,}  📢 {d.get(\"reach\",0):,}  ❤️ {d.get(\"likes\",0):,}  💬 {d.get(\"comments\",0):,}  🔖 {d.get(\"saved\",0):,}  ✈️ {d.get(\"shares\",0):,}')
print('👁=曝光  📢=觸及  ❤️=愛心  💬=留言  🔖=收藏  ✈️=分享  ▶️=播放')
"
      rm -f "$SUMMARY_FILE"
    fi
    ;;

  cosmate)
    fetch_single "$ACCOUNT" "$DAYS" ""
    echo "👁=曝光  📢=觸及  ❤️=愛心  💬=留言  🔖=收藏  ✈️=分享  ▶️=播放"
    ;;

  *)
    echo "❌ 未知帳號: $ACCOUNT (目前可用: cosmate, all)"
    exit 1
    ;;
esac
