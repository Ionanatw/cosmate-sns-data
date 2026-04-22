#!/usr/bin/env bash
# 把 Threads/IG/Notion secrets 批次上傳到 GitHub repo
# 用法：bash scripts/upload_secrets.sh

set -euo pipefail

REPO="Ionanatw/threads-dating-app-analysis"
ENV_THREADS="/Users/ionachen/Documents/Claude/project/.env.threads"
ENV_IG="/Users/ionachen/Documents/Claude/project/.env.instagram"

# 要上傳的 key 清單
THREADS_KEYS=(
  THREADS_TOKEN_COSMATE   THREADS_USERID_COSMATE   THREADS_USERNAME_COSMATE
  THREADS_TOKEN_OLIE      THREADS_USERID_OLIE      THREADS_USERNAME_OLIE
  THREADS_TOKEN_DADANA    THREADS_USERID_DADANA    THREADS_USERNAME_DADANA
  THREADS_TOKEN_KIKI      THREADS_USERID_KIKI      THREADS_USERNAME_KIKI
  THREADS_TOKEN_AMY       THREADS_USERID_AMY       THREADS_USERNAME_AMY
  NOTION_TOKEN
  NOTION_THREADS_DB_ID
  NOTION_POSTS_DB_ID
)

IG_KEYS=(
  IG_TOKEN_COSMATE
  IG_USERID_COSMATE
  IG_USERNAME_COSMATE
)

get_env_value() {
  local env_file="$1"
  local key="$2"
  grep -E "^${key}=" "$env_file" | head -1 | cut -d'=' -f2-
}

upload_keys() {
  local env_file="$1"
  shift
  local keys=("$@")

  if [[ ! -f "$env_file" ]]; then
    echo "❌ 找不到 $env_file，跳過"
    return
  fi

  for key in "${keys[@]}"; do
    val=$(get_env_value "$env_file" "$key")
    if [[ -z "$val" ]]; then
      echo "⚠️  $key 不在 $env_file，跳過"
      continue
    fi
    echo -n "  uploading $key ... "
    echo "$val" | gh secret set "$key" --repo "$REPO" --body -
    echo "✅"
  done
}

echo "=== Threads + Notion secrets ($ENV_THREADS) ==="
upload_keys "$ENV_THREADS" "${THREADS_KEYS[@]}"

echo ""
echo "=== Instagram secrets ($ENV_IG) ==="
upload_keys "$ENV_IG" "${IG_KEYS[@]}"

echo ""
echo "全部完成。確認："
gh secret list --repo "$REPO" | grep -E "THREADS_|NOTION_|IG_" | sort
