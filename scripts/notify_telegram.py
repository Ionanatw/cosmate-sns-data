#!/usr/bin/env python3
"""
notify_telegram.py — 發 Telegram 通知（stdlib only）

用法：python3 scripts/notify_telegram.py "訊息文字"

環境變數：TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
未設定時印提示後 exit 0（本機跑 pipeline 不該因為沒通知設定而中斷）；
發送失敗也 exit 0 — 通知是輔助，不能反過來弄死 pipeline。
"""
import json
import os
import sys
import urllib.error
import urllib.request


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("用法：python3 notify_telegram.py \"訊息文字\"", file=sys.stderr)
        sys.exit(0)
    message = sys.argv[1]

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("ℹ️  未設定 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID，略過 Telegram 通知")
        sys.exit(0)

    payload = json.dumps({"chat_id": chat_id, "text": message}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            ok = json.load(resp).get("ok")
            print("✅ Telegram 通知已送出" if ok else "⚠️ Telegram 回應非 ok")
    except (urllib.error.URLError, OSError) as e:
        print(f"⚠️ Telegram 通知失敗（不影響 pipeline）：{e}", file=sys.stderr)


if __name__ == "__main__":
    main()
