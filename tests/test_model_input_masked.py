import pytest

from src.handoff.client import MockZendeskClient
from src.orchestrator.engine import Orchestrator


@pytest.mark.asyncio
async def test_model_step_receives_masked_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Card numbers, emails and phone numbers never reach the model step (they used to be masked in logs only)."""
    seen: list[str] = []
    orchestrator = Orchestrator(handoff_client=MockZendeskClient())
    real_call = orchestrator.call_llm

    async def spy(text: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        seen.append(text)
        return await real_call(text, *args, **kwargs)

    monkeypatch.setattr(orchestrator, "call_llm", spy)
    await orchestrator.handle_message(
        "test-mask-session",
        "My email is john.doe@acme.com and my card is 4532-1188-9922-3344.",
    )

    assert seen, "the model step was not reached"
    assert "4532-1188-9922-3344" not in seen[0]
    assert "john.doe@acme.com" not in seen[0]
    assert "[CARD]" in seen[0] and "[EMAIL]" in seen[0]
