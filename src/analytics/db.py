from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.analytics.models import Base, InteractionMetric
from src.utils.logger import get_logger

logger = get_logger(__name__)

# SQLite database URL for Phase 5 simplicity
DATABASE_URL = "sqlite+aiosqlite:///./analytics.db"

# Create async engine and sessionmaker
async_engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Asynchronously initializes the SQLite database, creating all tables if they do not exist."""
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Successfully initialized the analytics database and tables.")
    except Exception as e:
        logger.exception("Failed to initialize analytics database", error=str(e))


class AnalyticsRecorder:
    """Handles recording interaction performance metrics asynchronously in the database."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        """Initializes the AnalyticsRecorder.

        Args:
            session_factory: Optional async_sessionmaker session factory.
        """
        self.session_factory = session_factory or async_session_maker

    async def record_metric(
        self,
        session_id: str,
        latency_ms: int,
        used_fallback: bool,
        escalated: bool,
        intent: str | None = None,
        llm_model: str | None = None,
        tokens_used: int = 0,
    ) -> None:
        """Asynchronously writes a single InteractionMetric to the database.

        Args:
            session_id: Active conversation session ID.
            latency_ms: Message processing latency in milliseconds.
            used_fallback: True if FallbackEngine processed the query.
            escalated: True if human handoff escalation triggered.
            intent: Optional detected intent name.
            llm_model: Name of the LLM model used.
            tokens_used: Tokens consumed in the generation.
        """
        metric = InteractionMetric(
            session_id=session_id,
            timestamp=datetime.now(UTC).replace(tzinfo=None),
            intent=intent,
            llm_model=llm_model,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            used_fallback=used_fallback,
            escalated=escalated,
        )

        try:
            async with self.session_factory() as session:
                async with session.begin():
                    session.add(metric)
                await session.commit()
            logger.info(
                "Recorded interaction metric",
                session_id=session_id,
                latency_ms=latency_ms,
                fallback=used_fallback,
                escalated=escalated,
            )
        except Exception as e:
            logger.exception("Failed to write interaction metric to database", session_id=session_id, error=str(e))
