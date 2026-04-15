#!/bin/bash
# Threads 週一熱榜 — 一鍵跑完整流程
# 支援呼叫別名：threads-weekly / monday-threads-report / 週一熱榜
#
# 用法：
#   bash scripts/weekly.sh              # 爬 + 分析 + 出 HTML（不部署）
#   bash scripts/weekly.sh deploy       # 爬 + 分析 + 出 HTML + 部署
#   bash scripts/weekly.sh skip-scrape  # 不重抓，只重新分析 + 出 HTML

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

MODE="${1:-build}"

echo "════════════════════════════════════════"
echo "  Threads 週一熱榜 — $(date '+%Y-%m-%d %H:%M')"
echo "  動漫 × 交友 × Cosplay"
echo "════════════════════════════════════════"

# Step 1: 爬資料（除非 skip-scrape）
if [ "$MODE" != "skip-scrape" ]; then
  if [ -z "${APIFY_TOKEN:-}" ] && [ -f ".env" ]; then
    export $(grep APIFY_TOKEN .env | xargs)
  fi
  if [ -z "${APIFY_TOKEN:-}" ]; then
    echo "❌ APIFY_TOKEN not set (需要 .env 或 export)"
    exit 1
  fi

  echo ""
  echo "▶ Step 1a/3: 爬取三主題市場熱榜（anime + love + cosplay）"
  python3 scripts/scrape_multi_topic.py anime love cosplay --timeout 450

  echo ""
  echo "▶ Step 1b/3: 抓取 @cosmatedaily 官方 insights（近 30 天）"
  python3 scripts/scrape_cosmate.py --days 30
fi

# Step 2: 分析（近 30 天為主，近 7 天為進階）
echo ""
echo "▶ Step 2/3: 分析（近 30 天 + 近 7 天）"
python3 scripts/analyze_by_topic.py --all --days 30

# Step 3: 產 HTML（主頁 + 本週 archive + archive 列表）
echo ""
echo "▶ Step 3/3: 產出四 tab HTML + archive"
python3 scripts/render_index.py
python3 scripts/render_archive_index.py

# Optional: 部署（僅本機；CI 環境交給 wrangler-action）
if [ "$MODE" = "deploy" ]; then
  if [ -n "${CI:-}" ] || [ -n "${GITHUB_ACTIONS:-}" ]; then
    echo ""
    echo "ℹ️  偵測到 CI 環境，部署由 GitHub Actions 的 wrangler-action 接手"
  else
    echo ""
    echo "▶ 部署到 Cloudflare Pages"
    bash scripts/deploy.sh
  fi
fi

echo ""
echo "✅ 完成 — 開啟 index.html 預覽"
echo "   部署請執行：bash scripts/weekly.sh deploy"
