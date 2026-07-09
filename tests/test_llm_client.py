from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.intelligence.llm_client import LLMClient


@pytest.mark.asyncio
async def test_llm_client_chat_completion() -> None:
    """Test standard Chat Completions from OpenAI Async SDK."""
    # Build wrapper
    client = LLMClient(api_key="test_key_abc")

    # Structure mock response
    mock_choice = MagicMock()
    mock_choice.finish_reason = "stop"
    mock_choice.message.role = "assistant"
    mock_choice.message.content = "Response message text info."
    mock_choice.message.tool_calls = None

    mock_res = MagicMock()
    mock_res.choices = [mock_choice]

    # Patch AsyncOpenAI chat completions create endpoint
    with patch.object(client.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_res

        messages = [{"role": "user", "content": "Hello!"}]
        result = await client.chat_completion(messages)

        assert result["finish_reason"] == "stop"
        assert result["message"]["role"] == "assistant"
        assert result["message"]["content"] == "Response message text info."
        mock_create.assert_called_once_with(model="gpt-4o-mini", messages=messages)


@pytest.mark.asyncio
async def test_llm_client_get_embedding() -> None:
    """Test generating embeddings from OpenAI Async SDK."""
    client = LLMClient(api_key="test_key_abc")

    # Structure mock response
    mock_data = MagicMock()
    mock_data.embedding = [0.1, 0.2, 0.3, 0.4]

    mock_res = MagicMock()
    mock_res.data = [mock_data]

    with patch.object(client.client.embeddings, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_res

        vector = await client.get_embedding("sample text to embed")

        assert vector == [0.1, 0.2, 0.3, 0.4]
        mock_create.assert_called_once_with(model="text-embedding-3-small", input="sample text to embed")
