import json
from datetime import UTC, datetime

from redis.asyncio import Redis

from src.bot.models import Message, Role, SessionData, SessionState
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SessionManager:
    """Manages user sessions asynchronously using Redis, handling data persistence and TTL."""

    def __init__(self, redis_client: Redis, ttl_seconds: int = 172800) -> None:
        """Initialize SessionManager with redis client and ttl (default 48h)."""
        self.redis = redis_client
        self.ttl = ttl_seconds

    def _get_key(self, session_id: str) -> str:
        """Generate prefix-based Redis key to avoid collisions."""
        return f"wbot:session:{session_id}"

    async def get_or_create_session(self, session_id: str) -> SessionData:
        """Fetches the session from Redis. If it doesn't exist, creates and saves a new one."""
        key = self._get_key(session_id)
        data = await self.redis.get(key)
        if data:
            try:
                raw_dict = json.loads(data)
                return SessionData.model_validate(raw_dict)
            except Exception as e:
                logger.error("Failed to parse session data from Redis", session_id=session_id, error=str(e))

        # Create new session if not found or malformed
        logger.info("Creating new session in Redis", session_id=session_id)
        new_session = SessionData(
            session_id=session_id,
            state=SessionState.IDLE,
            history=[],
            last_interaction_time=datetime.now(UTC),
            metadata={},
        )
        await self.update_session(new_session)
        return new_session

    async def update_session(self, session_data: SessionData) -> None:
        """Saves the session state back to Redis and sets the TTL."""
        key = self._get_key(session_data.session_id)
        # Convert model to json using Pydantic's serialization
        serialized_data = session_data.model_dump_json()
        await self.redis.set(key, serialized_data, ex=self.ttl)
        logger.debug("Updated session in Redis", session_id=session_data.session_id, state=session_data.state)

    async def add_message(self, session_id: str, role: Role, content: str) -> None:
        """Appends a message to session history, updates last interaction time, and persists it."""
        session = await self.get_or_create_session(session_id)
        new_message = Message(role=role, content=content, timestamp=datetime.now(UTC))
        session.history.append(new_message)
        session.last_interaction_time = datetime.now(UTC)
        await self.update_session(session)

    async def is_within_24h_window(self, session_id: str) -> bool:
        """Checks if the user's last interaction was within the 24-hour window."""
        session = await self.get_or_create_session(session_id)
        # Find the last message sent by the USER (free-form messages are restricted within 24h of user's last message)
        last_user_time: datetime | None = None
        for msg in reversed(session.history):
            if msg.role == Role.USER:
                last_user_time = msg.timestamp
                break

        # If user has never spoken, treat as outside window or use session creation time as fallback
        if not last_user_time:
            last_user_time = session.last_interaction_time

        # Ensure timezone-aware comparison
        if last_user_time.tzinfo is None:
            last_user_time = last_user_time.replace(tzinfo=UTC)

        current_time = datetime.now(UTC)
        difference = current_time - last_user_time
        return difference.total_seconds() <= 86400
