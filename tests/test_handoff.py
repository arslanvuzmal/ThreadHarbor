import pytest

from src.bot.session import SessionData
from src.handoff.client import MockZendeskClient
from src.handoff.payload import build_payload


@pytest.mark.asyncio
async def test_build_payload() -> None:
    """Tests that build_payload creates a correct Pydantic HandoffPayload."""
    session = SessionData(
        session_id="user-123",
        user_profile={"name": "Alice Smith", "phone": "12345", "tier": "premium"},
        transcript=[
            {"role": "user", "content": "I have an issue"},
            {"role": "assistant", "content": "Let me help you"},
            {"role": "user", "content": "It is unacceptable"},
        ]
    )

    payload = await build_payload(session, "Sentiment: Negative")

    # Assert Pydantic model structure
    assert payload.user_profile == {"name": "Alice Smith", "phone": "12345", "tier": "premium"}
    assert payload.escalation_reason == "Sentiment: Negative"
    assert "Alice" in payload.user_profile["name"]
    assert len(payload.transcript) == 3
    assert payload.conversation_summary != ""
    assert isinstance(payload.conversation_summary, str)


@pytest.mark.asyncio
async def test_mock_zendesk_client() -> None:
    """Tests that MockZendeskClient correctly manages tickets in-memory."""
    client = MockZendeskClient()
    session = SessionData(session_id="session-xyz")
    payload = await build_payload(session, "Explicit Request")

    # 1. Create Ticket
    ticket_id = await client.create_ticket("session-xyz", payload)
    assert ticket_id == "ZENDESK-1"
    assert ticket_id in client.tickets
    assert client.tickets[ticket_id]["status"] == "open"
    assert client.tickets[ticket_id]["session_id"] == "session-xyz"
    assert client.tickets[ticket_id]["payload"] == payload

    # 2. Send Message to Agent
    await client.send_agent_message(ticket_id, "User sent another message")
    assert "User sent another message" in client.tickets[ticket_id]["messages"]

    # 3. Close Ticket
    await client.close_ticket(ticket_id)
    assert client.tickets[ticket_id]["status"] == "closed"

    # 4. Error case for missing ticket
    with pytest.raises(ValueError, match="does not exist"):
        await client.send_agent_message("ZENDESK-999", "Hello")

    with pytest.raises(ValueError, match="does not exist"):
        await client.close_ticket("ZENDESK-999")
