import pytest
from sqlalchemy import select

from src.analytics.db import AnalyticsRecorder, async_session_maker, init_db
from src.analytics.models import InteractionMetric


@pytest.mark.asyncio
async def test_analytics_recorder_insert() -> None:
    """Tests that AnalyticsRecorder correctly inserts metric rows into the SQLite analytics database."""
    # Ensure database is initialized
    await init_db()

    recorder = AnalyticsRecorder()
    session_id = "test-analytics-session"

    # Write a mock metric
    await recorder.record_metric(
        session_id=session_id,
        latency_ms=150,
        used_fallback=False,
        escalated=False,
        intent="test_intent",
        llm_model="gpt-4o-mini",
        tokens_used=50,
    )

    # Assert the metric is persisted and matches
    async with async_session_maker() as session:
        result = await session.execute(
            select(InteractionMetric)
            .where(InteractionMetric.session_id == session_id)
            .order_by(InteractionMetric.id.desc())
        )
        metric = result.scalars().first()

        assert metric is not None
        assert metric.session_id == session_id
        assert metric.latency_ms == 150
        assert metric.used_fallback is False
        assert metric.escalated is False
        assert metric.intent == "test_intent"
        assert metric.llm_model == "gpt-4o-mini"
        assert metric.tokens_used == 50
        assert metric.timestamp is not None
