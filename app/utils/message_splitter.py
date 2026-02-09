from __future__ import annotations

import re

def split_response(text: str, max_length: int = 300) -> list[str]:
    if not text or not text.strip():
        return []

    text = text.strip()

    if len(text) <= max_length:
        return [text]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) > 1:
        return _merge_chunks(paragraphs, max_length)

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) > 1:
        return _merge_chunks(lines, max_length)

    sentences = _split_sentences(text)
    if len(sentences) > 1:
        return _merge_chunks(sentences, max_length)

    return _split_by_length(text, max_length)

def _split_sentences(text: str) -> list[str]:
    pattern = r'(?<=[.!?])\s+'
    sentences = re.split(pattern, text)
    return [s.strip() for s in sentences if s.strip()]

def _merge_chunks(parts: list[str], max_length: int) -> list[str]:
    chunks: list[str] = []
    current = ""

    for part in parts:
        if len(part) > max_length:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_by_length(part, max_length))
            continue

        separator = "\n\n" if current else ""
        candidate = f"{current}{separator}{part}" if current else part

        if len(candidate) <= max_length:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = part

    if current:
        chunks.append(current.strip())

    return [c for c in chunks if c]

def _split_by_length(text: str, max_length: int) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current = ""

    for word in words:
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= max_length:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = word

    if current:
        chunks.append(current.strip())

    return [c for c in chunks if c]
