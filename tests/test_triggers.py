import pytest

from src.bot.session import SessionData
from src.orchestrator.triggers import EscalationTriggerEngine, SentimentAnalyzer


def test_explicit_intent_trigger() -> None:
    """Tests that explicit keywords trigger pre-LLM escalation."""
    engine = EscalationTriggerEngine()
    session = SessionData(session_id="12345")

    # Explicit phrases
    phrases = ["please connect me to an agent", "human representative", "talk to someone please", "I want to speak with a human"]
    for phrase in phrases:
        triggered, reason = engine.evaluate_pre_llm(phrase, session)
        assert triggered is True
        assert reason == "Explicit Request"

    # Normal phrase
    triggered, reason = engine.evaluate_pre_llm("hello, how are you", session)
    assert triggered is False
    assert reason is None


def test_sentiment_trigger() -> None:
    """Tests that negative sentiment keywords trigger pre-LLM escalation."""
    engine = EscalationTriggerEngine()
    session = SessionData(session_id="12345")

    # Negative phrase
    triggered, reason = engine.evaluate_pre_llm("This is a total scam, I am very angry!", session)
    assert triggered is True
    assert reason == "Sentiment: Negative"

    # Neutral phrase
    triggered, reason = engine.evaluate_pre_llm("Can I check my order status?", session)
    assert triggered is False
    assert reason is None


def test_sentiment_analyzer_direct() -> None:
    """Tests the Mock SentimentAnalyzer scores directly."""
    analyzer = SentimentAnalyzer()
    assert analyzer.analyze("angry scam refund") == -0.8
    assert analyzer.analyze("totally unacceptable behavior") == -0.8
    assert analyzer.analyze("good morning!") == 0.0


def test_loop_detection_repeating_message() -> None:
    """Tests that repeating the same user message twice in a row triggers escalation."""
    engine = EscalationTriggerEngine()
    session = SessionData(session_id="12345")

    # First turn
    session.last_user_message = "where is my refund"
    triggered, reason = engine.evaluate_pre_llm("where is my refund", session)
    assert triggered is True
    assert reason == "Loop Detected"


def test_loop_detection_consecutive_low_confidence() -> None:
    """Tests that 2 consecutive turns of low-confidence LLM responses trigger escalation."""
    engine = EscalationTriggerEngine()
    session = SessionData(session_id="12345")

    # First low-confidence turn
    triggered_1, reason_1 = engine.evaluate_post_llm("I'm not sure about that.", session)
    assert triggered_1 is False
    assert reason_1 is None
    assert session.low_confidence_consecutive_count == 1

    # Second low-confidence turn
    triggered_2, reason_2 = engine.evaluate_post_llm("I don't know the answer.", session)
    assert triggered_2 is True
    assert reason_2 == "Loop Detected"
    assert session.low_confidence_consecutive_count == 2

    # Normal turn resets the counter
    session.low_confidence_consecutive_count = 1
    triggered_3, reason_3 = engine.evaluate_post_llm("Sure, here is your order info.", session)
    assert triggered_3 is False
    assert reason_3 is None
    assert session.low_confidence_consecutive_count == 0


def test_policy_limit_trigger() -> None:
    """Tests that calling initiate_refund tool with amount > 500 triggers escalation."""
    engine = EscalationTriggerEngine()
    session = SessionData(session_id="12345")

    # High refund call
    tool_calls_high = [{"name": "initiate_refund", "arguments": {"amount": 600.0}}]
    triggered_high, reason_high = engine.evaluate_post_llm("Initiating refund.", session, tool_calls_high)
    assert triggered_high is True
    assert reason_high == "Policy Limit"

    # Acceptable refund call
    tool_calls_low = [{"name": "initiate_refund", "arguments": {"amount": 120.0}}]
    triggered_low, reason_low = engine.evaluate_post_llm("Initiating refund.", session, tool_calls_low)
    assert triggered_low is False
    assert reason_low is None
