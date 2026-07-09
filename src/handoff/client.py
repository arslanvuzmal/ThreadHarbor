from abc import ABC, abstractmethod
from typing import Any

from src.handoff.payload import HandoffPayload
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BaseHandoffClient(ABC):
    """Abstract Base Class for integrating external CCaaS ticketing systems (e.g. Zendesk, Freshdesk)."""

    @abstractmethod
    async def create_ticket(self, session_id: str, payload: HandoffPayload) -> str:
        """Creates a human handoff ticket in the CCaaS system.

        Args:
            session_id: The unique session/user ID.
            payload: The handoff context payload.

        Returns:
            The created ticket ID.
        """
        pass

    @abstractmethod
    async def send_agent_message(self, ticket_id: str, text: str) -> None:
        """Forwards user messages to the CCaaS system so they are visible to the agent.

        Args:
            ticket_id: The active ticket ID.
            text: Raw message content from the user.
        """
        pass

    @abstractmethod
    async def close_ticket(self, ticket_id: str) -> None:
        """Closes the ticket in the CCaaS system.

        Args:
            ticket_id: The active ticket ID.
        """
        pass


class MockZendeskClient(BaseHandoffClient):
    """Mock implementation of the Zendesk ticketing system client.

    Stores all active tickets in-memory and logs actions to simulate database storage.
    """

    def __init__(self) -> None:
        """Initializes the mock client with an empty in-memory tickets database."""
        self.tickets: dict[str, dict[str, Any]] = {}
        self.ticket_counter: int = 1

    async def create_ticket(self, session_id: str, payload: HandoffPayload) -> str:
        """Creates a mock ticket in-memory.

        Args:
            session_id: Unique user session ID.
            payload: Handoff payload.

        Returns:
            Mock ticket ID.
        """
        ticket_id = f"ZENDESK-{self.ticket_counter}"
        self.ticket_counter += 1

        self.tickets[ticket_id] = {
            "session_id": session_id,
            "payload": payload,
            "messages": [],
            "status": "open",
        }

        logger.info(
            "Mock Zendesk ticket created successfully",
            ticket_id=ticket_id,
            session_id=session_id,
            reason=payload.escalation_reason,
        )
        return ticket_id

    async def send_agent_message(self, ticket_id: str, text: str) -> None:
        """Appends the user's message to the mock ticket transcript.

        Args:
            ticket_id: The active mock ticket ID.
            text: The message text.
        """
        if ticket_id not in self.tickets:
            logger.error("Failed to forward agent message: ticket not found", ticket_id=ticket_id)
            raise ValueError(f"Ticket {ticket_id} does not exist")

        self.tickets[ticket_id]["messages"].append(text)
        logger.info("Mock Zendesk ticket updated with user message", ticket_id=ticket_id, text_length=len(text))

    async def close_ticket(self, ticket_id: str) -> None:
        """Sets the mock ticket status to closed.

        Args:
            ticket_id: The active mock ticket ID.
        """
        if ticket_id not in self.tickets:
            logger.error("Failed to close ticket: ticket not found", ticket_id=ticket_id)
            raise ValueError(f"Ticket {ticket_id} does not exist")

        self.tickets[ticket_id]["status"] = "closed"
        logger.info("Mock Zendesk ticket closed successfully", ticket_id=ticket_id)
