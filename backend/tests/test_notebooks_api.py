from fastapi.testclient import TestClient


def test_notebook_crud(client: TestClient) -> None:
    created = client.post("/api/notebooks", json={"title": "  Forschung  "}).json()
    assert created["title"] == "Forschung"
    assert created["source_count"] == 0

    listed = client.get("/api/notebooks").json()
    assert [nb["id"] for nb in listed] == [created["id"]]

    renamed = client.patch(f"/api/notebooks/{created['id']}", json={"title": "Neu"}).json()
    assert renamed["title"] == "Neu"

    assert client.delete(f"/api/notebooks/{created['id']}").status_code == 204
    assert client.get(f"/api/notebooks/{created['id']}").status_code == 404


def test_notebook_default_title_and_validation(client: TestClient) -> None:
    assert client.post("/api/notebooks", json={}).json()["title"] == "Unbenanntes Notebook"
    assert client.post("/api/notebooks", json={"title": ""}).status_code == 422


def test_unknown_notebook_returns_404(client: TestClient) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/api/notebooks/{missing}/sources").status_code == 404
