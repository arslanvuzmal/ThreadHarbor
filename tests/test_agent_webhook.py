from fastapi.testclient import TestClient


def test_agent_message_missing_token(client: TestClient) -> None:
    """Tests that POST /agent/message without Authorization returns 401."""
    payload = {
        "session_id": "test-user-1",
        "agent_id": "agent-1",
        "text": "Hello client",
        "action": "reply",
    }
    response = client.post("/agent/message", json=payload)
    assert response.status_code == 401
    assert "Missing Authorization header" in response.json()["error"]["message"]


def test_agent_message_invalid_token(client: TestClient) -> None:
    """Tests that POST /agent/message with invalid Authorization returns 401."""
    payload = {
        "session_id": "test-user-1",
        "agent_id": "agent-1",
        "text": "Hello client",
        "action": "reply",
    }
    headers = {"Authorization": "Bearer wrong_secret"}
    response = client.post("/agent/message", json=payload, headers=headers)
    assert response.status_code == 401
    assert "Invalid agent API secret" in response.json()["error"]["message"]


def test_agent_message_reply_action(client: TestClient) -> None:
    """Tests POST /agent/message with reply action and valid token."""
    # Ensure token matches default_agent_secret or whatever we configured
    # From settings we have AGENT_API_SECRET = "default_agent_secret"
    headers = {"Authorization": "Bearer default_agent_secret"}
    payload = {
        "session_id": "test-user-2",
        "agent_id": "agent-1",
        "text": "We are looking into **your order**",
        "action": "reply",
    }
    response = client.post("/agent/message", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


def test_agent_message_close_action(client: TestClient) -> None:
    """Tests POST /agent/message with close action transitions session and sends CSAT."""
    headers = {"Authorization": "Bearer default_agent_secret"}
    payload = {
        "session_id": "test-user-3",
        "agent_id": "agent-1",
        "text": "Closing chat",
        "action": "close",
    }
    response = client.post("/agent/message", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"status": "success"}
