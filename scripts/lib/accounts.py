#!/usr/bin/env python3
"""
accounts.py — 帳號單一註冊表（Single Source of Truth）

全 repo 的帳號清單唯一定義點。新增/移除帳號只改這個檔案：
  - shell 取清單：   python3 scripts/lib/accounts.py --list
  - persona 對照：   from accounts import ACCOUNT_TO_POSTER
  - CI 一致性比對：  python3 scripts/lib/accounts.py --check-workflow <workflow.yml>
    （workflow 的 env/secrets 清單沒辦法動態產生，所以用比對守住：
      漏列任何一個帳號的環境變數，lint job 直接 fail）

歷史教訓（為什麼要有這個檔）：
  - amy → 社畜Amy mapping 漏補（f7d55a6）
  - nadia 上線時 token-health-check.yml 漏加（260612 盤點發現）
  - persona 名稱手打進多個檔案造成空格不一致（不二錯 #022）
"""
import argparse
import sys

# ── 唯一帳號定義點 ─────────────────────────────────────────
# poster = Notion Posts DB「貼文人」multi_select 的 canonical 字面值（一字不差，含空格）
ACCOUNTS = [
    {"key": "cosmate", "poster": "CosMate小編",      "ig": True},
    {"key": "olie",    "poster": "動漫宅Olie.Huang", "ig": False},
    {"key": "dadana",  "poster": "宅人Dadana",       "ig": False},
    {"key": "kiki",    "poster": "交友中的Kiki",     "ig": False},
    {"key": "amy",     "poster": "社畜Amy",          "ig": False},
    {"key": "nadia",   "poster": "交軟專家nadia",    "ig": False},
]

THREADS_ACCOUNTS = [a["key"] for a in ACCOUNTS]
IG_ACCOUNTS = [a["key"] for a in ACCOUNTS if a["ig"]]
ACCOUNT_TO_POSTER = {a["key"]: a["poster"] for a in ACCOUNTS}

_ENV_SUFFIXES = ["TOKEN", "USERID", "USERNAME"]


def required_env_vars(prefixes=None):
    """列出所有帳號需要的環境變數名。

    prefixes: 限定回傳的變數前綴，如 ["THREADS_TOKEN", "IG_TOKEN"]；
              None = 全部（THREADS_* 三件套 + IG_* 三件套）。
    """
    out = []
    for key in THREADS_ACCOUNTS:
        for suffix in _ENV_SUFFIXES:
            out.append(f"THREADS_{suffix}_{key.upper()}")
    for key in IG_ACCOUNTS:
        for suffix in _ENV_SUFFIXES:
            out.append(f"IG_{suffix}_{key.upper()}")
    if prefixes:
        out = [v for v in out if any(v.startswith(p + "_") for p in prefixes)]
    return out


def check_workflow(path, prefixes=None):
    """檢查 workflow 檔是否列齊所有需要的環境變數，回傳缺漏清單。"""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return [v for v in required_env_vars(prefixes) if v not in text]


def main():
    parser = argparse.ArgumentParser(description="帳號單一註冊表")
    parser.add_argument("--list", action="store_true", help="輸出帳號 key（空白分隔，給 shell 用）")
    parser.add_argument("--list-ig", action="store_true", help="輸出 IG 帳號 key")
    parser.add_argument("--required-env", action="store_true", help="列出所有需要的環境變數名")
    parser.add_argument("--check-workflow", metavar="FILE", help="比對 workflow 是否列齊環境變數")
    parser.add_argument("--require", default="", help="限定比對的變數前綴（逗號分隔），如 THREADS_TOKEN,IG_TOKEN")
    args = parser.parse_args()

    prefixes = [p.strip() for p in args.require.split(",") if p.strip()] or None

    if args.list:
        print(" ".join(THREADS_ACCOUNTS))
    elif args.list_ig:
        print(" ".join(IG_ACCOUNTS))
    elif args.required_env:
        print("\n".join(required_env_vars(prefixes)))
    elif args.check_workflow:
        missing = check_workflow(args.check_workflow, prefixes)
        if missing:
            print(f"❌ {args.check_workflow} 缺少環境變數（帳號清單見 scripts/lib/accounts.py）：")
            for v in missing:
                print(f"   - {v}")
            sys.exit(1)
        print(f"✅ {args.check_workflow} 環境變數列齊（{len(required_env_vars(prefixes))} 個）")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
