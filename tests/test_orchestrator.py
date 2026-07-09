import pytest
from fakeredis.aioredis import FakeRedis

from src.bot.models import SessionState
from src.bot.session import SessionManager
from src.orchestrator.engine import Orchestrator


@pytest.mark.asyncio
async def test_orchestrator_normal_flow() -> None:
    """Test standard conversational flow: state changes and dummy AI response."""
    redis_client = FakeRedis(decode_responses=True)
    try:
        session_manager = SessionManager(redis_client)
        orchestrator = Orchestrator(session_manager)
        session_id = "user_abc"

        # Idle session at start
        session = await session_manager.get_or_create_session(session_id)
        assert session.state == SessionState.IDLE

        # Process standard input
        response = await orchestrator.process_message(session_id, "How do I check my order status?")
        assert response.should_escalate is False
        assert "processing your request: How do I check my order status?" in response.text

        # Verify session state transitions to AWAITING_INPUT
        session = await session_manager.get_or_create_session(session_id)
        assert session.state == SessionState.AWAITING_INPUT
        assert len(session.history) == 2  # USER msg, BOT response msg
    finally:
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_orchestrator_escalation_keywords() -> None:
    """Test keyword-triggered escalations: transition state and escalate flag."""
    redis_client = FakeRedis(decode_responses=True)
    try:
        session_manager = SessionManager(redis_client)
        orchestrator = Orchestrator(session_manager)
        session_id = "user_escalate"

        # Check keyword "agent"
        response1 = await orchestrator.process_message(session_id, "I need an agent please.")
        assert response1.should_escalate is True
        assert "escalating" in response1.text.lower()

        session = await session_manager.get_or_create_session(session_id)
        assert session.state == SessionState.ESCALATED

        # Check keyword "refund" (even with different capitalization)
        session_id2 = "user_escalate2"
        response2 = await orchestrator.process_message(session_id2, "Where is my ReFuNd?")
        assert response2.should_escalate is True

        session2 = await session_manager.get_or_create_session(session_id2)
        assert session2.state == SessionState.ESCALATED
    finally:
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_orchestrator_human_handoff_behavior() -> None:
    """Test orchestrator behavior when session is currently in human handoff state."""
    redis_client = FakeRedis(decode_responses=True)
    try:
        session_manager = SessionManager(redis_client)
        orchestrator = Orchestrator(session_manager)
        session_id = "user_human"

        # Put session into Human Handoff state
        session = await session_manager.get_or_create_session(session_id)
        session.state = SessionState.HUMAN_HANDOFF
        await session_manager.update_session(session)

        # Send standard input -> bot should bypass standard processing and return placeholder support text
        response = await orchestrator.process_message(session_id, "Can you help me?")
        assert "representative will assist you" in response.text
        assert response.should_escalate is False

        # Session should remain in HUMAN_HANDOFF state
        session = await session_manager.get_or_create_session(session_id)
        assert session.state == SessionState.HUMAN_HANDOFF
    finally:
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_handle_agent_reply() -> None:
    """Test handling human agent replies and potential state transitions back."""
    redis_client = FakeRedis(decode_responses=True)
    try:
        session_manager = SessionManager(redis_client)
        orchestrator = Orchestrator(session_manager)
        session_id = "user_handoff"

        # Agent replies -> state transitions to HUMAN_HANDOFF
        response = await orchestrator.handle_agent_reply(session_id, "Hello, I am a human agent.")
        assert response.text == "Hello, I am a human agent."

        session = await session_manager.get_or_create_session(session_id)
        assert session.state == SessionState.HUMAN_HANDOFF

        # Agent closes chat -> state transitions back to AWAITING_INPUT
        await orchestrator.handle_agent_reply(session_id, "We have resolved your issue, closing now.")
        session2 = await session_manager.get_or_create_session(session_id)
        assert session2.state == SessionState.AWAITING_INPUT
    finally:
        await redis_client.aclose()
