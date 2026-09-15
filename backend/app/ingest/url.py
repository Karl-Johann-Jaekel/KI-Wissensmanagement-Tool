"""Fetch a web page (or a PDF behind a URL) with SSRF protection and extract its text."""

import ipaddress
import logging
import socket
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura

from app.ingest.chunker import Segment
from app.ingest.parsers import ParsedDocument, ParseError, parse_pdf

log = logging.getLogger(__name__)

MAX_BYTES = 15 * 1024 * 1024
MAX_REDIRECTS = 4
USER_AGENT = "Mozilla/5.0 (compatible; NotebookClone/0.1; +source-import)"


def fetch_url(url: str, timeout: float = 20.0) -> ParsedDocument:
    content_type, body, final_url = _safe_get(url, timeout)
    if "pdf" in content_type or body.startswith(b"%PDF-"):
        return parse_pdf(body, fallback_title=_title_from_url(final_url))

    html = body.decode("utf-8", errors="replace")
    text = trafilatura.extract(
        html, url=final_url, include_comments=False, include_tables=True, favor_precision=True
    )
    if not text or len(text.strip()) < 200:
        raise ParseError(
            "Auf der Seite wurde kein Artikeltext gefunden (evtl. JavaScript-Seite oder Paywall)."
        )
    metadata = trafilatura.extract_metadata(html, default_url=final_url)
    title = (metadata.title if metadata and metadata.title else None) or _title_from_url(final_url)
    return ParsedDocument(title=title[:500], segments=[Segment(text=text)])


def _safe_get(url: str, timeout: float) -> tuple[str, bytes, str]:
    current = url
    with httpx.Client(
        timeout=timeout, follow_redirects=False, headers={"User-Agent": USER_AGENT}
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            assert_public_http_url(current)
            with client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ParseError("Weiterleitung ohne Ziel.")
                    current = urljoin(current, location)
                    continue
                if response.status_code >= 400:
                    raise ParseError(f"Die Seite antwortete mit HTTP {response.status_code}.")
                content_type = response.headers.get("content-type", "").lower()
                if not any(t in content_type for t in ("html", "text", "pdf", "xml")):
                    raise ParseError(
                        f"Inhaltstyp {content_type or 'unbekannt'} wird nicht unterstützt."
                    )
                body = bytearray()
                for block in response.iter_bytes():
                    body.extend(block)
                    if len(body) > MAX_BYTES:
                        raise ParseError("Die Seite ist zu groß (> 15 MB).")
                return content_type, bytes(body), current
    raise ParseError("Zu viele Weiterleitungen.")


def assert_public_http_url(url: str) -> None:
    """Reject non-http(s) schemes and hosts resolving to private/loopback/link-local IPs."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ParseError("Nur http(s)-URLs werden unterstützt.")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ParseError(f"Host {parsed.hostname} wurde nicht gefunden.") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            log.warning("Blocked URL import to non-public address %s", address)
            raise ParseError("Die URL zeigt auf eine interne Adresse und ist nicht erlaubt.")


def _title_from_url(url: str) -> str:
    parsed = urlparse(url)
    last = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    return f"{parsed.hostname}{'/' + last if last else ''}"
