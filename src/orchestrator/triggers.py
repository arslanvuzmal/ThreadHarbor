import json
from typing import Any

from src.bot.session import SessionData
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SentimentAnalyzer:
    """Mock sentiment analyzer for evaluating user message sentiment based on simple keyword matches."""

    def analyze(self, text: str) -> float:
        """Analyzes the given text and returns a sentiment score between -1.0 (most negative) and 1.0 (most positive).

        If keywords like "angry", "unacceptable", "scam", or "refund" are matched, returns -0.8.
        Otherwise, returns 0.0 (neutral).

        Args:
            text: Plain text to analyze.

        Returns:
            Sentiment score float.
        """
        text_lower = text.lower()
        keywords = ["angry", "unacceptable", "scam", "refund"]
        if any(kw in text_lower for kw in keywords):
            logger.debug("Negative sentiment detected via keyword match", text=text)
            return -0.8
        return 0.0


class EscalationTriggerEngine:
    """Evaluates various pre-LLM and post-LLM triggers to determine if a chat session should be escalated."""

    def __init__(self, sentiment_analyzer: SentimentAnalyzer | None = None) -> None:
        """Initializes the EscalationTriggerEngine.

        Args:
            sentiment_analyzer: Optional SentimentAnalyzer instance.
        """
        self.sentiment_analyzer = sentiment_analyzer or SentimentAnalyzer()

    def evaluate_pre_llm(self, text: str, session: SessionData) -> tuple[bool, str | None]:
        """Evaluates triggers before calling the LLM.

        Checks for:
        1. Explicit Intent: Keywords like "agent", "human", "representative", "talk to someone".
        2. Loop Detection: User repeats the exact same message twice in a row.
        3. Sentiment: Negative sentiment score (< -0.5).

        Args:
            text: User's raw text message.
            session: Current SessionData object.

        Returns:
            A tuple of (escalation_triggered: bool, escalation_reason: Optional[str]).
        """
        text_lower = text.lower()

        # 1. Explicit Intent
        explicit_keywords = ["agent", "human", "representative", "talk to someone"]
        if any(kw in text_lower for kw in explicit_keywords):
            return True, "Explicit Request"

        # 2. Loop Detection (User repeats the exact same message twice in a row)
        if session.last_user_message and session.last_user_message.strip() == text.strip():
            return True, "Loop Detected"

        # 3. Sentiment Analysis Check
        sentiment_score = self.sentiment_analyzer.analyze(text)
        if sentiment_score < -0.5:
            return True, "Sentiment: Negative"

        return False, None

    def evaluate_post_llm(
        self,
        llm_response_text: str,
        session: SessionData,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> tuple[bool, str | None]:
        """Evaluates triggers during/after calling the LLM.

        Checks for:
        1. Low confidence detection: LLM response contains "I don't know" or "I'm not sure".
           If this occurs for 2 consecutive turns, it triggers escalation.
        2. Policy limit check: Tool calls to "initiate_refund" with an amount > $500.

        Args:
            llm_response_text: Text response returned by the LLM.
            session: Current SessionData object.
            tool_calls: Optional list of tool/function calls made by the LLM.

        Returns:
            A tuple of (escalation_triggered: bool, escalation_reason: Optional[str]).
        """
        # 1. Low Confidence Detection (contains "I don't know" or "I'm not sure" case-insensitive)
        response_lower = llm_response_text.lower()
        is_low_confidence = "i don't know" in response_lower or "i'm not sure" in response_lower

        if is_low_confidence:
            session.low_confidence_consecutive_count += 1
            logger.info(
                "Low confidence LLM response detected",
                consecutive_count=session.low_confidence_consecutive_count,
            )
        else:
            session.low_confidence_consecutive_count = 0

        if session.low_confidence_consecutive_count >= 2:
            return True, "Loop Detected"

        # 2. Policy limit check
        if tool_calls:
            for call in tool_calls:
                name = call.get("name") or call.get("function", {}).get("name")
                if name == "initiate_refund":
                    # Arguments can be a dict or serialized JSON string
                    args = call.get("arguments") or call.get("function", {}).get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}

                    amount = args.get("amount")
                    if amount is not None:
                        try:
                            amount_val = float(amount)
                            if amount_val > 500.0:
                                return True, "Policy Limit"
                        except (ValueError, TypeError):
                            pass

        return False, None
