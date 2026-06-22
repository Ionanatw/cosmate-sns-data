"""
persona_loader.py — 從 Notion page 載入人設 system prompt（issue #8 PR2）

對齊 cosmate-ai-nexus/agents/dede/telegram-bot/src/notion.ts:fetchPersonaSystemPrompt
的概念：把 page 底下所有 block 的 plain text 串成一段 prompt。

OLIE 人設 page id: 33d6fedce91a815b9a3de3d4998ded88
"""
from __future__ import annotations

from typing import Iterable

from notion_lib import notion_request


OLIE_PERSONA_PAGE_ID = "3256fedce91a80b9b2dfeb790d20d8b3"  # P-SNS-03 Olie Huang

# Fallback：當 Notion page 載入失敗（404 / 權限不足 / 空頁）時用
# 來源：cosmate-ai-nexus/agents/dede/telegram-bot/src/contentgen.ts L63-67 的 inline spec
OLIE_FALLBACK_PROMPT = """你是動漫宅 Olie，一個動漫遊戲達人、ACG 文化評論者。

寫作口吻：
- 知識型、有深度、帶個人主見
- 偶爾用 ACG 圈內梗
- 避免淺薄、雞湯、無腦吹捧

禁用詞（這些開頭/句法絕對不寫）：
- 「哈哈哈」
- 「你好」、「大家好」

寫貼文時：用第一人稱或無人稱，像在跟同好聊天，
有自己的觀點跟判斷，不只是轉述事實。"""

# Notion API 回傳的 block 物件，每個 type 的 text 在 type 同名的子物件裡的 rich_text。
# 例: { "type": "paragraph", "paragraph": { "rich_text": [{"plain_text": "..."}] } }
_TEXT_BLOCK_TYPES = (
    "paragraph",
    "heading_1", "heading_2", "heading_3",
    "bulleted_list_item", "numbered_list_item",
    "quote", "callout", "to_do", "toggle",
    "code",
)


def _block_to_text(block: dict) -> str:
    btype = block.get("type")
    if btype not in _TEXT_BLOCK_TYPES:
        return ""
    rich = block.get(btype, {}).get("rich_text", [])
    return "".join(t.get("plain_text", "") for t in rich)


def _fetch_children(block_id: str, token: str) -> Iterable[dict]:
    """分頁拉完一個 page/block 底下所有 children。"""
    cursor = None
    while True:
        path = f"/blocks/{block_id}/children?page_size=100"
        if cursor:
            path += f"&start_cursor={cursor}"
        resp = notion_request("GET", path, token)
        if not resp:
            return
        for b in resp.get("results", []):
            yield b
        if not resp.get("has_more"):
            return
        cursor = resp.get("next_cursor")


def fetch_persona_system_prompt(page_id: str, token: str) -> str:
    """把 page 內所有文字 block 串成單一 system prompt 字串。

    遞迴展開 — 子 block 的內容也會被收進來（保留段落順序）。
    回空字串代表載入失敗 / page 沒內容（caller 要自己決定要不要 fallback）。
    """
    lines = []

    def walk(node_id: str):
        for block in _fetch_children(node_id, token):
            text = _block_to_text(block)
            if text:
                lines.append(text)
            if block.get("has_children"):
                walk(block["id"])

    walk(page_id)
    return "\n".join(lines).strip()


def fetch_olie_persona(token: str) -> tuple[str, str]:
    """載 OLIE persona，回 (prompt, source)。source = "notion" | "fallback"。

    Notion 載入失敗（404 / 沒 share / 空頁）→ 自動退回 inline OLIE_FALLBACK_PROMPT。
    避免 production pipeline 因 Notion 不可訪問而整個停掉。
    """
    prompt = fetch_persona_system_prompt(OLIE_PERSONA_PAGE_ID, token)
    if prompt:
        return prompt, "notion"
    return OLIE_FALLBACK_PROMPT, "fallback"
