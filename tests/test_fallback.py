from src.orchestrator.fallback import FallbackEngine


def test_fallback_engine_keywords() -> None:
    """Tests that FallbackEngine processes static keywords to exact responses and flags."""
    engine = FallbackEngine()

    # 1. Hours match
    response, escalated = engine.process("what are your working hours?")
    assert "9 AM - 5 PM EST" in response.text
    assert escalated is False

    response, escalated = engine.process("Are you guys open now?")
    assert "9 AM - 5 PM EST" in response.text
    assert escalated is False

    # 2. Refund match
    response, escalated = engine.process("How can I initiate a refund?")
    assert "returns portal" in response.text
    assert escalated is False

    # 3. Agent match (triggers escalation)
    response, escalated = engine.process("please let me talk to an agent")
    assert "connecting you to a human" in response.text
    assert escalated is True


def test_fallback_engine_default_unmatched() -> None:
    """Tests that unmatched messages under FallbackEngine degrade to default escalation."""
    engine = FallbackEngine()

    # Default unmatched
    response, escalated = engine.process("can you tell me a story about a dragon?")
    assert "experiencing technical difficulties" in response.text
    assert escalated is True
