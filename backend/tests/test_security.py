from fastapi.testclient import TestClient


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Access-Key": ""})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_route_rejects_missing_key(client: TestClient) -> None:
    client.headers.pop("X-Access-Key")
    assert client.get("/api/auth/check").status_code == 401


def test_protected_route_rejects_wrong_key(client: TestClient) -> None:
    response = client.get("/api/auth/check", headers={"X-Access-Key": "wrong-key-000000"})
    assert response.status_code == 401


def test_protected_route_accepts_valid_key(client: TestClient) -> None:
    assert client.get("/api/auth/check").status_code == 200
