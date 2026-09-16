from typing import Any

from fastapi.testclient import TestClient

from app.llm import prompts
from app.llm.provider import ChatMessage, LLMError
from tests.fakes import FakeLLM


def _upload(client: TestClient, notebook_id: str, name: str, text: str) -> str:
    response = client.post(
        f"/api/notebooks/{notebook_id}/sources", files={"file": (name, text.encode())}
    )
    return str(response.json()["id"])


def _chat(client: TestClient, notebook_id: str, **payload: Any) -> Any:
    return client.post(f"/api/notebooks/{notebook_id}/chat", json=payload)


def test_answer_contains_validated_citations(
    client: TestClient, notebook_id: str, fake_llm: FakeLLM
) -> None:
    source_id = _upload(client, notebook_id, "bio.txt", "Pflanzen betreiben Photosynthese.")
    fake_llm.answer = "Pflanzen nutzen Photosynthese [1]. Erfunden [7]."

    response = _chat(client, notebook_id, question="Was machen Pflanzen mit Licht?")
    assert response.status_code == 200
    answer = response.json()["answer"]
    assert answer["content"] == "Pflanzen nutzen Photosynthese [1]. Erfunden."
    assert len(answer["citations"]) == 1
    citation = answer["citations"][0]
    assert citation["source_id"] == source_id
    assert citation["source_title"] == "bio"
    assert "Photosynthese" in citation["snippet"]

    chunk = client.get(f"/api/sources/{source_id}/chunks/{citation['chunk_id']}")
    assert chunk.status_code == 200

    # passages were numbered and labelled in the prompt
    prompt = fake_llm.calls[-1][0][-1]["content"]
    assert "[1] (Quelle: bio)" in prompt

    messages = client.get(f"/api/notebooks/{notebook_id}/messages").json()
    assert [m["role"] for m in messages] == ["user", "assistant"]


def test_without_ready_sources_the_llm_is_not_called(
    client: TestClient, notebook_id: str, fake_llm: FakeLLM
) -> None:
    response = _chat(client, notebook_id, question="Irgendwas?")
    assert response.json()["answer"]["content"] == prompts.NO_SOURCES_ANSWER
    assert fake_llm.calls == []


def test_empty_source_selection_means_no_sources(
    client: TestClient, notebook_id: str, fake_llm: FakeLLM
) -> None:
    _upload(client, notebook_id, "a.txt", "Inhalt über Photosynthese.")
    calls_after_upload = len(fake_llm.calls)
    response = _chat(client, notebook_id, question="Photosynthese?", source_ids=[])
    assert response.json()["answer"]["content"] == prompts.NO_SOURCES_ANSWER
    assert len(fake_llm.calls) == calls_after_upload


def test_source_filter_limits_citations(
    client: TestClient, notebook_id: str, fake_llm: FakeLLM
) -> None:
    _upload(client, notebook_id, "eins.txt", "Photosynthese in Quelle eins.")
    second = _upload(client, notebook_id, "zwei.txt", "Photosynthese in Quelle zwei.")
    fake_llm.answer = "Antwort [1]."
    response = _chat(client, notebook_id, question="Photosynthese?", source_ids=[second])
    citations = response.json()["answer"]["citations"]
    assert [c["source_id"] for c in citations] == [second]


def test_llm_failure_returns_503_and_stores_nothing(
    client: TestClient, notebook_id: str, fake_llm: FakeLLM
) -> None:
    _upload(client, notebook_id, "a.txt", "Inhalt über Photosynthese.")

    def broken(_messages: list[ChatMessage]) -> str:
        raise LLMError("Das Sprachmodell ist gerade nicht erreichbar.")

    fake_llm.answer = broken
    response = _chat(client, notebook_id, question="Photosynthese?")
    assert response.status_code == 503
    assert "nicht erreichbar" in response.json()["detail"]
    assert client.get(f"/api/notebooks/{notebook_id}/messages").json() == []


def test_history_is_sent_without_citation_markers(
    client: TestClient, notebook_id: str, fake_llm: FakeLLM
) -> None:
    _upload(client, notebook_id, "a.txt", "Photosynthese braucht Licht und Wasser.")
    fake_llm.answer = "Sie braucht Licht [1]."
    _chat(client, notebook_id, question="Was braucht Photosynthese?")
    _chat(client, notebook_id, question="Und sonst?")

    messages = fake_llm.calls[-1][0]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[2]["content"] == "Sie braucht Licht."


def test_history_is_condensed_to_plain_short_text() -> None:
    from app.routers.chat import HISTORY_CHARS, condense_for_history

    verbose = (
        "Das Modell nutzt **8 Heads** [1]:\n\n- erster Punkt [2]\n- zweiter Punkt\n\n---\n"
        "**Keine Angaben zu folgenden Punkten**:\n1. Sanktionen\n" + "Weiterer Text. " * 60
    )
    condensed = condense_for_history(verbose)
    assert condensed.startswith("Das Modell nutzt 8 Heads: erster Punkt zweiter Punkt Keine")
    assert not any(token in condensed for token in ("**", "---", "\n", "[1]", "- "))
    assert len(condensed) <= HISTORY_CHARS + 2
    assert condensed.endswith(" …")


def test_clear_messages(client: TestClient, notebook_id: str) -> None:
    _chat(client, notebook_id, question="Hallo?")
    assert client.delete(f"/api/notebooks/{notebook_id}/messages").status_code == 204
    assert client.get(f"/api/notebooks/{notebook_id}/messages").json() == []
