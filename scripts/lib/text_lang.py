"""
text_lang.py — 文字語言判定（issue #8 PR2 follow-up）

複製自 scripts/analyze_by_topic.py:is_zh_tw（+ SIMPLIFIED_ONLY）— 抽到 lib 給
auto_post_pipeline 用，避免從 analyze_by_topic import 帶進不必要的副作用。

⚠️ 兩處同步：改 SIMPLIFIED_ONLY 或 is_zh_tw 規則時，記得同步更新
    scripts/analyze_by_topic.py:51 開始的 is_zh_tw 定義。
"""
from __future__ import annotations

import re

# 簡體獨有字（繁體不會出現），命中即視為簡中
SIMPLIFIED_ONLY = set(
    "们这国发说时间问题还过给从将见长书头东车动电风开关样应当对难条无边觉买习义谁"
    "话间应该没办继续应该实样区让进听给写发现几条业务运营产业数据网络计算机软"
)

_CJK_RE = re.compile(r"[一-鿿]")
_WS_RE = re.compile(r"\s")


def is_zh_tw(text: str) -> bool:
    """繁中啟發式：CJK 佔比 >= 30%、CJK 字數 >= 8、不含簡體獨有字。"""
    if not text:
        return False
    cjk = _CJK_RE.findall(text)
    stripped = _WS_RE.sub("", text)
    if not stripped:
        return False
    if len(cjk) / len(stripped) < 0.3 or len(cjk) < 8:
        return False
    if any(c in SIMPLIFIED_ONLY for c in text):
        return False
    return True
