"""
Utilitario para dividir respostas longas em mensagens menores,
simulando naturalidade em conversas de WhatsApp.
"""
from __future__ import annotations

import re


def split_response(text: str, max_length: int = 300) -> list[str]:
    """
    Divide uma resposta longa em chunks menores para envio sequencial.

    Estrategia de divisao (em ordem de prioridade):
    1. Por paragrafos (\\n\\n)
    2. Por quebras de linha (\\n)
    3. Por sentencas (pontuacao final)
    4. Por tamanho maximo (fallback)

    Args:
        text: Texto completo da resposta.
        max_length: Tamanho maximo de cada chunk.

    Returns:
        Lista de strings, cada uma sendo um chunk da mensagem.
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    # Se ja esta dentro do limite, retorna direto
    if len(text) <= max_length:
        return [text]

    # 1. Tenta dividir por paragrafos
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) > 1:
        return _merge_chunks(paragraphs, max_length)

    # 2. Tenta dividir por quebras de linha
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) > 1:
        return _merge_chunks(lines, max_length)

    # 3. Tenta dividir por sentencas
    sentences = _split_sentences(text)
    if len(sentences) > 1:
        return _merge_chunks(sentences, max_length)

    # 4. Fallback: divide por tamanho maximo respeitando espacos
    return _split_by_length(text, max_length)


def _split_sentences(text: str) -> list[str]:
    """Divide texto em sentencas usando pontuacao final."""
    # Divide em sentencas por . ! ? seguidos de espaco ou fim de string
    pattern = r'(?<=[.!?])\s+'
    sentences = re.split(pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def _merge_chunks(parts: list[str], max_length: int) -> list[str]:
    """
    Agrupa partes pequenas em chunks que respeitem o max_length.
    Se uma parte individual excede max_length, aplica split_by_length.
    """
    chunks: list[str] = []
    current = ""

    for part in parts:
        # Se a parte sozinha excede o limite, divide ela
        if len(part) > max_length:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_by_length(part, max_length))
            continue

        # Tenta adicionar ao chunk atual
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
    """Divide texto por tamanho, respeitando limites de palavras."""
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
