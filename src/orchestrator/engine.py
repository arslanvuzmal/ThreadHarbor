from src.bot.models import BotResponse, Role, SessionState
from src.bot.session import SessionManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Orchestrator:
    """Manages conversational state transition logic, user request routing, and human-in-the-loop handoff."""

    def __init__(self, session_manager: SessionManager) -> None:
        """Initialize the Orchestrator with a SessionManager."""
        self.session_manager = session_manager

    async def process_message(self, session_id: str, user_input: str) -> BotResponse:
        """Processes an incoming user message, transitions the conversational state, and returns a response.

        Args:
            session_id: The ID of the session.
            user_input: The raw message string sent by the user.

        Returns:
            A BotResponse model instance containing text, optional buttons, and escalation flags.
        """
        # 1. Fetch current session
        session = await self.session_manager.get_or_create_session(session_id)
        old_state = session.state

        # If user was human handoff, skip processing or route to human
        if old_state == SessionState.HUMAN_HANDOFF:
            return BotResponse(
                text="A customer support representative will assist you shortly.",
                should_escalate=False,
            )

        # 2. Add user input to history
        await self.session_manager.add_message(session_id, Role.USER, user_input)

        # 3. Transition to PROCESSING state
        session.state = SessionState.PROCESSING
        logger.info(
            "Session state transition",
            session_id=session_id,
            old_state=old_state,
            new_state=session.state,
        )

        # 4. Phase 2 Dummy Intelligence keyword routing check
        cleaned_input = user_input.lower()
        should_escalate = False
        response_text = ""

        if any(keyword in cleaned_input for keyword in ["agent", "human", "refund"]):
            should_escalate = True
            session.state = SessionState.ESCALATED
            response_text = "I am escalating your request to a human representative. Someone will assist you shortly."
            logger.info(
                "Session state transition (Escalation triggered)",
                session_id=session_id,
                old_state=old_state,
                new_state=session.state,
            )
        else:
            session.state = SessionState.AWAITING_INPUT
            response_text = f"I am processing your request: {user_input}. (AI will be added in Phase 3)"
            logger.info(
                "Session state transition",
                session_id=session_id,
                old_state=old_state,
                new_state=session.state,
            )

        # 5. Add bot message to history
        await self.session_manager.add_message(session_id, Role.BOT, response_text)

        # 6. Save final session state (since add_message loads and updates, we set state specifically)
        session = await self.session_manager.get_or_create_session(session_id)
        if should_escalate:
            session.state = SessionState.ESCALATED
        else:
            session.state = SessionState.AWAITING_INPUT
        await self.session_manager.update_session(session)

        # 7. Return response
        return BotResponse(
            text=response_text,
            buttons=None,
            should_escalate=should_escalate,
        )

    async def handle_agent_reply(self, session_id: str, agent_message: str) -> BotResponse:
        """Process a reply sent by a human agent back to the user.

        Transitions state based on agent action or keeps HUMAN_HANDOFF active.

        Args:
            session_id: The ID of the session.
            agent_message: The message sent by the agent.

        Returns:
            A BotResponse containing the agent's reply.
        """
        # Fetch current state
        session = await self.session_manager.get_or_create_session(session_id)

        # Determine next state
        old_state = session.state
        if "close" in agent_message.lower() or "resolve" in agent_message.lower():
            session.state = SessionState.AWAITING_INPUT
        else:
            session.state = SessionState.HUMAN_HANDOFF

        logger.info(
            "Agent message transition",
            session_id=session_id,
            from_state=old_state.name,
            to_state=session.state.name,
        )

        # Save session state changes
        await self.session_manager.update_session(session)

        # Add the agent message to history
        await self.session_manager.add_message(session_id, Role.SYSTEM, f"Agent: {agent_message}")

        return BotResponse(
            text=agent_message,
            buttons=None,
            should_escalate=False,
        )
