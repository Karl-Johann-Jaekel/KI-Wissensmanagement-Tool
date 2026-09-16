"""Notebook overview and briefing document: both build on the per-source guides."""

from typing import Any

from fastapi.testclient import TestClient

from tests.fakes import FakeLLM


def _upload(client: TestClient, notebook_id: str, name: str, text: str) -> str:
    response = client.post(
        f"/api/notebooks/{notebook_id}/sources", files={"file": (name, text.encode())}
    )
    return str(response.json()["id"])


def _notebook(client: TestClient, notebook_id: str) -> Any:
    return client.get(f"/api/notebooks/{notebook_id}").json()


def test_overview_appears_once_a_source_guide_is_ready(
    client: TestClient, notebook_id: str
) -> None:
    assert _notebook(client, notebook_id)["overview_status"] == "pending"

    _upload(client, notebook_id, "bio.txt", "Pflanzen betreiben Photosynthese.")

    notebook = _notebook(client, notebook_id)
    assert notebook["overview_status"] == "ready"
    assert notebook["summary"] == "Die Quellen behandeln gemeinsam ein Thema."
    assert notebook["key_questions"] == ["Übergreifende Frage 1?", "Übergreifende Frage 2?"]


def test_overview_is_built_from_the_source_guides_not_the_raw_text(
    client: TestClient, notebook_id: str, fake_llm: FakeLLM
) -> None:
    _upload(client, notebook_id, "bio.txt", "Ein sehr spezieller Satz über Photosynthese.")

    overview_calls = [
        messages
        for messages, json_mode in fake_llm.calls
        if json_mode and messages[0]["content"].startswith("Du fasst zusammen")
    ]
    assert len(overview_calls) == 1
    prompt = overview_calls[0][-1]["content"]
    assert "Eine kurze Zusammenfassung." in prompt  # the guide summary
    assert "Ein sehr spezieller Satz" not in prompt  # not the document itself


def test_removing_the_last_source_clears_the_overview(client: TestClient, notebook_id: str) -> None:
    source_id = _upload(client, notebook_id, "bio.txt", "Pflanzen betreiben Photosynthese.")
    assert _notebook(client, notebook_id)["overview_status"] == "ready"

    client.delete(f"/api/sources/{source_id}")

    notebook = _notebook(client, notebook_id)
    assert notebook["overview_status"] == "pending"
    assert notebook["summary"] is None
    assert notebook["key_questions"] == []


def test_overview_can_be_regenerated(client: TestClient, notebook_id: str) -> None:
    _upload(client, notebook_id, "bio.txt", "Pflanzen betreiben Photosynthese.")

    response = client.post(f"/api/notebooks/{notebook_id}/overview")
    assert response.status_code == 202
    assert _notebook(client, notebook_id)["overview_status"] == "ready"


def test_briefing_answers_the_key_questions_with_citations(
    client: TestClient, notebook_id: str, fake_llm: FakeLLM
) -> None:
    source_id = _upload(client, notebook_id, "bio.txt", "Pflanzen betreiben Photosynthese.")
    fake_llm.answer = "Pflanzen nutzen Licht [1]."

    response = client.post(f"/api/notebooks/{notebook_id}/reports", json={"kind": "briefing"})
    assert response.status_code == 201, response.text
    note = response.json()

    assert note["title"].startswith("Briefing: ")
    # one section per key question of the overview
    assert "## Übergreifende Frage 1?" in note["content"]
    assert "## Übergreifende Frage 2?" in note["content"]
    # both sections cite the same passage, so the document lists it once
    assert len(note["citations"]) == 1
    assert note["citations"][0]["source_id"] == source_id
    assert note["citations"][0]["n"] == 1
    assert note["content"].count("[1]") == 2

    assert note["id"] in [n["id"] for n in client.get(f"/api/notebooks/{notebook_id}/notes").json()]


def test_report_without_sources_is_refused(client: TestClient, notebook_id: str) -> None:
    response = client.post(f"/api/notebooks/{notebook_id}/reports", json={})
    assert response.status_code == 409
    assert "Quellen-Guides" in response.json()["detail"]


def test_briefing_respects_the_source_filter(
    client: TestClient, notebook_id: str, fake_llm: FakeLLM
) -> None:
    _upload(client, notebook_id, "eins.txt", "Photosynthese in Quelle eins.")
    second = _upload(client, notebook_id, "zwei.txt", "Photosynthese in Quelle zwei.")
    fake_llm.answer = "Antwort [1]."

    note = client.post(
        f"/api/notebooks/{notebook_id}/reports", json={"source_ids": [second]}
    ).json()

    assert {c["source_id"] for c in note["citations"]} == {second}


def test_faq_asks_the_questions_of_the_source_guides(
    client: TestClient, notebook_id: str, fake_llm: FakeLLM
) -> None:
    _upload(client, notebook_id, "bio.txt", "Pflanzen betreiben Photosynthese.")
    fake_llm.answer = "Pflanzen nutzen Licht [1]."

    note = client.post(f"/api/notebooks/{notebook_id}/reports", json={"kind": "faq"}).json()

    assert note["title"].startswith("FAQ: ")
    # the source guide proposes these, the notebook overview proposes different ones
    for question in ("Frage 1?", "Frage 2?", "Frage 3?"):
        assert f"## {question}" in note["content"]
    assert "Übergreifende Frage 1?" not in note["content"]
    assert note["citations"]


def test_faq_spreads_over_the_sources_before_repeating_one(
    client: TestClient, notebook_id: str, fake_llm: FakeLLM
) -> None:
    _upload(client, notebook_id, "eins.txt", "Photosynthese in Quelle eins.")
    _upload(client, notebook_id, "zwei.txt", "Photosynthese in Quelle zwei.")
    fake_llm.answer = "Antwort [1]."

    note = client.post(f"/api/notebooks/{notebook_id}/reports", json={"kind": "faq"}).json()

    headings = [line for line in note["content"].splitlines() if line.startswith("## ")]
    # both sources propose the same three questions, so round-robin pairs them up
    assert headings[:2] == ["## Frage 1?", "## Frage 1?"]
    assert headings[2:4] == ["## Frage 2?", "## Frage 2?"]
