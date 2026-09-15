"""Paragraph-aware chunking with overlap.

Sizes are measured in characters (~4 chars per token for DE/EN), which keeps the chunker
dependency-free and deterministic. Chunks never cross page boundaries so every chunk has
exactly one page number for citations.
"""

import re
from dataclasses import dataclass

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[\"'„“(\[]?[A-ZÄÖÜ0-9])")
_WHITESPACE = re.compile(r"[ \t\f\v]+")


@dataclass(frozen=True)
class Segment:
    """A contiguous piece of source text, e.g. one PDF page."""

    text: str
    page: int | None = None


@dataclass(frozen=True)
class ChunkDraft:
    ordinal: int
    page: int | None
    content: str


def chunk_segments(
    segments: list[Segment], max_chars: int = 1800, overlap_chars: int = 300
) -> list[ChunkDraft]:
    if overlap_chars >= max_chars // 2:
        raise ValueError("overlap_chars must be smaller than half of max_chars")

    drafts: list[ChunkDraft] = []
    unit_limit = max_chars - overlap_chars - 2  # room for overlap + separator
    for segment in segments:
        current = ""
        for unit in _split_units(segment.text, unit_limit):
            if current and len(current) + 2 + len(unit) > max_chars:
                drafts.append(ChunkDraft(len(drafts), segment.page, current))
                tail = _overlap_tail(current, overlap_chars)
                current = f"{tail}\n\n{unit}" if tail else unit
            else:
                current = f"{current}\n\n{unit}" if current else unit
        if current:
            drafts.append(ChunkDraft(len(drafts), segment.page, current))
    return drafts


def _split_units(text: str, limit: int) -> list[str]:
    """Paragraphs; paragraphs above `limit` fall back to sentences, then to words."""
    units: list[str] = []
    for raw in _PARAGRAPH_SPLIT.split(text):
        paragraph = _normalize(raw)
        if not paragraph:
            continue
        if len(paragraph) <= limit:
            units.append(paragraph)
            continue
        buffer = ""
        for sentence in _SENTENCE_SPLIT.split(paragraph):
            for piece in _hard_split(sentence, limit):
                if buffer and len(buffer) + 1 + len(piece) > limit:
                    units.append(buffer)
                    buffer = piece
                else:
                    buffer = f"{buffer} {piece}" if buffer else piece
        if buffer:
            units.append(buffer)
    return units


def _hard_split(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    pieces: list[str] = []
    buffer = ""
    for word in text.split(" "):
        while len(word) > limit:  # pathological tokens, e.g. base64 blobs
            if buffer:
                pieces.append(buffer)
                buffer = ""
            pieces.append(word[:limit])
            word = word[limit:]
        if buffer and len(buffer) + 1 + len(word) > limit:
            pieces.append(buffer)
            buffer = word
        else:
            buffer = f"{buffer} {word}" if buffer else word
    if buffer:
        pieces.append(buffer)
    return pieces


def _overlap_tail(text: str, overlap_chars: int) -> str:
    """Last ~overlap_chars of text, snapped to a sentence or word start."""
    if len(text) <= overlap_chars:
        return ""
    tail = text[-overlap_chars:]
    sentence_start = _SENTENCE_SPLIT.search(tail)
    if sentence_start and sentence_start.end() < len(tail) // 2:
        return tail[sentence_start.end() :].strip()
    space = tail.find(" ")
    return tail[space + 1 :].strip() if space != -1 else tail.strip()


def _normalize(text: str) -> str:
    lines = [_WHITESPACE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
