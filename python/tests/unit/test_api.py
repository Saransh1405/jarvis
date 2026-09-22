import json

import pytest
from fastapi.testclient import TestClient

from jarvis_ai.api.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_chat_stub(client: TestClient) -> None:
    resp = client.post("/api/v1/chat", json={"message": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert "Echo: hello" in data["message"]
    assert data["conversation_id"]
    assert data["provider"] == "stub"
    assert data["source"] == "llm"


def test_chat_calculator_via_api(client: TestClient) -> None:
    resp = client.post("/api/v1/chat", json={"message": "what is 99 times 101?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "9999" in data["message"]
    assert data["tools_used"] == ["calculator"]
    assert data["source"] == "agent:calculator"


def test_chat_stream_stub(client: TestClient) -> None:
    with client.stream("POST", "/api/v1/chat/stream", json={"message": "hi"}) as resp:
        assert resp.status_code == 200
        chunks = []
        for line in resp.iter_lines():
            if line.startswith("data: "):
                chunks.append(json.loads(line[6:]))
        assert any(c.get("type") == "token" for c in chunks)
        assert any(c.get("type") == "done" for c in chunks)
