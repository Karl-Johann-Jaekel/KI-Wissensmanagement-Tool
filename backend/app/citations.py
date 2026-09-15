"""Parse, validate and renumber `[n]` citation markers in model answers (ADR-05)."""

import re
import uuid
from dataclasses import dataclass

# [1]  [1, 3]  [1; 3]  [2-4]  [2–4]
_GROUP_PATTERN = r"\[\s*(\d+(?:\s*(?:[,;]|[-–])\s*\d+)*)\s*\]"
_GROUP = re.compile(_GROUP_PATTERN)
# adjacent groups such as "[1][2] [3]" belong to the same claim
_RUN = re.compile(rf"{_GROUP_PATTERN}(?:[ \t]*{_GROUP_PATTERN})*")
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([.,;:!?)])")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
SNIPPET_CHARS = 220
MAX_RANGE = 10
MAX_CITATIONS_PER_CLAIM = 3


@dataclass(frozen=True)
class Passage:
    n: int  # number shown to the model, 1-based
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    source_title: str
    page: int | None
    content: str


@dataclass(frozen=True)
class ResolvedCitation:
    n: int  # renumbered, 1-based, in order of first appearance
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    source_title: str
    page: int | None
    snippet: str


def resolve_citations(answer: str, passages: list[Passage]) -> tuple[str, list[ResolvedCitation]]:
    """Return the cleaned answer and the citations it actually uses.

    - numbers not in `passages` invalidate their whole bracket group; such groups are removed
      (typically academic references like `[2, 19]` copied from the source text)
    - more than MAX_CITATIONS_PER_CLAIM adjacent numbers are removed as a whole: models tend to
      append every passage to statements like "the sources say nothing about this"
    - valid numbers are renumbered by first appearance and written as `[1][2]`
    """
    by_number = {p.n: p for p in passages}
    new_number: dict[int, int] = {}

    def drop_dumps(match: re.Match[str]) -> str:
        numbers = {n for group in _GROUP.findall(match.group(0)) for n in _expand(group)}
        return "" if len(numbers) > MAX_CITATIONS_PER_CLAIM else match.group(0)

    def replace(match: re.Match[str]) -> str:
        numbers = _expand(match.group(1))
        if not numbers or any(n not in by_number for n in numbers):
            return ""
        rendered: list[str] = []
        for n in numbers:
            if n not in new_number:
                new_number[n] = len(new_number) + 1
            marker = f"[{new_number[n]}]"
            if marker not in rendered:
                rendered.append(marker)
        return "".join(rendered)

    text = _GROUP.sub(replace, _RUN.sub(drop_dumps, answer))
    text = re.sub(r"(?<=\d\])[ \t]+(?=\[\d)", "", text)  # [1] [2] → [1][2]
    text = re.sub(r"(\[\d+\])(?:\1)+", r"\1", text)  # [1][1] → [1]
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    text = _MULTI_SPACE.sub(" ", text).strip()

    citations = [
        ResolvedCitation(
            n=renumbered,
            chunk_id=by_number[original].chunk_id,
            source_id=by_number[original].source_id,
            source_title=by_number[original].source_title,
            page=by_number[original].page,
            snippet=_snippet(by_number[original].content),
        )
        for original, renumbered in sorted(new_number.items(), key=lambda item: item[1])
    ]
    return text, citations


def strip_citations(text: str) -> str:
    """Remove all markers, e.g. for chat history sent back to the model."""
    return _MULTI_SPACE.sub(" ", _SPACE_BEFORE_PUNCT.sub(r"\1", _GROUP.sub("", text))).strip()


def _expand(group: str) -> list[int]:
    numbers: list[int] = []
    for part in re.split(r"\s*[,;]\s*", group.strip()):
        bounds = re.split(r"\s*[-–]\s*", part)
        if len(bounds) == 2:
            start, end = int(bounds[0]), int(bounds[1])
            if end < start or end - start > MAX_RANGE:
                return []
            numbers.extend(range(start, end + 1))
        else:
            numbers.append(int(bounds[0]))
    return list(dict.fromkeys(numbers))


def _snippet(content: str) -> str:
    flat = " ".join(content.split())
    if len(flat) <= SNIPPET_CHARS:
        return flat
    cut = flat[:SNIPPET_CHARS].rsplit(" ", 1)[0]
    return f"{cut} …"
