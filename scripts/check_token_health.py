#!/usr/bin/env python3
"""Check health of all Threads and Instagram API tokens. Exits 1 if any token fails."""

import os
import sys
import requests

THREADS_ACCOUNTS = ["cosmate", "olie", "dadana", "kiki", "amy"]
IG_ACCOUNTS = ["cosmate"]

failed = []
ok = []


def check_threads_token(account):
    token = os.environ.get(f"THREADS_TOKEN_{account.upper()}")
    if not token:
        failed.append(f"Threads:{account} [missing env var]")
        return
    try:
        r = requests.get(
            "https://graph.threads.net/v1.0/me",
            params={"fields": "id,username", "access_token": token},
            timeout=10,
        )
        if r.status_code == 200:
            username = r.json().get("username", "?")
            ok.append(f"Threads:{account} (@{username})")
        else:
            error = r.json().get("error", {}).get("message", r.text[:100])
            failed.append(f"Threads:{account} [{r.status_code}] {error}")
    except Exception as e:
        failed.append(f"Threads:{account} [exception] {e}")


def check_ig_token(account):
    token = os.environ.get(f"IG_TOKEN_{account.upper()}")
    if not token:
        failed.append(f"IG:{account} [missing env var]")
        return
    try:
        r = requests.get(
            "https://graph.facebook.com/v19.0/me",
            params={"fields": "id,username", "access_token": token},
            timeout=10,
        )
        if r.status_code == 200:
            username = r.json().get("username", "?")
            ok.append(f"IG:{account} (@{username})")
        else:
            error = r.json().get("error", {}).get("message", r.text[:100])
            failed.append(f"IG:{account} [{r.status_code}] {error}")
    except Exception as e:
        failed.append(f"IG:{account} [exception] {e}")


for account in THREADS_ACCOUNTS:
    check_threads_token(account)

for account in IG_ACCOUNTS:
    check_ig_token(account)

if ok:
    print("✅ 正常：")
    for item in ok:
        print(f"   {item}")

if failed:
    print("\n❌ 失敗：")
    for item in failed:
        print(f"   {item}")
    print(f"\n{len(failed)} 個 token 失效，請盡快更新。")
    sys.exit(1)
else:
    print(f"\n全部 {len(ok)} 個 token 正常。")
