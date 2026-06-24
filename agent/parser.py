"""
LLM output parsing utilities for the persona engine.

Parses structured output from the single-pass Actor:
  【内心独白】 → monologue
  【最终回复】 → reply
  【表达方式】 → modality (语音/文字/照片/…)

Supports both Chinese and English section headers.
"""

from __future__ import annotations

import re


# -- Modality Parsing --
_MODALITY_ALIASES = {
    "文字": "文字",
    "text": "文字",
    "typing": "文字",
    "语音": "语音",
    "voice": "语音",
    "audio": "语音",
    "speech": "语音",
    "静默": "静默",
    "silence": "静默",
    "silent": "静默",
    "表情": "表情",
    "emoji": "表情",
    "sticker": "表情",
    "照片": "照片",
    "photo": "照片",
    "image": "照片",
    "selfie": "照片",
    "多条拆分": "多条拆分",
    "split": "多条拆分",
    "multiple": "多条拆分",
}

def _parse_modality(raw: str) -> str:
    """Extract primary modality keyword from Actor output.

    Returns the canonical Chinese modality key used by the skill engine.
    """
    cleaned = raw.strip().lstrip("\uff1a: \n")
    # Take first token before punctuation (。.，,、/ or whitespace)
    match = re.match(r'[\w\u4e00-\u9fff]+', cleaned)
    if not match:
        return "文字"
    return _MODALITY_ALIASES.get(match.group(0).lower(), "文字")


# -- Section header regex: Chinese 【】 and English [] formats --
_SECTION_RE = re.compile(
    r'(?:【(?P<zh>内心独白|最终回复|表达方式)】'
    r'|\[(?P<en>Inner Monologue|Final Reply|Expression Mode)\])'
)
_TAG_MAP = {
    '内心独白': 'monologue', 'Inner Monologue': 'monologue',
    '最终回复': 'reply',     'Final Reply': 'reply',
    '表达方式': 'modality',  'Expression Mode': 'modality',
}


def extract_reply(raw: str) -> tuple[str, str, str]:
    """Extract monologue, reply, and modality from Actor output.

    Supports both Chinese (【最终回复】) and English ([Final Reply]) section headers.
    Returns canonical Chinese modality key for internal consistency.
    """
    # Strip <think>...</think> blocks from reasoning models (e.g. MiniMax M2.7)
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()

    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(raw))
    for i, m in enumerate(matches):
        tag = m.group('zh') or m.group('en')
        key = _TAG_MAP[tag]
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        sections[key] = raw[start:end].strip()

    monologue = sections.get('monologue', '')
    reply = sections.get('reply', '')
    modality_raw = sections.get('modality', '')

    # Parse modality with bilingual map
    modality = _parse_modality(modality_raw) if modality_raw else "文字"

    # Silence short-circuit: Actor chose not to speak
    if modality == "静默":
        return monologue, "", "静默"

    if not reply:
        # Fallback: strip action descriptions
        reply = re.sub(r'[(（(][^)）)]*[)）)]', '', raw).strip()
        reply = re.sub(r'\*[^*]+\*', '', reply).strip()
        if not reply:
            reply = "..."
    else:
        # Normal path: strip action tags like *顿了顿* / ＊顿了顿＊ and （沉默） from reply
        reply = re.sub(r'[*＊][^*＊]+[*＊]', '', reply).strip()
        reply = re.sub(r'[（(][^（(）)]{1,40}[）)]', '', reply).strip()
        if not reply:
            reply = "..."

    return monologue, reply, modality
