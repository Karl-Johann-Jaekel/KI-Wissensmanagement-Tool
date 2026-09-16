import pytest

from app.ingest.chunker import Segment, chunk_segments

SENTENCE = "Die Photosynthese wandelt Lichtenergie in chemische Energie um. "


def paragraph(n_sentences: int) -> str:
    return (SENTENCE * n_sentences).strip()


def test_short_text_yields_single_chunk() -> None:
    chunks = chunk_segments([Segment("Ein kurzer Absatz.")], max_chars=500, overlap_chars=100)
    assert len(chunks) == 1
    assert chunks[0].content == "Ein kurzer Absatz."
    assert chunks[0].ordinal == 0
    assert chunks[0].page is None


def test_empty_segments_are_skipped() -> None:
    assert (
        chunk_segments([Segment("   \n\n  "), Segment("")], max_chars=500, overlap_chars=100) == []
    )


def test_chunks_respect_max_size_and_have_sequential_ordinals() -> None:
    text = "\n\n".join(paragraph(4) for _ in range(30))
    chunks = chunk_segments([Segment(text)], max_chars=600, overlap_chars=120)
    assert len(chunks) > 5
    assert all(len(c.content) <= 600 for c in chunks)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_paragraph_boundaries_are_preferred() -> None:
    paragraphs = [f"Absatz {i}. " + paragraph(3) for i in range(10)]
    chunks = chunk_segments([Segment("\n\n".join(paragraphs))], max_chars=700, overlap_chars=50)
    for chunk in chunks:
        # every chunk ends with a complete paragraph, never mid-sentence
        assert chunk.content.endswith("um.")


def test_consecutive_chunks_overlap() -> None:
    text = "\n\n".join(f"Satz Nummer {i} steht hier. " * 3 for i in range(40))
    chunks = chunk_segments([Segment(text)], max_chars=500, overlap_chars=120)
    for previous, following in zip(chunks, chunks[1:], strict=False):
        head = following.content.split("\n\n")[0]
        assert head in previous.content, "next chunk should start with the tail of the previous one"


def test_long_paragraph_without_breaks_is_split_by_sentence_then_words() -> None:
    long_sentence = " ".join(["Wort"] * 800)  # ~4000 chars, no sentence punctuation
    chunks = chunk_segments([Segment(long_sentence)], max_chars=500, overlap_chars=100)
    assert len(chunks) > 1
    assert all(len(c.content) <= 500 for c in chunks)
    assert all("Wor " not in c.content for c in chunks), "words must not be cut in half"


def test_pathological_token_is_hard_cut() -> None:
    chunks = chunk_segments([Segment("x" * 2000)], max_chars=500, overlap_chars=100)
    assert all(len(c.content) <= 500 for c in chunks)
    assert "".join(c.content.replace("\n\n", "") for c in chunks).count("x") >= 2000


def test_pages_are_preserved_and_chunks_never_cross_pages() -> None:
    segments = [Segment(paragraph(20), page=1), Segment("Seite zwei.", page=2)]
    chunks = chunk_segments(segments, max_chars=400, overlap_chars=80)
    assert {c.page for c in chunks} == {1, 2}
    assert chunks[-1].page == 2
    assert chunks[-1].content == "Seite zwei."


def test_invalid_overlap_is_rejected() -> None:
    with pytest.raises(ValueError):
        chunk_segments([Segment("x")], max_chars=100, overlap_chars=60)
