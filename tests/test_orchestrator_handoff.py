import pytest

from src.handoff.client import MockZendeskClient
from src.orchestrator.engine import Orchestrator


@pytest.mark.asyncio
async def test_angry_user_pre_llm_escalation() -> None:
    """Tests that an angry user message triggers escalation, bypassing the LLM call entirely."""
    client = MockZendeskClient()
    orchestrator = Orchestrator(handoff_client=client)

    session_id = "user-abc"
    user_input = "Your product is a total scam and I'm super angry!"

    response = await orchestrator.handle_message(session_id, user_input)

    # 1. Assert response
    assert response.text == "I'm connecting you to a human specialist. Please hold."

    # 2. Check that state transitioned to HUMAN_HANDOFF
    session = await orchestrator.get_or_create_session(session_id)
    assert session.state == "HUMAN_HANDOFF"
    assert session.ticket_id == "ZENDESK-1"

    # 3. Check ticket in MockZendeskClient
    assert "ZENDESK-1" in client.tickets
    ticket = client.tickets["ZENDESK-1"]
    assert ticket["payload"].escalation_reason == "Sentiment: Negative"


@pytest.mark.asyncio
async def test_silent_mode_bypass_in_human_handoff() -> None:
    """Tests that when a session is in HUMAN_HANDOFF state, user inputs bypass the LLM and forward to the agent."""
    client = MockZendeskClient()
    orchestrator = Orchestrator(handoff_client=client)

    session_id = "user-def"

    # First, let's trigger escalation to transition to HUMAN_HANDOFF
    response_1 = await orchestrator.handle_message(session_id, "I want to talk to a human representative")
    assert response_1.text == "I'm connecting you to a human specialist. Please hold."

    session = await orchestrator.get_or_create_session(session_id)
    assert session.state == "HUMAN_HANDOFF"
    ticket_id = session.ticket_id
    assert ticket_id == "ZENDESK-1"

    # Send a message during HUMAN_HANDOFF
    response_2 = await orchestrator.handle_message(session_id, "Can you see my message, agent?")

    # Should bypass LLM, return empty response, and forward message to agent
    assert response_2.text == ""

    # Check transcript has the user message
    session_post = await orchestrator.get_or_create_session(session_id)
    assert session_post.transcript[-1]["role"] == "user"
    assert session_post.transcript[-1]["content"] == "Can you see my message, agent?"

    # Check mock ticket has received the message
    assert "Can you see my message, agent?" in client.tickets[ticket_id]["messages"]


@pytest.mark.asyncio
async def test_policy_limit_post_llm_escalation() -> None:
    """Tests that a restricted tool call (e.g. refund > 500) triggers post-LLM escalation."""
    client = MockZendeskClient()
    orchestrator = Orchestrator(handoff_client=client)

    session_id = "user-ghi"
    response = await orchestrator.handle_message(session_id, "force refund trigger")

    # Should trigger post-LLM escalation and transition state
    assert response.text == "I'm connecting you to a human specialist. Please hold."

    session = await orchestrator.get_or_create_session(session_id)
    assert session.state == "HUMAN_HANDOFF"
    assert session.ticket_id == "ZENDESK-1"
