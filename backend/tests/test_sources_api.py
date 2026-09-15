from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import get_sessionmaker
from app.ingest.pipeline import recover_interrupted
from app.llm.provider import LLMError
from app.models import Chunk, Source
from tests.fakes import FakeLLM
from tests.pdf_factory import make_pdf

LONG_TEXT = "\n\n".join(
    f"Absatz {i}: Die Photosynthese wandelt Lichtenergie in chemische Energie um. " * 6
    for i in range(20)
)


def _upload(client: TestClient, notebook_id: str, name: str, data: bytes) -> Any:
    return client.post(f"/api/notebooks/{notebook_id}/sources", files={"file": (name, data)})


def _only_source(client: TestClient, notebook_id: str) -> dict[str, Any]:
    sources = client.get(f"/api/notebooks/{notebook_id}/sources").json()
    assert len(sources) == 1
    return dict(sources[0])


def test_text_upload_is_chunked_embedded_and_gets_a_guide(
    client: TestClient, notebook_id: str
) -> None:
    response = _upload(client, notebook_id, "bio.md", f"# Biologie\n\n{LONG_TEXT}".encode())
    assert response.status_code == 202
    assert response.json()["status"] == "processing"

    source = _only_source(client, notebook_id)  # background task ran inside TestClient
    assert source["status"] == "ready"
    assert source["title"] == "Biologie"
    assert source["chunk_count"] > 1
    assert source["guide_status"] == "ready"
    assert source["summary"] == "Eine kurze Zusammenfassung."
    assert len(source["suggested_questions"]) == 3
    assert client.get(f"/api/notebooks/{notebook_id}").json()["source_count"] == 1


def test_pdf_upload_keeps_pages(client: TestClient, notebook_id: str) -> None:
    pdf = make_pdf([["Seite eins handelt von Vertraegen."], ["Seite zwei von Paragraph 42."]])
    _upload(client, notebook_id, "recht.pdf", pdf)
    source = _only_source(client, notebook_id)
    assert source["status"] == "ready"
    assert source["type"] == "pdf"
    assert source["page_count"] == 2

    with get_sessionmaker()() as db:
        pages = db.scalars(select(Chunk.page).order_by(Chunk.ordinal)).all()
    assert pages == [1, 2]


def test_unsupported_file_type_is_rejected(client: TestClient, notebook_id: str) -> None:
    assert _upload(client, notebook_id, "bild.png", b"\x89PNG").status_code == 415


def test_too_large_upload_is_rejected(client: TestClient, notebook_id: str) -> None:
    from app.config import get_settings
    from app.main import app

    small = get_settings().model_copy(update={"max_upload_mb": 1})
    app.dependency_overrides[get_settings] = lambda: small
    response = _upload(client, notebook_id, "big.txt", b"x" * (1024 * 1024 + 1))
    assert response.status_code == 413


def test_unreadable_pdf_ends_in_error_state(client: TestClient, notebook_id: str) -> None:
    _upload(client, notebook_id, "kaputt.pdf", b"%PDF-1.4 nonsense")
    source = _only_source(client, notebook_id)
    assert source["status"] == "error"
    assert "PDF" in source["error"]


def test_guide_failure_keeps_source_usable_and_can_be_retried(
    client: TestClient, notebook_id: str, fake_llm: FakeLLM
) -> None:
    def broken(*_args: object, **_kwargs: object) -> str:
        raise LLMError("Rate limit")

    original = fake_llm.complete
    fake_llm.complete = broken  # type: ignore[method-assign]
    _upload(client, notebook_id, "a.txt", LONG_TEXT.encode())
    source = _only_source(client, notebook_id)
    assert source["status"] == "ready"
    assert source["guide_status"] == "error"
    assert source["guide_error"] == "Rate limit"

    fake_llm.complete = original  # type: ignore[method-assign]
    assert client.post(f"/api/sources/{source['id']}/guide").status_code == 202
    assert _only_source(client, notebook_id)["guide_status"] == "ready"


def test_chunk_endpoint_returns_neighbours(client: TestClient, notebook_id: str) -> None:
    _upload(client, notebook_id, "a.txt", LONG_TEXT.encode())
    source = _only_source(client, notebook_id)
    with get_sessionmaker()() as db:
        chunk_ids = db.scalars(select(Chunk.id).order_by(Chunk.ordinal)).all()

    middle = client.get(f"/api/sources/{source['id']}/chunks/{chunk_ids[1]}").json()
    assert middle["ordinal"] == 1
    assert middle["previous_content"] and middle["next_content"]
    assert middle["source_title"] == "a"

    other = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/api/sources/{other}/chunks/{chunk_ids[1]}").status_code == 404


def test_deleting_source_removes_chunks(client: TestClient, notebook_id: str) -> None:
    _upload(client, notebook_id, "a.txt", LONG_TEXT.encode())
    source = _only_source(client, notebook_id)
    assert client.delete(f"/api/sources/{source['id']}").status_code == 204
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(Chunk)) == 0


def test_recover_interrupted_marks_stuck_sources(client: TestClient, notebook_id: str) -> None:
    with get_sessionmaker()() as db:
        db.add(Source(notebook_id=notebook_id, title="x", type="text", status="processing"))
        db.commit()
        recover_interrupted(db)
    source = _only_source(client, notebook_id)
    assert source["status"] == "error"
    assert "unterbrochen" in source["error"]
