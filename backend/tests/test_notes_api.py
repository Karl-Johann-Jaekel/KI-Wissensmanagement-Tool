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


def test_answer_can_be_saved_as_note_with_source_list(
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
    assert note["content"] == "Der Umsatz stieg um 12 % [1].\n\nQuellen:\n[1] bericht"


def test_only_assistant_messages_of_the_notebook_can_become_notes(
    client: TestClient, notebook_id: str
) -> None:
    question = client.post(
        f"/api/notebooks/{notebook_id}/chat", json={"question": "Hallo?"}
    ).json()["question"]
    response = client.post(f"/api/notebooks/{notebook_id}/notes/from-message/{question['id']}")
    assert response.status_code == 404
