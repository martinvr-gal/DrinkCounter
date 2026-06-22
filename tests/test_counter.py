from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, CounterService, get_service


def build_service(tmp_path: Path) -> CounterService:
    return CounterService(tmp_path / "counter.db")


def test_counter_persists_across_service_instances(tmp_path: Path) -> None:
    first_service = build_service(tmp_path)
    assert first_service.get_counter() == 0

    first_service.increment(5)
    first_service.decrement(2)
    first_service.set_counter(11)

    second_service = build_service(tmp_path)
    assert second_service.get_counter() == 11


def test_api_increment_decrement_and_set(tmp_path: Path) -> None:
    test_db = tmp_path / "counter.db"
    test_service = CounterService(test_db)
    app.dependency_overrides[get_service] = lambda: test_service

    try:
        client = TestClient(app)

        assert client.get("/", follow_redirects=False).status_code == 307
        assert client.get("/tv").status_code == 200
        assert client.get("/admin").status_code == 200

        assert client.get("/api/counter").json() == {"value": 0}

        response = client.post("/api/counter/increment", json={"amount": 3})
        assert response.status_code == 200
        assert response.json() == {"value": 3}

        response = client.post("/api/counter/decrement", json={"amount": 2})
        assert response.status_code == 200
        assert response.json() == {"value": 1}

        response = client.post("/api/counter/set", json={"value": 8})
        assert response.status_code == 200
        assert response.json() == {"value": 8}

        response = client.post("/api/counter/increment", json={"amount": 0})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
