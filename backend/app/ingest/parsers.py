"""Turn uploaded bytes into text segments (one per PDF page, one for plain text)."""

import io
import logging
import re
from dataclasses import dataclass
from pathlib import PurePath

from pypdf import PdfReader

from app.ingest.chunker import Segment

log = logging.getLogger(__name__)

TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
PDF_EXTENSIONS = {".pdf"}


class ParseError(ValueError):
    """User-facing parsing problem; the message is shown in the UI."""


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    segments: list[Segment]
    page_count: int | None = None


def parse_upload(filename: str, data: bytes) -> ParsedDocument:
    suffix = PurePath(filename).suffix.lower()
    if suffix in PDF_EXTENSIONS or data.startswith(b"%PDF-"):
        return parse_pdf(data, fallback_title=_stem(filename))
    if suffix in TEXT_EXTENSIONS:
        return parse_text(data, fallback_title=_stem(filename), markdown=suffix != ".txt")
    raise ParseError(f"Dateityp {suffix or '(ohne Endung)'} wird nicht unterstützt (PDF, TXT, MD).")


def parse_text(data: bytes, fallback_title: str, markdown: bool = False) -> ParsedDocument:
    text = _decode(data)
    if not text.strip():
        raise ParseError("Die Datei enthält keinen Text.")
    title = fallback_title
    if markdown:
        heading = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
        if heading:
            title = heading.group(1).strip()
    return ParsedDocument(title=title[:500], segments=[Segment(text=text)])


def parse_pdf(data: bytes, fallback_title: str) -> ParsedDocument:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        pages = list(reader.pages)
    except Exception as exc:
        log.warning("PDF could not be opened: %s", exc)
        raise ParseError(
            "Das PDF konnte nicht gelesen werden (beschädigt oder verschlüsselt)."
        ) from exc

    segments: list[Segment] = []
    for number, page in enumerate(pages, start=1):
        try:
            raw = page.extract_text() or ""
        except Exception as exc:  # a single broken page should not fail the document
            log.warning("Text extraction failed on page %d: %s", number, exc)
            continue
        text = reflow_pdf_text(raw)
        if text:
            segments.append(Segment(text=text, page=number))

    if not segments:
        raise ParseError(
            "Im PDF wurde kein Text gefunden. Gescannte PDFs (nur Bilder) werden nicht unterstützt."
        )

    title = fallback_title
    metadata_title = (reader.metadata.title if reader.metadata else None) or ""
    if len(metadata_title.strip()) > 3:
        title = metadata_title.strip()
    return ParsedDocument(title=title[:500], segments=segments, page_count=len(pages))


def reflow_pdf_text(raw: str) -> str:
    """Join hard-wrapped PDF lines into paragraphs.

    - `Silben-\\ntrennung` → `Silbentrennung` (only when the next line starts lowercase)
    - a line ending a sentence and noticeably shorter than a full line ends a paragraph
    """
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    full_width = sorted(len(line) for line in lines)[int(len(lines) * 0.8)]

    paragraphs: list[str] = []
    current = ""
    for line in lines:
        if not current:
            current = line
        elif re.search(r"[A-Za-zÄÖÜäöüß]-$", current) and line[:1].islower():
            current = current[:-1] + line
        else:
            current = f"{current} {line}"
        if re.search(r"[.!?:…\"“”]$", line) and len(line) < full_width * 0.75:
            paragraphs.append(current)
            current = ""
    if current:
        paragraphs.append(current)
    return "\n\n".join(paragraphs)


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def _stem(filename: str) -> str:
    return PurePath(filename).stem or "Unbenannte Quelle"
