import uuid

import pytest

from app.citations import Passage, resolve_citations, strip_citations


def passages(count: int) -> list[Passage]:
    source = uuid.uuid4()
    return [
        Passage(
            n=i,
            chunk_id=uuid.uuid4(),
            source_id=source,
            source_title="Bericht",
            page=i * 10,
            content=f"Inhalt der Passage {i}. " * 20,
        )
        for i in range(1, count + 1)
    ]


def test_valid_markers_are_renumbered_by_first_appearance() -> None:
    ps = passages(4)
    text, citations = resolve_citations("A stimmt [3]. B auch [1]. C wieder [3].", ps)
    assert text == "A stimmt [1]. B auch [2]. C wieder [1]."
    assert [(c.n, c.chunk_id, c.page) for c in citations] == [
        (1, ps[2].chunk_id, 30),
        (2, ps[0].chunk_id, 10),
    ]


def test_invented_numbers_are_removed() -> None:
    text, citations = resolve_citations("Erfunden [9]. Echt [2].", passages(3))
    assert text == "Erfunden. Echt [1]."
    assert len(citations) == 1


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("Mehrere [1, 3].", "Mehrere [1][2]."),
        ("Semikolon [3; 1].", "Semikolon [1][2]."),
        ("Bereich [2-4].", "Bereich [1][2][3]."),
        ("Gedankenstrich [2–3].", "Gedankenstrich [1][2]."),
        ("Nebeneinander [2][2] und [2].", "Nebeneinander [1] und [1]."),
        ("Leerzeichen [ 1 ].", "Leerzeichen [1]."),
        # observed with ministral-14b on the AI Act: sub-units glued to the passage number
        ("Verbot a [3a], Verbot e [4, lit. e].", "Verbot a [1], Verbot e [2]."),
        ("Absatz [3, Abs. 2].", "Absatz [1]."),
    ],
)
def test_marker_variants_are_normalized(answer: str, expected: str) -> None:
    text, _ = resolve_citations(answer, passages(5))
    assert text == expected


def test_group_with_any_invalid_number_is_dropped_entirely() -> None:
    # typical academic reference copied from a paper, not a passage citation
    text, citations = resolve_citations("Wie gezeigt [2, 19], gilt das [1].", passages(8))
    assert text == "Wie gezeigt, gilt das [1]."
    assert [c.n for c in citations] == [1]


def test_citation_dump_on_a_single_claim_is_removed() -> None:
    # observed with ministral-14b on a question the sources cannot answer
    answer = "Dazu enthalten die Quellen keine Angaben. [1][2][3][4][5][6][7][8]"
    text, citations = resolve_citations(answer, passages(8))
    assert text == "Dazu enthalten die Quellen keine Angaben."
    assert citations == []


def test_up_to_three_adjacent_citations_are_kept() -> None:
    text, citations = resolve_citations("A [1][2] [3]. B [4, 5, 6, 7]. C [2-5].", passages(8))
    assert text == "A [1][2][3]. B. C."
    assert [c.n for c in citations] == [1, 2, 3]


def test_zero_and_absurd_ranges_are_invalid() -> None:
    text, citations = resolve_citations("Null [0]. Riesig [1-500].", passages(8))
    assert text == "Null. Riesig."
    assert citations == []


def test_answer_without_markers_yields_no_citations() -> None:
    text, citations = resolve_citations("Dazu enthalten die Quellen keine Angaben.", passages(3))
    assert text == "Dazu enthalten die Quellen keine Angaben."
    assert citations == []


def test_snippet_is_shortened_at_word_boundary() -> None:
    _, citations = resolve_citations("X [1].", passages(1))
    snippet = citations[0].snippet
    assert snippet.endswith(" …")
    assert len(snippet) <= 222


def test_strip_citations() -> None:
    assert strip_citations("Der Umsatz stieg [1][2], vor allem [3, 4] durch Export [5].") == (
        "Der Umsatz stieg, vor allem durch Export."
    )
