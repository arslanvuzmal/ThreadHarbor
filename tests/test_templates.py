import time

import pytest
import respx

from src.api.routes.webhook import process_incoming_message
from src.handoff.client import MockZendeskClient
from src.orchestrator.engine import Orchestrator
from src.utils.whatsapp_templates import TemplateManager


@pytest.mark.asyncio
async def test_template_manager_send() -> None:
    """Tests that TemplateManager properly constructs the template schema payload and sends it via HTTP."""
    manager = TemplateManager()
    recipient = "1234567890"

    # Use respx to mock Graph API
    with respx.mock:
        respx.post("https://graph.facebook.com/v21.0/default_phone_number_id/messages").respond(
            status_code=200,
            json={"messaging_product": "whatsapp", "messages": [{"id": "msg_id_123"}]},
        )

        resp = await manager.send_template_message(recipient, "order_update")
        assert resp.get("messages") is not None
        assert resp["messages"][0]["id"] == "msg_id_123"


@pytest.mark.asyncio
async def test_24h_window_expired_sends_template() -> None:
    """Tests that process_incoming_message checks 24h window and fallbacks to template message instead of free-text."""
    client = MockZendeskClient()
    orchestrator = Orchestrator(handoff_client=client)

    sender_wa_id = "test-expired-user"
    phone_number_id = "test-phone-id"

    # Seed an expired session state in the store (last interaction was 25 hours ago / 90000 seconds)
    session = await orchestrator.get_or_create_session(sender_wa_id)
    session.last_interaction_timestamp = time.time() - 90000
    await orchestrator.save_session(session)

    # Use respx to mock the template sending
    with respx.mock:
        # Mock template dispatch GET/POST
        respx.post(f"https://graph.facebook.com/v21.0/{phone_number_id}/messages").respond(
            status_code=200,
            json={"status": "sent", "type": "template"},
        )

        # Call process_incoming_message (background task)
        # Checks window expiration and falls back to template message.
        from fastapi import BackgroundTasks
        bg = BackgroundTasks()

        import httpx
        http_client = httpx.AsyncClient()

        await process_incoming_message(
            sender_wa_id=sender_wa_id,
            phone_number_id=phone_number_id,
            text_content="Hello, can you help me?",
            orchestrator=orchestrator,
            access_token="test-token",
            background_tasks=bg,
            http_client=http_client,
        )

        # Verify that the correct template payload was sent over HTTP
        assert len(respx.calls) > 0
        last_request = respx.calls[-1].request
        import json
        req_body = json.loads(last_request.content.decode("utf-8"))

        # Verify strict compliance
        assert req_body["type"] == "template"
        assert req_body["template"]["name"] == "order_update_01"

        # Verify that session is updated with current timestamp for the incoming message
        session_post = await orchestrator.get_or_create_session(sender_wa_id)
        assert abs(session_post.last_interaction_timestamp - time.time()) < 10.0
