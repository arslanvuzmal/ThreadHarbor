import json

import httpx
import pytest
import respx

from src.handoff.payload import generate_summary


@pytest.mark.asyncio
@respx.mock
async def test_summary_request_to_openai_is_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    """The handoff summary is the one real model call; it must not carry card numbers or emails."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "Summary."}}]})
    )
    await generate_summary(
        [{"role": "user", "content": "My email is john.doe@acme.com and my card is 4532-1188-9922-3344."}]
    )
    sent = json.loads(route.calls.last.request.content)["messages"][1]["content"]
    assert "4532-1188-9922-3344" not in sent
    assert "john.doe@acme.com" not in sent
    assert "[CARD]" in sent and "[EMAIL]" in sent
