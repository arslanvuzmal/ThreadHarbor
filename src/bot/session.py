import json
import time
from typing import Any, ClassVar

import redis
from pydantic import BaseModel, Field

from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BotResponse(BaseModel):
    """Encapsulates the text response returned by the Orchestrator."""

    text: str = ""


class SessionData(BaseModel):
    """Data model representing the state and metadata of a user's WhatsApp conversation session."""

    session_id: str
    state: str = "AWAITING_INPUT"  # IDLE, AWAITING_INPUT, PROCESSING, ESCALATED, HUMAN_HANDOFF
    user_profile: dict[str, Any] = Field(
        default_factory=lambda: {"name": "Customer", "phone": "", "tier": "standard"}
    )
    transcript: list[dict[str, Any]] = Field(default_factory=list)

    # Escalation and tracking attributes
    low_confidence_consecutive_count: int = 0
    last_user_message: str | None = None
    ticket_id: str | None = None
    phone_number_id: str | None = None

    # Interaction window tracking (Meta's 24-hour compliance rule)
    last_interaction_timestamp: float = Field(default_factory=time.time)


class RedisSessionStore:
    """Manages storage and retrieval of SessionData using Redis with a 48-hour TTL.

    Falls back to a standard in-memory dictionary if Redis connection is unavailable.
    """
    _fallback_store: ClassVar[dict[str, str]] = {}

    def __init__(self) -> None:
        """Initializes the RedisSessionStore and attempts a connection to Redis."""
        self.settings = get_settings()
        self._redis: redis.Redis | None = None

        try:
            # Type ignore is used because from_url accepts any keyword and we want strict type checking
            self._redis = redis.Redis.from_url(
                self.settings.REDIS_URL,
                decode_responses=True,
            )
            # Ping to verify the connection works
            self._redis.ping()
            logger.info("Successfully connected to Redis session store")
        except Exception as e:
            logger.warning(
                "Redis session store is unavailable; using in-memory fallback",
                error=str(e),
            )
            self._redis = None

    def _get_key(self, session_id: str) -> str:
        """Constructs the Redis key for a given session ID.

        Args:
            session_id: Unique identifier for the user session.

        Returns:
            The prefixed key string.
        """
        return f"wbot:session:{session_id}"

    def get_session(self, session_id: str) -> str | None:
        """Retrieves raw session string from Redis or in-memory fallback.

        Args:
            session_id: Unique identifier for the user session.

        Returns:
            The serialized session JSON string, or None if not found.
        """
        key = self._get_key(session_id)
        if self._redis:
            try:
                res = self._redis.get(key)
                if isinstance(res, bytes):
                    return res.decode("utf-8")
                return res
            except Exception as e:
                logger.error("Failed to get session from Redis, checking fallback", error=str(e))

        return self._fallback_store.get(key)

    def save_session(self, session_id: str, data_str: str, ttl_seconds: int = 172800) -> None:
        """Saves a session's serialized data with a 48-hour TTL.

        Args:
            session_id: Unique identifier for the user session.
            data_str: Serialized JSON string of SessionData.
            ttl_seconds: TTL for the session key in seconds (defaults to 172800 / 48 hours).
        """
        key = self._get_key(session_id)
        if self._redis:
            try:
                self._redis.setex(key, ttl_seconds, data_str)
                return
            except Exception as e:
                logger.error("Failed to save session to Redis, writing to fallback", error=str(e))

        self._fallback_store[key] = data_str


class SessionManager:
    """Provides high-level session check and lifecycle utilities."""

    _store_instance = RedisSessionStore()

    @classmethod
    def is_within_24h_window(cls, session_id: str) -> bool:
        """Checks whether the session is inside the 24-hour active interaction window.

        Args:
            session_id: The session ID of the user.

        Returns:
            bool: True if within the 24-hour window, otherwise False.
        """
        raw_session = cls._store_instance.get_session(session_id)
        if not raw_session:
            return True

        try:
            data = json.loads(raw_session)
            last_timestamp = data.get("last_interaction_timestamp")
            if last_timestamp is None:
                return True
            return (time.time() - float(last_timestamp)) < 86400
        except Exception as e:
            logger.error("Failed to evaluate 24h window, default to True", error=str(e))
            return True
