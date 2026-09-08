from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

import api
from api import app


client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("message", ["", "   ", "\t\n"])
def test_chat_rejects_blank_messages(monkeypatch, message):
    session_factory = Mock()
    runner = AsyncMock()
    monkeypatch.setattr(api, "SQLiteSession", session_factory)
    monkeypatch.setattr(api.Runner, "run", runner)

    response = client.post("/chat", json={"message": message})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "message"]
    session_factory.assert_not_called()
    runner.assert_not_called()


@pytest.mark.parametrize("message", ["What is the DSCR for loan 1001?", "  Hello  "])
def test_chat_accepts_nonempty_messages(monkeypatch, message):
    agent = object()
    session = object()
    session_factory = Mock(return_value=session)
    runner = AsyncMock(return_value=SimpleNamespace(final_output="Test answer"))
    monkeypatch.setattr(app.state, "loan_agent", agent, raising=False)
    monkeypatch.setattr(api, "SQLiteSession", session_factory)
    monkeypatch.setattr(api.Runner, "run", runner)

    response = client.post("/chat", json={"message": message})

    assert response.status_code == 200
    assert response.json() == {"answer": "Test answer"}
    session_factory.assert_called_once_with("web_demo", "web_conversations.db")
    runner.assert_awaited_once_with(agent, message, session=session)
