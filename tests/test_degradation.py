import asyncio
import pytest
from sqlalchemy import select

from src.analytics.db import async_session_maker, init_db
from src.analytics.models import InteractionMetric
from src.handoff.client import MockZendeskClient
from src.orchestrator.engine import Orchestrator


@pytest.mark.asyncio
async def test_orchestrator_graceful_degradation() -> None:
    """Tests that any processing exception triggers FallbackEngine gracefully without crashing and records used_fallback in DB."""
    # Ensure database is initialized
    await init_db()

    client = MockZendeskClient()
    orchestrator = Orchestrator(handoff_client=client)

    session_id = "test-degrade-session"
    user_input = "force error of the LLM"

    # Call orchestrator with text that forces an error
    response = await orchestrator.handle_message(session_id, user_input)

    # Assert it did not crash and returned the Fallback Engine's default failure message
    assert response.text == "I'm experiencing technical difficulties. Let me connect you to a human specialist."

    # Give a tiny slice of time for the background task to execute
    await asyncio.sleep(0.1)

    # Assert that used_fallback was recorded in the database
    async with async_session_maker() as session:
        result = await session.execute(
            select(InteractionMetric)
            .where(InteractionMetric.session_id == session_id)
            .order_by(InteractionMetric.id.desc())
        )
        metric = result.scalars().first()

        assert metric is not None
        assert metric.session_id == session_id
        assert metric.used_fallback is True
        assert metric.escalated is True
        assert metric.intent == "degraded_escalation"
