from dataclasses import dataclass

from app.services.text import normalize_text, stable_hash


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    content_hash: str


def chunk_text(text: str, *, max_chars: int = 1600, overlap_chars: int = 220) -> list[TextChunk]:
    clean = normalize_text(text)
    if not clean:
        return []

    paragraphs = [part.strip() for part in clean.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if not current:
            current = paragraph
            continue
        if len(current) + 2 + len(paragraph) <= max_chars:
            current = f"{current}\n\n{paragraph}"
            continue
        chunks.extend(_split_oversized(current, max_chars=max_chars, overlap_chars=overlap_chars))
        current = paragraph

    if current:
        chunks.extend(_split_oversized(current, max_chars=max_chars, overlap_chars=overlap_chars))

    return [
        TextChunk(index=index, content=chunk, content_hash=stable_hash(chunk))
        for index, chunk in enumerate(chunks)
        if chunk.strip()
    ]


def _split_oversized(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text.strip()]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            sentence_boundary = max(text.rfind(". ", start, end), text.rfind("\n", start, end))
            if sentence_boundary > start + max_chars // 2:
                end = sentence_boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap_chars)
    return chunks
