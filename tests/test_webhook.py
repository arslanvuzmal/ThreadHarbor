import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
import respx
from fakeredis.aioredis import FakeRedis
from fastapi.testclient import TestClient
from httpx import Response

from src.utils.config import Settings


def test_get_webhook_success(client: TestClient, app_settings: Settings) -> None:
    """Test GET /webhook with correct verify token returns challenge."""
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": app_settings.WHATSAPP_VERIFY_TOKEN,
            "hub.challenge": "1158201444",
        },
    )
    assert response.status_code == 200
    assert response.text == "1158201444"


def test_get_webhook_wrong_token(client: TestClient) -> None:
    """Test GET /webhook with wrong token returns 403."""
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "1158201444",
        },
    )
    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": 403,
            "message": "Verification failed: Invalid token or mode",
        }
    }


def test_get_webhook_missing_params(client: TestClient) -> None:
    """Test GET /webhook with missing params returns 403."""
    response = client.get("/webhook")
    assert response.status_code == 403


@pytest.mark.asyncio
@respx.mock
async def test_post_webhook_valid_text_message(
    client: TestClient,
    signature_generator: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test POST /webhook immediately returns 200 and triggers background tasks."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15555555555",
                                "phone_number_id": "1234567890",
                            },
                            "contacts": [{"profile": {"name": "John Doe"}, "wa_id": "16505551234"}],
                            "messages": [
                                {
                                    "from": "16505551234",
                                    "id": "wamid.HBgLMTY1MDU1NTEyMzQVAgARGBI5OEVCRDY1NUZDMEYwN0FFN0EA",
                                    "timestamp": "1650555123",
                                    "text": {
                                        "body": "Hello! My email is john@example.com and phone is +1-555-555-5555"
                                    },
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    body_bytes = json.dumps(payload).encode("utf-8")
    signature = signature_generator(body_bytes)

    # Mock outbound Graph API call
    route = respx.post("https://graph.facebook.com/v21.0/1234567890/messages").mock(
        return_value=Response(200, json={"message_id": "wamid.mocked"})
    )

    # Mock LLM and RAG Pipeline
    import src.intelligence.llm_client
    import src.intelligence.rag

    mock_llm_call = AsyncMock(return_value={
        "finish_reason": "stop",
        "message": {
            "role": "assistant",
            "content": "Mock text response from chatbot AI.",
        }
    })
    monkeypatch.setattr(src.intelligence.llm_client.LLMClient, "chat_completion", mock_llm_call)

    # Mock RAG retrieve_context
    mock_rag_call = AsyncMock(return_value=[{"text": "mock context chunk"}])
    monkeypatch.setattr(src.intelligence.rag.RAGPipeline, "retrieve_context", mock_rag_call)

    # Use FakeRedis to back our route handler
    import redis.asyncio as aioredis
    original_from_url = aioredis.from_url
    fake_redis = FakeRedis(decode_responses=True)

    def mock_from_url(*_args: Any, **_kwargs: Any) -> Any:
        return fake_redis

    aioredis.from_url = mock_from_url

    try:
        response = client.post(
            "/webhook",
            content=body_bytes,
            headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "success"}

        # Verify that background tasks executed successfully with the mocked endpoints
        assert mock_llm_call.called
        assert mock_rag_call.called
        assert route.called
    finally:
        aioredis.from_url = original_from_url
        await fake_redis.aclose()


def test_post_webhook_invalid_signature(client: TestClient) -> None:
    """Test POST /webhook with invalid signature returns 401."""
    payload = {"some": "data"}
    body_bytes = json.dumps(payload).encode("utf-8")

    response = client.post(
        "/webhook",
        content=body_bytes,
        headers={"X-Hub-Signature-256": "sha256=invalid", "Content-Type": "application/json"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": 401,
            "message": "Invalid signature",
        }
    }


def test_post_webhook_empty_body(client: TestClient, signature_generator: Any) -> None:
    """Test POST /webhook with empty body returns 400."""
    body_bytes = b""
    signature = signature_generator(body_bytes)

    response = client.post(
        "/webhook",
        content=body_bytes,
        headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": 400,
            "message": "Empty payload body",
        }
    }


def test_post_webhook_status_update(
    client: TestClient,
    signature_generator: Any,
) -> None:
    """Test POST /webhook with status update (no message) returns 200 and does not crash."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15555555555",
                                "phone_number_id": "1234567890",
                            },
                            "statuses": [
                                {
                                    "id": "wamid.HBgLMTY1MDU1NTEyMzQVAgARGBI5OEVCRDY1NUZDMEYwN0FFN0EA",
                                    "status": "delivered",
                                    "timestamp": "1650555124",
                                    "recipient_id": "16505551234",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    body_bytes = json.dumps(payload).encode("utf-8")
    signature = signature_generator(body_bytes)

    response = client.post(
        "/webhook",
        content=body_bytes,
        headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success"}


@pytest.mark.asyncio
@respx.mock
async def test_post_webhook_interactive_message(
    client: TestClient,
    signature_generator: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test POST /webhook with valid interactive message returns 200."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15555555555",
                                "phone_number_id": "1234567890",
                            },
                            "messages": [
                                {
                                    "from": "16505551234",
                                    "id": "wamid.HBgLMTY1MDU1NTEyMzQVAgARGBI5OEVCRDY1NUZDMEYwN0FFN0EA",
                                    "timestamp": "1650555123",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {"id": "button_1", "title": "Yes"},
                                    },
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    body_bytes = json.dumps(payload).encode("utf-8")
    signature = signature_generator(body_bytes)

    # Mock outbound Graph API call
    route = respx.post("https://graph.facebook.com/v21.0/1234567890/messages").mock(
        return_value=Response(200, json={"message_id": "wamid.mocked"})
    )

    # Mock LLM and RAG Pipeline
    import src.intelligence.llm_client
    import src.intelligence.rag

    mock_llm_call = AsyncMock(return_value={
        "finish_reason": "stop",
        "message": {
            "role": "assistant",
            "content": "Interactive selected item response details.",
        }
    })
    monkeypatch.setattr(src.intelligence.llm_client.LLMClient, "chat_completion", mock_llm_call)

    mock_rag_call = AsyncMock(return_value=[])
    monkeypatch.setattr(src.intelligence.rag.RAGPipeline, "retrieve_context", mock_rag_call)

    import redis.asyncio as aioredis
    original_from_url = aioredis.from_url
    fake_redis = FakeRedis(decode_responses=True)

    def mock_from_url(*_args: Any, **_kwargs: Any) -> Any:
        return fake_redis

    aioredis.from_url = mock_from_url

    try:
        response = client.post(
            "/webhook",
            content=body_bytes,
            headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "success"}

        assert mock_llm_call.called
        assert mock_rag_call.called
        assert route.called
    finally:
        aioredis.from_url = original_from_url
        await fake_redis.aclose()
