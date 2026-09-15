import uuid

from fastapi.testclient import TestClient

from app.db import get_sessionmaker
from app.models import Chunk
from app.retrieval.rrf import reciprocal_rank_fusion
from app.retrieval.search import hybrid_search, reference_ranking, text_ranking
from app.retrieval.text_query import build_or_tsquery, extract_references
from tests.fakes import FakeEmbedder


def test_rrf_rewards_items_ranked_high_in_both_lists() -> None:
    fused = reciprocal_rank_fusion([["a", "b"], ["c", "b"]])
    assert fused[0] == "b"  # rank 2 in both lists beats rank 1 in only one
    assert fused[1:] == ["a", "c"]


def test_rrf_limit_and_determinism() -> None:
    assert reciprocal_rank_fusion([["x", "y"], []], limit=1) == ["x"]
    assert reciprocal_rank_fusion([]) == []


def test_rrf_weights_favour_a_ranking() -> None:
    assert reciprocal_rank_fusion([["a"], ["b"]], weights=[1.0, 2.0]) == ["b", "a"]


def test_references_are_extracted_from_questions() -> None:
    labels = [r.label for r in extract_references("Was regeln Art. 5 und Artikel 50 sowie § 42a?")]
    assert labels == ["Art. 5", "Artikel 50", "§ 42a"]
    assert [r.label for r in extract_references("Was steht in Anhang III?")] == ["Anhang III"]
    assert extract_references("Welche Pflichten gelten für Anbieter?") == []


def test_reference_heading_is_distinguished_from_cross_reference() -> None:
    (article_50,) = extract_references("Was regelt Artikel 50?")
    assert article_50.heading.search("KAPITEL IV Artikel 50 Transparenzpflichten für Anbieter")
    assert not article_50.heading.search("gemäß Artikel 50 Absatz 2 der Verordnung")
    assert not article_50.heading.search("Pflichten gemäß Artikel 50; e) weitere")
    (article_5,) = extract_references("Artikel 5?")
    assert not article_5.heading.search("Artikel 50 Transparenzpflichten")


def test_tsquery_drops_stopwords_and_sanitizes() -> None:
    assert build_or_tsquery("Was steht in § 42 über die Kündigung?") == "steht | 42 | kündigung"
    assert build_or_tsquery("What is the XJ-4711 & 'drop'?") == "xj | 4711 | drop"
    assert build_or_tsquery("Was ist das?") is None


def _upload(client: TestClient, notebook_id: str, name: str, text: str) -> str:
    response = client.post(
        f"/api/notebooks/{notebook_id}/sources", files={"file": (name, text.encode())}
    )
    return str(response.json()["id"])


FILLER = "\n\n".join(
    f"Abschnitt {i} beschreibt allgemeine Grundlagen der Organisation und ihrer Abläufe. " * 5
    for i in range(12)
)


def test_full_text_finds_exact_rare_term(client: TestClient, notebook_id: str) -> None:
    _upload(client, notebook_id, "a.txt", FILLER + "\n\nDas Bauteil XJ4711 ist zertifiziert.")
    with get_sessionmaker()() as db:
        ids = text_ranking(db, uuid.UUID(notebook_id), None, "Ist XJ4711 zertifiziert?", 20)
        top = hybrid_search(
            db,
            notebook_id=uuid.UUID(notebook_id),
            source_ids=None,
            question="Ist XJ4711 zertifiziert?",
            query_vector=FakeEmbedder().embed_query("Ist XJ4711 zertifiziert?"),
        )
    assert len(ids) == 1
    assert top[0].chunk_id == ids[0]
    assert "XJ4711" in top[0].content


def test_article_question_finds_defining_chunk_and_its_continuation(
    client: TestClient, notebook_id: str
) -> None:
    law = "\n\n".join(
        [
            FILLER,
            "Die Behörde prüft die Transparenzpflichten gemäß Artikel 50 Absatz 2 jährlich.",
            FILLER,
            "KAPITEL IV Artikel 50 Transparenzpflichten für Anbieter und Betreiber bestimmter "
            "KI-Systeme.",
            "(1) Anbieter stellen sicher, dass Personen informiert werden, wenn sie mit einem "
            "KI-System interagieren. " * 12,
            FILLER,
            "Artikel 5 Verbotene Praktiken im KI-Bereich sind unzulässig.",
        ]
    )
    _upload(client, notebook_id, "verordnung.txt", law)
    question = "Was regelt Artikel 50?"
    with get_sessionmaker()() as db:
        ranked = reference_ranking(db, uuid.UUID(notebook_id), None, question, 20)
        top = hybrid_search(
            db,
            notebook_id=uuid.UUID(notebook_id),
            source_ids=None,
            question=question,
            query_vector=FakeEmbedder().embed_query(question),
        )
        contents = {c.id: c.content for c in db.query(Chunk).all()}

    assert "Artikel 50 Transparenzpflichten" in contents[ranked[0]]
    assert "(1) Anbieter stellen sicher" in contents[ranked[1]]  # continuation of the article
    assert any("Absatz 2 jährlich" in contents[chunk_id] for chunk_id in ranked[2:])
    assert not any("Artikel 5 Verbotene" in contents[chunk_id] for chunk_id in ranked)
    assert top[0].chunk_id == ranked[0]


def test_search_is_scoped_to_notebook_and_selected_sources(
    client: TestClient, notebook_id: str
) -> None:
    other = client.post("/api/notebooks", json={"title": "Anderes"}).json()["id"]
    _upload(client, other, "fremd.txt", "Photosynthese im fremden Notebook.")
    first = _upload(client, notebook_id, "eins.txt", "Photosynthese in Quelle eins.")
    second = _upload(client, notebook_id, "zwei.txt", "Photosynthese in Quelle zwei.")

    with get_sessionmaker()() as db:
        vector = FakeEmbedder().embed_query("Photosynthese")
        everything = hybrid_search(
            db,
            notebook_id=uuid.UUID(notebook_id),
            source_ids=None,
            question="Photosynthese",
            query_vector=vector,
        )
        only_second = hybrid_search(
            db,
            notebook_id=uuid.UUID(notebook_id),
            source_ids=[uuid.UUID(second)],
            question="Photosynthese",
            query_vector=vector,
        )
    assert {str(r.source_id) for r in everything} == {first, second}
    assert {str(r.source_id) for r in only_second} == {second}
