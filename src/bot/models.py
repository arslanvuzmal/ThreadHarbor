from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Role(StrEnum):
    """The role of the message sender."""

    USER = "USER"
    BOT = "BOT"
    SYSTEM = "SYSTEM"


class SessionState(StrEnum):
    """The state of the user conversation session."""

    IDLE = "IDLE"
    AWAITING_INPUT = "AWAITING_INPUT"
    PROCESSING = "PROCESSING"
    ESCALATED = "ESCALATED"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"


class Message(BaseModel):
    """A single message structure in the conversation history."""

    role: Role
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionData(BaseModel):
    """Conversation session details stored in Redis."""

    session_id: str
    state: SessionState = SessionState.IDLE
    history: list[Message] = Field(default_factory=list)
    last_interaction_time: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BotResponse(BaseModel):
    """Response returned by the Orchestrator."""

    text: str
    buttons: list[dict[str, Any]] | None = None
    should_escalate: bool = False
