#!/usr/bin/env python3
"""
validate_notion_schema.py — 開跑前驗證 Notion DB schema 與程式碼引用一致

針對三次歷史踩坑設計的防呆（不二錯 #022 等）：
  1. 欄位名不一致：程式碼引用的欄位在 Notion 不存在，或只差頭尾空白
     （例：「總觀看時間(分) 」Notion 端有尾端空格，程式碼沒寫 → PATCH 400）
  2. multi_select 選項污染：去除空白後相同的重複選項
     （例：「動漫宅Olie.Huang」vs「動漫宅 Olie.Huang」並存 → /gen 失效）
  3. 貼文人選項 vs 帳號註冊表：accounts.py 的 poster 名只差空白 → 視為錯誤

用法（環境變數）：
  NOTION_TOKEN          必填
  NOTION_THREADS_DB_ID  選填，有給才驗 Threads DB
  NOTION_POSTS_DB_ID    選填，有給才驗 Posts DB

  python3 scripts/validate_notion_schema.py            # 驗證，任何錯誤 exit 1
  python3 scripts/validate_notion_schema.py --warn-only  # 只警告不擋（除錯用）

掛載點：metrics-sync.yml 第一步。失敗 → workflow 變紅 → failure-notify 發 Telegram。
僅用 stdlib。
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from accounts import ACCOUNT_TO_POSTER  # noqa: E402（帳號單一註冊表）

# 程式碼實際引用的欄位名（與 sync_to_notion.py / sync_ig_to_notion.py 一字不差）
EXPECTED_THREADS_DB_PROPS = [
    "Post ID", "Account", "Text Preview", "Last Synced", "Post Date", "Permalink",
    "Views", "Likes", "Replies", "Reposts", "Quotes", "Shares",
]
EXPECTED_POSTS_DB_PROPS = [
    "Headline", "Platform", "Format", "Status", "來源", "貼文人", "Link",
    "Post date", "Threads Post ID", "Media Type",
    "瀏覽數", "讚", "留言", "轉發", "小飛機", "引用",
    "Reach", "Saved", "互動次數", "平均觀看秒數", "總觀看時間(分) ",  # 尾端空格為 Notion 端實際值，勿「修正」
]

errors = []
warnings = []


def normalize(name):
    """去除所有空白後的比對 key（抓「只差空格」的同名異字）"""
    return re.sub(r"\s+", "", name)


def fetch_db_schema(db_id, token):
    req = urllib.request.Request(f"https://api.notion.com/v1/databases/{db_id}")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Notion-Version", "2022-06-28")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        errors.append(f"無法取得 DB {db_id[:8]}… schema：HTTP {e.code} {body[:150]}")
        return None


def check_expected_props(db_label, props, expected):
    """檢查程式碼引用的欄位名是否與 Notion 完全一致（含空白）"""
    actual_names = list(props.keys())
    by_norm = {}
    for n in actual_names:
        by_norm.setdefault(normalize(n), []).append(n)

    for exp in expected:
        if exp in actual_names:
            continue
        variants = by_norm.get(normalize(exp), [])
        if variants:
            errors.append(
                f"[{db_label}] 欄位空白不一致：程式碼用 {exp!r}，Notion 實際是 "
                f"{', '.join(repr(v) for v in variants)}（會造成 PATCH 400 / 靜默忽略）"
            )
        else:
            errors.append(f"[{db_label}] 程式碼引用的欄位 {exp!r} 在 Notion 不存在")


# 本 repo 的 sync 腳本會寫入的選項值 — 這些值被污染會直接打中 pipeline → error
# 其他欄位的污染只列 warning（曝光但不擋每日同步，留給鴿王在 Notion 端合併）
PIPELINE_WRITTEN_VALUES = {
    "Platform": {"Threads", "Instagram"},
    "Format":   {"Post", "Reel"},
    "Status":   {"Posted"},
    "來源":     {"✍️人工"},  # canonical 無空格（260612 統一決策）
    "貼文人":   set(ACCOUNT_TO_POSTER.values()),
}


def check_option_duplicates(db_label, props):
    """掃 select/multi_select/status 選項：去空白後相同 = 污染"""
    for pname, pdef in props.items():
        ptype = pdef.get("type")
        if ptype not in ("select", "multi_select", "status"):
            continue
        options = pdef.get(ptype, {}).get("options", [])
        by_norm = {}
        for opt in options:
            by_norm.setdefault(normalize(opt["name"]), []).append(opt["name"])
        written = PIPELINE_WRITTEN_VALUES.get(pname, set())
        for norm_key, names in by_norm.items():
            if len(names) <= 1:
                continue
            msg = (
                f"[{db_label}] 欄位「{pname}」有同名異字選項（只差空白）："
                f"{', '.join(repr(n) for n in names)}（不二錯 #022 模式，請在 Notion 端合併）"
            )
            if pname == "貼文人" or any(n in written for n in names):
                errors.append(msg)
            else:
                warnings.append(msg)


def check_posters(db_label, props):
    """貼文人選項 vs 帳號註冊表 canonical 名"""
    poster_prop = props.get("貼文人")
    if not poster_prop or poster_prop.get("type") != "multi_select":
        return
    option_names = [o["name"] for o in poster_prop["multi_select"].get("options", [])]
    by_norm = {}
    for n in option_names:
        by_norm.setdefault(normalize(n), []).append(n)

    for key, poster in ACCOUNT_TO_POSTER.items():
        if poster in option_names:
            continue
        variants = [v for v in by_norm.get(normalize(poster), []) if v != poster]
        if variants:
            errors.append(
                f"[{db_label}] 帳號 {key} 的 poster {poster!r} 與 Notion 既有選項 "
                f"{', '.join(repr(v) for v in variants)} 只差空白 — 寫入會再生一個重複選項"
            )
        else:
            # 全新帳號第一次寫入時 Notion 會自動建選項，屬正常生命週期
            warnings.append(f"[{db_label}] 帳號 {key} 的 poster {poster!r} 尚無對應選項（首次寫入會自動建立）")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--warn-only", action="store_true", help="只印出問題，不以非零碼結束")
    args = parser.parse_args()

    token = os.environ.get("NOTION_TOKEN")
    if not token:
        sys.exit("❌ 缺少 NOTION_TOKEN")

    targets = []
    if os.environ.get("NOTION_THREADS_DB_ID"):
        targets.append(("Threads DB", os.environ["NOTION_THREADS_DB_ID"], EXPECTED_THREADS_DB_PROPS, False))
    if os.environ.get("NOTION_POSTS_DB_ID"):
        targets.append(("Posts DB", os.environ["NOTION_POSTS_DB_ID"], EXPECTED_POSTS_DB_PROPS, True))
    if not targets:
        sys.exit("❌ NOTION_THREADS_DB_ID / NOTION_POSTS_DB_ID 至少要給一個")

    for label, db_id, expected, has_poster in targets:
        schema = fetch_db_schema(db_id, token)
        if schema is None:
            continue
        props = schema.get("properties", {})
        print(f"🔍 {label}：{len(props)} 個欄位")
        check_expected_props(label, props, expected)
        check_option_duplicates(label, props)
        if has_poster:
            check_posters(label, props)

    for w in warnings:
        print(f"⚠️  {w}")
    if errors:
        print(f"\n❌ schema 驗證發現 {len(errors)} 個問題：")
        for e in errors:
            print(f"   - {e}")
        if not args.warn_only:
            sys.exit(1)
    else:
        print("✅ Notion schema 驗證通過（欄位名一致、無選項污染）")


if __name__ == "__main__":
    main()
