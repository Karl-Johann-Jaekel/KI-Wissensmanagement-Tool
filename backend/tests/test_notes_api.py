from fastapi.testclient import TestClient

from tests.fakes import FakeLLM


def test_note_crud(client: TestClient, notebook_id: str) -> None:
    created = client.post(
        f"/api/notebooks/{notebook_id}/notes", json={"title": "Idee", "content": "Text"}
    )
    assert created.status_code == 201
    note = created.json()

    updated = client.patch(f"/api/notes/{note['id']}", json={"content": "Neuer Text"}).json()
    assert updated["title"] == "Idee"
    assert updated["content"] == "Neuer Text"

    listed = client.get(f"/api/notebooks/{notebook_id}/notes").json()
    assert [n["id"] for n in listed] == [note["id"]]

    assert client.delete(f"/api/notes/{note['id']}").status_code == 204
    assert client.get(f"/api/notebooks/{notebook_id}/notes").json() == []


def test_note_validation(client: TestClient, notebook_id: str) -> None:
    response = client.post(f"/api/notebooks/{notebook_id}/notes", json={"title": "", "content": ""})
    assert response.status_code == 422


def test_answer_can_be_saved_as_note_with_its_citations(
    client: TestClient, notebook_id: str, fake_llm: FakeLLM
) -> None:
    client.post(
        f"/api/notebooks/{notebook_id}/sources",
        files={"file": ("bericht.txt", b"Der Umsatz stieg um 12 Prozent.")},
    )
    fake_llm.answer = "Der Umsatz stieg um 12 % [1]."
    answer = client.post(
        f"/api/notebooks/{notebook_id}/chat", json={"question": "Wie entwickelte sich der Umsatz?"}
    ).json()["answer"]

    response = client.post(f"/api/notebooks/{notebook_id}/notes/from-message/{answer['id']}")
    assert response.status_code == 201
    note = response.json()
    assert note["title"] == "Wie entwickelte sich der Umsatz?"
    # The markers stay in the text and the citations travel with them, so a saved note
    # keeps working links into the source instead of a flat list of names.
    assert note["content"] == "Der Umsatz stieg um 12 % [1]."
    assert [c["n"] for c in note["citations"]] == [1]
    assert note["citations"][0]["source_title"] == "bericht"
    assert note["citations"][0]["chunk_id"] == answer["citations"][0]["chunk_id"]


def test_only_assistant_messages_of_the_notebook_can_become_notes(
    client: TestClient, notebook_id: str
) -> None:
    question = client.post(
        f"/api/notebooks/{notebook_id}/chat", json={"question": "Hallo?"}
    ).json()["question"]
    response = client.post(f"/api/notebooks/{notebook_id}/notes/from-message/{question['id']}")
    assert response.status_code == 404


def test_own_notes_have_no_citations(client: TestClient, notebook_id: str) -> None:
    note = client.post(
        f"/api/notebooks/{notebook_id}/notes",
        json={"title": "Eigene Notiz", "content": "Handgeschrieben [1]."},
    ).json()
    assert note["citations"] == []


def test_editing_a_saved_answer_keeps_its_citations(
    client: TestClient, notebook_id: str, fake_llm: FakeLLM
) -> None:
    client.post(
        f"/api/notebooks/{notebook_id}/sources",
        files={"file": ("bericht.txt", b"Der Umsatz stieg um 12 Prozent.")},
    )
    fake_llm.answer = "Der Umsatz stieg um 12 % [1]."
    answer = client.post(f"/api/notebooks/{notebook_id}/chat", json={"question": "Umsatz?"}).json()[
        "answer"
    ]
    note = client.post(f"/api/notebooks/{notebook_id}/notes/from-message/{answer['id']}").json()

    updated = client.patch(
        f"/api/notes/{note['id']}", json={"content": "Umsatz plus 12 % [1]. Eigener Zusatz."}
    ).json()
    assert [c["chunk_id"] for c in updated["citations"]] == [
        c["chunk_id"] for c in note["citations"]
    ]


def test_citation_of_a_deleted_source_explains_itself(
    client: TestClient, notebook_id: str, fake_llm: FakeLLM
) -> None:
    source_id = client.post(
        f"/api/notebooks/{notebook_id}/sources",
        files={"file": ("bericht.txt", b"Der Umsatz stieg um 12 Prozent.")},
    ).json()["id"]
    fake_llm.answer = "Der Umsatz stieg um 12 % [1]."
    answer = client.post(f"/api/notebooks/{notebook_id}/chat", json={"question": "Umsatz?"}).json()[
        "answer"
    ]
    note = client.post(f"/api/notebooks/{notebook_id}/notes/from-message/{answer['id']}").json()
    citation = note["citations"][0]

    client.delete(f"/api/sources/{source_id}")

    # The note keeps its citation; opening it has to say why nothing shows up.
    response = client.get(f"/api/sources/{source_id}/chunks/{citation['chunk_id']}")
    assert response.status_code == 404
    assert "nicht mehr" in response.json()["detail"]
