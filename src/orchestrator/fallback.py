
from src.bot.session import BotResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FallbackEngine:
    """A rule-based, non-AI fallback decision tree for graceful degradation when LLM services are offline."""

    def process(self, user_input: str) -> tuple[BotResponse, bool]:
        """Evaluates user input against a hardcoded decision tree.

        Args:
            user_input: Raw message text from the user.

        Returns:
            A tuple containing (BotResponse, escalated: bool).
            If escalated is True, the Orchestrator should trigger human agent handoff.
        """
        text_lower = user_input.lower()

        # 1. Hours query
        if "hours" in text_lower or "open" in text_lower:
            logger.info("Fallback matched rule: Hours query")
            return BotResponse(text="Our support hours are 9 AM - 5 PM EST."), False

        # 2. Refund query
        if "refund" in text_lower or "return" in text_lower:
            logger.info("Fallback matched rule: Refund query")
            return (
                BotResponse(text="Please visit our returns portal at [link] or I can connect you to an agent."),
                False,
            )

        # 3. Explicit Agent request
        if "agent" in text_lower or "human" in text_lower:
            logger.info("Fallback matched rule: Explicit agent request")
            return BotResponse(text="I'm connecting you to a human specialist. Please hold."), True

        # 4. Default fallback (system failure / technical difficulties)
        logger.info("Fallback falling back to default system failure response")
        return (
            BotResponse(
                text="I'm experiencing technical difficulties. Let me connect you to a human specialist."
            ),
            True,
        )
