#!/bin/bash
# 部署報告到 Cloudflare Pages
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== 部署到 Cloudflare Pages ==="
# 強制 ASCII commit message，避免 Cloudflare Pages 對 UTF-8 敏感誤判
DEPLOY_MSG="Deploy $(date -u +%Y-%m-%dT%H:%M:%SZ)"
npx wrangler pages deploy "$PROJECT_DIR" \
  --project-name threads-analytics-report \
  --commit-dirty=true \
  --commit-message "$DEPLOY_MSG"

echo ""
echo "Live: https://threads-analytics-report.pages.dev"
