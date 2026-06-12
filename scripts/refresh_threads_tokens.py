#!/usr/bin/env python3
"""refresh_threads_tokens.py — Threads long-lived token 主動 refresh（避免 60 天硬上限）

對 accounts.py:THREADS_ACCOUNTS 裡每個帳號打 th_refresh_token，把新 token 寫進兩個 repo 的 GH secret。

Threads token TTL 60 天，> 24h 後可 refresh，過期則 refresh 失效（這就是 260612 撞到的洞）。
週排程主動跑，token 永遠停在「剛 refresh 完 60 天」狀態。

環境變數：
  THREADS_TOKEN_<KEY>      — 各帳號當前 token（被讀也被刷）
  GH_PAT_SECRETS_WRITE     — fine-grained PAT，Secrets: read/write 對兩個 repo
  DRY_RUN                  — 'true' 只試跑、不真寫 secret

寫入順序：ai-nexus 先，sns-data 後。
中間 fail 的話 sns-data 保留舊 token（仍有效），下週 retry。

輸出：refresh_summary.txt（給 workflow 後續 Telegram 用）；exit 1 if 任一 fail
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from accounts import THREADS_ACCOUNTS  # noqa: E402

REFRESH_URL = "https://graph.threads.net/refresh_access_token"
REPOS = ["Ionanatw/cosmate-ai-nexus", "Ionanatw/cosmate-sns-data"]
SUMMARY_FILE = Path("refresh_summary.txt")
DRY_RUN = os.environ.get("DRY_RUN", "").lower() == "true"


def refresh_token(current_token):
    """Dry-run 不打 API（避免 refresh 把舊 token 失效）；正常模式才真打。"""
    if DRY_RUN:
        return {"access_token": current_token, "expires_in": 60 * 86400, "_dry_run": True}
    url = f"{REFRESH_URL}?{urlencode({'grant_type': 'th_refresh_token', 'access_token': current_token})}"
    with urlopen(url, timeout=15) as resp:
        return json.load(resp)


def set_secret(repo, name, value):
    if DRY_RUN:
        print(f"   [DRY-RUN] gh secret set {name} -R {repo}")
        return True, ""
    pat = os.environ.get("GH_PAT_SECRETS_WRITE", "")
    if not pat:
        return False, "GH_PAT_SECRETS_WRITE 未設定"
    env = os.environ.copy()
    env["GH_TOKEN"] = pat  # 蓋掉 GHA 預設的 GITHUB_TOKEN（無 secrets:write 權限）
    r = subprocess.run(
        ["gh", "secret", "set", name, "-R", repo],
        input=value, text=True, capture_output=True, env=env,
    )
    return r.returncode == 0, r.stderr.strip()


def main():
    print(f"🔄 開始 refresh（DRY_RUN={DRY_RUN}）")
    succeeded, failed = [], []

    for acct in THREADS_ACCOUNTS:
        env_var = f"THREADS_TOKEN_{acct.upper()}"
        current = os.environ.get(env_var)
        if not current:
            failed.append(f"{acct}: 缺 env var {env_var}")
            print(f"❌ {acct}: 缺 {env_var}")
            continue

        try:
            data = refresh_token(current)
            new_token = data.get("access_token")
            expires_in = data.get("expires_in", 0)
            if not new_token:
                failed.append(f"{acct}: refresh API 回應沒 access_token: {data}")
                print(f"❌ {acct}: refresh API 無 token")
                continue

            errors = []
            for repo in REPOS:
                ok, err = set_secret(repo, env_var, new_token)
                if ok:
                    print(f"   ✅ {repo} secret {env_var} 已更新")
                else:
                    errors.append(f"{repo}: {err}")
                    print(f"   ❌ {repo} secret {env_var} 失敗：{err}")
                    break  # 不繼續寫，避免擴大 drift

            if errors:
                failed.append(f"{acct}: " + " | ".join(errors))
            else:
                days = expires_in // 86400 if expires_in else "?"
                succeeded.append(f"{acct}: 新 token ({days} 天)")
                print(f"✅ {acct}: refresh ok，到期 ~{days} 天後")

        except Exception as e:
            failed.append(f"{acct}: {type(e).__name__}: {e}")
            print(f"❌ {acct}: {type(e).__name__}: {e}")

    summary_lines = [
        f"🔄 Threads token refresh{'（DRY-RUN）' if DRY_RUN else ''}",
        f"✅ {len(succeeded)} 成功 / ❌ {len(failed)} 失敗",
        "",
    ]
    if succeeded:
        summary_lines.append("成功:")
        summary_lines.extend(f"  • {s}" for s in succeeded)
    if failed:
        summary_lines.append("")
        summary_lines.append("失敗:")
        summary_lines.extend(f"  • {f}" for f in failed)
    SUMMARY_FILE.write_text("\n".join(summary_lines))
    print(f"\n📝 寫入 {SUMMARY_FILE}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
