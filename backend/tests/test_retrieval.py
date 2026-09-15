import uuid

from fastapi.testclient import TestClient

from app.db import get_sessionmaker
from app.retrieval.rrf import reciprocal_rank_fusion
from app.retrieval.search import hybrid_search, text_ranking
from app.retrieval.text_query import build_or_tsquery
from tests.fakes import FakeEmbedder


def test_rrf_rewards_items_ranked_high_in_both_lists() -> None:
    fused = reciprocal_rank_fusion([["a", "b"], ["c", "b"]])
    assert fused[0] == "b"  # rank 2 in both lists beats rank 1 in only one
    assert fused[1:] == ["a", "c"]


def test_rrf_limit_and_determinism() -> None:
    assert reciprocal_rank_fusion([["x", "y"], []], limit=1) == ["x"]
    assert reciprocal_rank_fusion([]) == []


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
