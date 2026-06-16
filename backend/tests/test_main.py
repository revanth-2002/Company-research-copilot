from fastapi.testclient import TestClient
import os
import sys

from app.main import app


client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_and_get_session():
    payload = {
        "company_name": "Acme Corp",
        "website": "https://example.com",
        "objective": "Investigate market fit",
        "auto_run": False,
    }
    post = client.post("/sessions", json=payload)
    assert post.status_code == 200
    data = post.json()
    assert "id" in data
    session_id = data["id"]

    get = client.get(f"/sessions/{session_id}")
    assert get.status_code == 200
    got = get.json()
    assert got["id"] == session_id
