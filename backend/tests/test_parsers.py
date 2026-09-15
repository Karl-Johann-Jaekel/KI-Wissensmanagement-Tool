import pytest

from app.ingest.parsers import ParseError, parse_upload, reflow_pdf_text
from app.ingest.url import assert_public_http_url
from tests.pdf_factory import make_pdf


def test_markdown_title_comes_from_first_heading() -> None:
    doc = parse_upload("notes.md", b"# Mein Titel\n\nInhalt")
    assert doc.title == "Mein Titel"
    assert doc.segments[0].page is None


def test_text_falls_back_to_cp1252() -> None:
    doc = parse_upload("alt.txt", "Größe und Maß".encode("cp1252"))
    assert "Größe" in doc.segments[0].text
    assert doc.title == "alt"


def test_unsupported_extension_is_rejected() -> None:
    with pytest.raises(ParseError):
        parse_upload("bild.png", b"\x89PNG")


def test_empty_text_is_rejected() -> None:
    with pytest.raises(ParseError):
        parse_upload("leer.txt", b"   \n")


def test_pdf_keeps_page_numbers_and_metadata_title() -> None:
    data = make_pdf(
        [["Erste Seite ueber Vertraege."], [], ["Dritte Seite mit Paragraph 42."]],
        title="Vertragsrecht Grundlagen",
    )
    doc = parse_upload("upload.pdf", data)
    assert doc.title == "Vertragsrecht Grundlagen"
    assert doc.page_count == 3
    assert [s.page for s in doc.segments] == [1, 3]  # empty page skipped
    assert "Paragraph 42" in doc.segments[1].text


def test_pdf_without_text_is_rejected() -> None:
    with pytest.raises(ParseError, match="kein Text"):
        parse_upload("scan.pdf", make_pdf([[], []]))


def test_broken_pdf_is_rejected() -> None:
    with pytest.raises(ParseError):
        parse_upload("kaputt.pdf", b"%PDF-1.4 garbage")


def test_reflow_joins_hyphenated_words_and_wrapped_lines() -> None:
    raw = (
        "Dies ist eine lange Zeile, die im PDF hart umbro-\n"
        "chen wurde und dann weiter bis zum Ende läuft. Da\n"
        "steht noch ein kurzer Schluss.\n"
        "Neuer Absatz beginnt hier, auch er ist lang genug\n"
        "und endet mit einer vollen Zeile ohne Punkt am En-\n"
        "de."
    )
    text = reflow_pdf_text(raw)
    assert "umbrochen" in text
    assert "Ende läuft. Da steht" in text  # sentence end inside a full line is no paragraph break
    assert text.split("\n\n") == [
        "Dies ist eine lange Zeile, die im PDF hart umbrochen wurde und dann weiter bis zum "
        "Ende läuft. Da steht noch ein kurzer Schluss.",
        "Neuer Absatz beginnt hier, auch er ist lang genug und endet mit einer vollen Zeile "
        "ohne Punkt am Ende.",
    ]


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://10.0.0.5/",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "ftp://example.org/x",
    ],
)
def test_url_import_blocks_internal_targets(url: str) -> None:
    with pytest.raises(ParseError):
        assert_public_http_url(url)
