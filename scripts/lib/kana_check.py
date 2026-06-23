"""
kana_check.py — 日文假名 pre-flight 攔截（issue #8 PR2）

避免 Claude 改寫時意外輸出日文假名（平假名 / 片假名 / 半型片假名），
跟既有 cosmate-ai-nexus/agents/dede/telegram-bot/src/threads.ts:preFlightKanaCheck
同一份規則。

只擋假名 — 日文漢字（新作、発売）跟繁中、符號、emoji 都不擋。
"""
from __future__ import annotations

import re

# 平假名 U+3040-309F / 片假名 U+30A0-30FF / 半型片假名 U+FF65-FF9F
_KANA_RE = re.compile(r"[぀-ゟ゠-ヿ･-ﾟ]")


def has_kana(text: str) -> bool:
    return bool(_KANA_RE.search(text or ""))


def find_kana_chars(text: str) -> list[str]:
    """找出命中的假名字元（去重，保留出現順序），給 error message 用。"""
    seen = set()
    out = []
    for ch in _KANA_RE.findall(text or ""):
        if ch not in seen:
            seen.add(ch)
            out.append(ch)
    return out
