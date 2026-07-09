from unittest.mock import AsyncMock, MagicMock

import pytest
from fakeredis.aioredis import FakeRedis

from src.bot.models import SessionState
from src.bot.session import SessionManager
from src.orchestrator.engine import Orchestrator


@pytest.mark.asyncio
async def test_orchestrator_bypass_handoff() -> None:
    """Test that Orchestrator bypasses AI completion if session is already in HUMAN_HANDOFF."""
    redis_client = FakeRedis(decode_responses=True)
    try:
        session_manager = SessionManager(redis_client)
        session_id = "user_handoff_bypass"

        session = await session_manager.get_or_create_session(session_id)
        session.state = SessionState.HUMAN_HANDOFF
        await session_manager.update_session(session)

        # Mock LLM and RAG Pipeline
        mock_llm = MagicMock()
        mock_rag = MagicMock()

        orchestrator = Orchestrator(session_manager, mock_llm, mock_rag)

        # Call process_message
        response = await orchestrator.process_message(session_id, "Hello, is anyone there?")

        # Check that it returns fallback bypass representative text
        assert "representative will assist" in response.text
        assert response.should_escalate is False
        mock_llm.chat_completion.assert_not_called()
    finally:
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_orchestrator_agentic_loop_direct_answer() -> None:
    """Test Orchestrator process message directly returning text without tool execution."""
    redis_client = FakeRedis(decode_responses=True)
    try:
        session_manager = SessionManager(redis_client)
        session_id = "user_direct_answer"

        # Mock RAG
        mock_rag = AsyncMock()
        mock_rag.retrieve_context.return_value = [{"text": "Sample context FAQ answer."}]

        # Mock LLM client returning clean text directly
        mock_llm = AsyncMock()
        mock_llm.chat_completion.return_value = {
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": "Our standard delivery takes 3 business days.",
            },
        }

        orchestrator = Orchestrator(session_manager, mock_llm, mock_rag)

        response = await orchestrator.process_message(session_id, "How long does shipping take?")

        assert "delivery" in response.text
        assert response.should_escalate is False

        # Session should be AWAITING_INPUT
        session = await session_manager.get_or_create_session(session_id)
        assert session.state == SessionState.AWAITING_INPUT
        assert len(session.history) == 2  # USER + BOT
    finally:
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_orchestrator_agentic_loop_with_tool_calling() -> None:
    """Test Orchestrator resolving LLM tool calls and generating final text after execution."""
    redis_client = FakeRedis(decode_responses=True)
    try:
        session_manager = SessionManager(redis_client)
        session_id = "user_tool_caller"

        mock_rag = AsyncMock()
        mock_rag.retrieve_context.return_value = []

        mock_llm = AsyncMock()
        # 1st completion returns tool calling intent
        # 2nd completion returns the final answered text
        mock_llm.chat_completion.side_effect = [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "type": "function",
                            "function": {
                                "name": "check_order_status",
                                "arguments": '{"order_id": "8888"}',
                            },
                        }
                    ],
                },
            },
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "I checked order 8888. It has Shipped and will arrive in 3 days.",
                },
            },
        ]

        orchestrator = Orchestrator(session_manager, mock_llm, mock_rag)

        response = await orchestrator.process_message(session_id, "Where is my order 8888?")

        assert "I checked order 8888" in response.text
        assert "Shipped" in response.text
        assert response.should_escalate is False
    finally:
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_orchestrator_escalation_by_marker() -> None:
    """Test escalation trigger when assistant returns the specific [ESCALATE] marker."""
    redis_client = FakeRedis(decode_responses=True)
    try:
        session_manager = SessionManager(redis_client)
        session_id = "user_escalation_marker"

        mock_rag = AsyncMock()
        mock_rag.retrieve_context.return_value = []

        mock_llm = AsyncMock()
        mock_llm.chat_completion.return_value = {
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": "[ESCALATE] Let me connect you with a human representative immediately.",
            },
        }

        orchestrator = Orchestrator(session_manager, mock_llm, mock_rag)

        response = await orchestrator.process_message(session_id, "I want to complain!")

        assert response.should_escalate is True
        # Marker should be stripped
        assert "[ESCALATE]" not in response.text
        assert "Let me connect you" in response.text

        # Verify state transitioned to ESCALATED
        session = await session_manager.get_or_create_session(session_id)
        assert session.state == SessionState.ESCALATED
    finally:
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_orchestrator_escalation_by_large_refund() -> None:
    """Test escalation triggered when user executes a refund tool with amount > $500."""
    redis_client = FakeRedis(decode_responses=True)
    try:
        session_manager = SessionManager(redis_client)
        session_id = "user_refund_escalate"

        mock_rag = AsyncMock()
        mock_rag.retrieve_context.return_value = []

        mock_llm = AsyncMock()
        # 1st completion returns initiate_refund tool call for $600
        # 2nd completion returns stop response
        mock_llm.chat_completion.side_effect = [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_refund123",
                            "type": "function",
                            "function": {
                                "name": "initiate_refund",
                                "arguments": '{"order_id": "9999", "reason": "damaged", "amount": 600.0}',
                            },
                        }
                    ],
                },
            },
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "I have initiated the refund for $600.00. Since it is over $500, it requires approval.",
                },
            },
        ]

        orchestrator = Orchestrator(session_manager, mock_llm, mock_rag)

        response = await orchestrator.process_message(session_id, "I want a $600 refund!")

        assert response.should_escalate is True
        assert "$600" in response.text

        session = await session_manager.get_or_create_session(session_id)
        assert session.state == SessionState.ESCALATED
    finally:
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_orchestrator_graceful_fallback() -> None:
    """Test that unhandled client exceptions return a fallback response and escalate gracefully instead of crashing."""
    redis_client = FakeRedis(decode_responses=True)
    try:
        session_manager = SessionManager(redis_client)
        session_id = "user_failure_node"

        mock_rag = AsyncMock()
        mock_rag.retrieve_context.side_effect = Exception("Qdrant connection timed out!")

        mock_llm = AsyncMock()

        orchestrator = Orchestrator(session_manager, mock_llm, mock_rag)

        response = await orchestrator.process_message(session_id, "Hello?")

        assert response.should_escalate is True
        assert "trouble connecting" in response.text
    finally:
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_handle_agent_reply() -> None:
    """Test handling of human agent replies and manual closing workflow transitions."""
    redis_client = FakeRedis(decode_responses=True)
    try:
        session_manager = SessionManager(redis_client)
        # Mock LLM and RAG
        mock_llm = MagicMock()
        mock_rag = MagicMock()

        orchestrator = Orchestrator(session_manager, mock_llm, mock_rag)
        session_id = "agent_reply_session"

        # 1. Agent reply maintaining HANDOFF state
        response = await orchestrator.handle_agent_reply(session_id, "Hello, how can I help you?")
        assert response.text == "Hello, how can I help you?"
        session = await session_manager.get_or_create_session(session_id)
        assert session.state == SessionState.HUMAN_HANDOFF

        # 2. Agent reply closing/resolving the chat state
        await orchestrator.handle_agent_reply(session_id, "Your issue has been resolved. Closing chat.")
        session = await session_manager.get_or_create_session(session_id)
        assert session.state == SessionState.AWAITING_INPUT
    finally:
        await redis_client.aclose()
