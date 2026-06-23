#!/usr/bin/env python3
"""
lint_repo.py — 跨平台相容性與硬路徑守門（stdlib only）

歷史上 6 個 fix commit 全是「macOS 寫、Linux CI 跑」才爆的炸彈，
這個 lint 在 PR 階段就攔下來：

  R1  *.sh 禁用 `date -v`        （BSD date，Ubuntu 會 invalid option）
  R2  *.sh 禁用 `declare -A`     （bash 4+，macOS 內建 bash 3.x 不支援）
  R3  .github/workflows 禁出現 /Users/ 硬路徑（CI 上必炸）
  R4  scripts/ 出現 /Users/ 硬路徑僅允許 LOCAL_PATH_ALLOW 內的檔案
      （那些是「本機 fallback、CI 有 guard」的既有設計）

用法：python3 scripts/lint_repo.py   # 有違規 exit 1
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 已棄用、僅留參考的舊腳本，不納入檢查
LEGACY_SKIP = {
    "scripts/scrape_multi_topic.sh",  # 已由 scrape_multi_topic.py 取代
}

# 允許 /Users/ 出現的檔案：本機 .env fallback / 上游 repo fallback 路徑（都有存在性 guard）
LOCAL_PATH_ALLOW = {
    "scripts/fetch_insights.sh",
    "scripts/fetch_ig_insights.sh",
    "scripts/extract_trending_signals.py",
    "scripts/scrape_playwright_topics.py",
    "scripts/scrape_cosmate.py",
    "scripts/upload_secrets.sh",
    "scripts/backfill_trending_signal_urls.py",
    "scripts/lint_repo.py",  # 本檔（docstring 提到規則）
    "scripts/lib/notion_lib.py",  # ionachen .env.threads fallback（跟 extract_trending_signals 同性質）
}

RULES_SH = [
    (re.compile(r"\bdate\s+-v"), "R1: `date -v` 是 BSD-only，Linux 會炸 — 改用 python3 算時間"),
    (re.compile(r"\bdeclare\s+-A"), "R2: `declare -A` 需 bash 4+，macOS bash 3.x 不支援 — 改用 grep/case"),
]

violations = []


def rel(p):
    return str(p.relative_to(REPO))


def lint_shell(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        for pattern, msg in RULES_SH:
            if pattern.search(line):
                violations.append(f"{rel(path)}:{lineno} — {msg}")


def lint_hardcoded_paths(path, allow):
    if rel(path) in allow:
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        if "/Users/" in line:
            violations.append(
                f"{rel(path)}:{lineno} — R3/R4: 硬寫 /Users/ 路徑，CI（Ubuntu）上不存在 — "
                "改用 Path(__file__) 相對路徑或環境變數"
            )


def main():
    sh_files = sorted(REPO.glob("scripts/**/*.sh"))
    py_files = sorted(REPO.glob("scripts/**/*.py"))
    wf_files = sorted(REPO.glob(".github/workflows/*.yml"))

    for f in sh_files:
        if rel(f) in LEGACY_SKIP:
            continue
        lint_shell(f)
        lint_hardcoded_paths(f, LOCAL_PATH_ALLOW)

    for f in py_files:
        lint_hardcoded_paths(f, LOCAL_PATH_ALLOW)

    for f in wf_files:
        lint_hardcoded_paths(f, allow=set())  # workflows 零容忍

    checked = len(sh_files) + len(py_files) + len(wf_files)
    if violations:
        print(f"❌ lint 發現 {len(violations)} 個違規：")
        for v in violations:
            print(f"   - {v}")
        sys.exit(1)
    print(f"✅ lint 通過（檢查 {checked} 個檔案）")


if __name__ == "__main__":
    main()
