#!/usr/bin/env python3
"""
heal_notion_options.py — 自動修復 Notion select 選項的「只差空白」污染（self-heal）。

背景：某些未跟上 260612「無空格 canonical」遷移的殘留寫入端（例：nexus 舊 clone
的 dcard 腳本）會反覆寫入含空格的選項值（如「✍️ 人工」），Notion 便自動把該選項
重新建回來 → validate_notion_schema 偵測到「只差空白」污染 → metrics-sync 整條凍結
（不二錯 #022 的復發形態）。

本 script 掛在 metrics-sync validate 步驟「之前」：把「正規化（去空白）後等於 canonical、
但不完全相等」的髒選項，所有使用它的頁面 retag 成 canonical，再從 schema 刪掉髒選項。
只往「已知 canonical」合併，不猜測；冪等（沒污染就 no-op），失敗不擋（exit 0）。

用法（環境變數）：
  NOTION_TOKEN         必填
  NOTION_POSTS_DB_ID   必填（要修的 DB）

  python3 scripts/heal_notion_options.py            # 修復
  python3 scripts/heal_notion_options.py --dry-run  # 只報告，不動 Notion

僅用 stdlib。
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

# (DB 環境變數名, 欄位名, canonical 值) — 只針對 pipeline 會寫、canonical 明確的 select 欄位。
# canonical 與 validate_notion_schema.py 的 PIPELINE_WRITTEN_VALUES 保持一致。
HEAL_TARGETS = [
    ("NOTION_POSTS_DB_ID", "來源", "✍️人工"),
]

# multi_select 的「同人物差字變體」別名表（差的不只是空白，正規化抓不到，需明列）。
# 例：交友中Kiki（漏「的」）→ 交友中的Kiki。canonical 名以 accounts.py ACCOUNT_TO_POSTER 為準。
# 發現新變體就往這裡加一行（比照 nexus commands.ts alias 容錯做法）。
# 結構：DB 環境變數名 → 欄位名 → { 舊變體: canonical }
MULTISELECT_ALIASES = {
    "NOTION_POSTS_DB_ID": {
        "貼文人": {
            "交友中Kiki": "交友中的Kiki",
        },
    },
}


def normalize(name):
    return re.sub(r"\s+", "", name)


def api(method, path, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"https://api.notion.com/v1{path}", data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Notion-Version", "2022-06-28")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def query_pages_with_option(db_id, field, option_name, token):
    pages, cursor = [], None
    while True:
        body = {"filter": {"property": field, "select": {"equals": option_name}}, "page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        res = api("POST", f"/databases/{db_id}/query", token, body)
        pages += res["results"]
        if not res.get("has_more"):
            return pages
        cursor = res["next_cursor"]


def heal_select(db_id, field, canonical, token, dry_run):
    """回傳 (髒選項數, 已 retag 頁數)。"""
    schema = api("GET", f"/databases/{db_id}", token)
    prop = schema.get("properties", {}).get(field)
    if not prop or prop.get("type") != "select":
        return 0, 0
    options = prop["select"]["options"]
    norm_canon = normalize(canonical)
    bad = [o for o in options if normalize(o["name"]) == norm_canon and o["name"] != canonical]
    if not bad:
        return 0, 0

    bad_names = [o["name"] for o in bad]
    print(f"🩹 [{field}] 發現含空白污染選項：{', '.join(repr(n) for n in bad_names)} → 併入 {canonical!r}")

    retagged = 0
    for name in bad_names:
        pages = query_pages_with_option(db_id, field, name, token)
        print(f"   - {name!r}：{len(pages)} 頁待 retag")
        if dry_run:
            retagged += len(pages)
            continue
        for p in pages:
            api("PATCH", f"/pages/{p['id']}", token, {"properties": {field: {"select": {"name": canonical}}}})
            retagged += 1

    if not dry_run:
        # 重新抓 schema（retag 可能剛建出 canonical 選項），保留除髒選項外的全部
        fresh = api("GET", f"/databases/{db_id}", token)["properties"][field]["select"]["options"]
        keep = [{"id": o["id"]} for o in fresh
                if not (normalize(o["name"]) == norm_canon and o["name"] != canonical)]
        api("PATCH", f"/databases/{db_id}", token, {"properties": {field: {"select": {"options": keep}}}})
        print(f"   ✅ 已刪除 {len(bad_names)} 個髒選項、retag {retagged} 頁")
    else:
        print(f"   （dry-run）將 retag {retagged} 頁並刪除 {len(bad_names)} 個髒選項")
    return len(bad_names), retagged


def query_pages_with_multiselect(db_id, field, option_name, token):
    pages, cursor = [], None
    while True:
        body = {"filter": {"property": field, "multi_select": {"contains": option_name}}, "page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        res = api("POST", f"/databases/{db_id}/query", token, body)
        pages += res["results"]
        if not res.get("has_more"):
            return pages
        cursor = res["next_cursor"]


def heal_multiselect_aliases(db_id, field, alias_map, token, dry_run):
    """把 multi_select 的已知舊變體 tag 併入 canonical，再刪掉變體選項。回傳 (變體數, retag 頁數)。"""
    schema = api("GET", f"/databases/{db_id}", token)
    prop = schema.get("properties", {}).get(field)
    if not prop or prop.get("type") != "multi_select":
        return 0, 0
    existing = {o["name"] for o in prop["multi_select"]["options"]}
    variants = {v: c for v, c in alias_map.items() if v in existing}
    if not variants:
        return 0, 0

    retagged = 0
    for variant, canonical in variants.items():
        pages = query_pages_with_multiselect(db_id, field, variant, token)
        print(f"🩹 [{field}] 差字變體 {variant!r} → 併入 {canonical!r}：{len(pages)} 頁待 retag")
        if dry_run:
            retagged += len(pages)
            continue
        for p in pages:
            cur = [o["name"] for o in p["properties"][field]["multi_select"]]
            new = [n for n in cur if n != variant]
            if canonical not in new:
                new.append(canonical)
            api("PATCH", f"/pages/{p['id']}", token,
                {"properties": {field: {"multi_select": [{"name": n} for n in new]}}})
            retagged += 1

    if not dry_run:
        fresh = api("GET", f"/databases/{db_id}", token)["properties"][field]["multi_select"]["options"]
        keep = [{"id": o["id"]} for o in fresh if o["name"] not in variants]
        api("PATCH", f"/databases/{db_id}", token, {"properties": {field: {"multi_select": {"options": keep}}}})
        print(f"   ✅ 已刪除 {len(variants)} 個變體選項、retag {retagged} 頁")
    else:
        print(f"   （dry-run）將 retag {retagged} 頁並刪除 {len(variants)} 個變體選項")
    return len(variants), retagged


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只報告，不動 Notion")
    args = parser.parse_args()

    token = os.environ.get("NOTION_TOKEN")
    if not token:
        sys.exit("❌ 缺少 NOTION_TOKEN")

    total_bad = 0
    for db_env, field, canonical in HEAL_TARGETS:
        db_id = os.environ.get(db_env)
        if not db_id:
            print(f"⏭️  {db_env} 未設定，跳過 {field}")
            continue
        try:
            n_bad, _ = heal_select(db_id, field, canonical, token, args.dry_run)
            total_bad += n_bad
        except urllib.error.HTTPError as e:
            # 自癒失敗不擋 pipeline（後面的 validate 仍會攔）；印出讓 log 看得到
            body = e.read().decode("utf-8", errors="replace")
            print(f"⚠️  自癒 {field} 失敗：HTTP {e.code} {body[:150]}", file=sys.stderr)

    # multi_select 差字變體（例：貼文人 交友中Kiki → 交友中的Kiki）
    for db_env, fields in MULTISELECT_ALIASES.items():
        db_id = os.environ.get(db_env)
        if not db_id:
            print(f"⏭️  {db_env} 未設定，跳過 multi_select 別名修復")
            continue
        for field, alias_map in fields.items():
            try:
                n_var, _ = heal_multiselect_aliases(db_id, field, alias_map, token, args.dry_run)
                total_bad += n_var
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                print(f"⚠️  自癒 {field} 別名失敗：HTTP {e.code} {body[:150]}", file=sys.stderr)

    if total_bad == 0:
        print("✅ 無選項污染，無需修復")


if __name__ == "__main__":
    main()
