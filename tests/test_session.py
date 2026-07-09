from datetime import UTC, datetime, timedelta

import pytest
from fakeredis.aioredis import FakeRedis

from src.bot.models import Role, SessionState
from src.bot.session import SessionManager


@pytest.mark.asyncio
async def test_session_creation_and_retrieval() -> None:
    """Test that get_or_create_session creates a session if not exists, and retrieves it if exists."""
    redis_client = FakeRedis(decode_responses=True)
    try:
        manager = SessionManager(redis_client)
        session_id = "test_user_1"

        # Check not exists -> creates default
        session = await manager.get_or_create_session(session_id)
        assert session.session_id == session_id
        assert session.state == SessionState.IDLE
        assert len(session.history) == 0

        # Retrieve again -> should be the same
        session2 = await manager.get_or_create_session(session_id)
        assert session2.session_id == session_id
        assert session2.state == SessionState.IDLE
    finally:
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_session_update_and_ttl() -> None:
    """Test that update_session correctly persists state changes and sets TTL."""
    redis_client = FakeRedis(decode_responses=True)
    try:
        manager = SessionManager(redis_client, ttl_seconds=10)
        session_id = "test_user_2"

        session = await manager.get_or_create_session(session_id)
        session.state = SessionState.PROCESSING
        session.metadata = {"key": "val"}

        await manager.update_session(session)

        retrieved = await manager.get_or_create_session(session_id)
        assert retrieved.state == SessionState.PROCESSING
        assert retrieved.metadata == {"key": "val"}

        # Verify TTL is set
        ttl = await redis_client.ttl(f"wbot:session:{session_id}")
        assert 0 < ttl <= 10
    finally:
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_add_message() -> None:
    """Test appending messages to a session's conversational history."""
    redis_client = FakeRedis(decode_responses=True)
    try:
        manager = SessionManager(redis_client)
        session_id = "test_user_3"

        await manager.add_message(session_id, Role.USER, "Hello!")
        await manager.add_message(session_id, Role.BOT, "Hi there!")

        session = await manager.get_or_create_session(session_id)
        assert len(session.history) == 2
        assert session.history[0].role == Role.USER
        assert session.history[0].content == "Hello!"
        assert session.history[1].role == Role.BOT
        assert session.history[1].content == "Hi there!"
    finally:
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_is_within_24h_window() -> None:
    """Test 24-hour window validation logic for WhatsApp free-form messages."""
    redis_client = FakeRedis(decode_responses=True)
    try:
        manager = SessionManager(redis_client)
        session_id = "test_user_4"

        # 1. New session (no user history) -> treated as within 24h of creation (default current time)
        assert await manager.is_within_24h_window(session_id) is True

        # 2. Add USER message just now -> within 24h
        await manager.add_message(session_id, Role.USER, "Just spoke")
        assert await manager.is_within_24h_window(session_id) is True

        # 3. Modify USER message timestamp in database to be 25 hours ago -> outside 24h window
        session = await manager.get_or_create_session(session_id)
        session.history[0].timestamp = datetime.now(UTC) - timedelta(hours=25)
        await manager.update_session(session)

        assert await manager.is_within_24h_window(session_id) is False

        # 4. Add a new USER message now -> back within 24h window
        await manager.add_message(session_id, Role.USER, "Back again")
        assert await manager.is_within_24h_window(session_id) is True
    finally:
        await redis_client.aclose()
