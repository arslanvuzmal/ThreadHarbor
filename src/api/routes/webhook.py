import json
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from src.api.dependencies import get_app_settings, get_handoff_client
from src.handoff.client import BaseHandoffClient
from src.orchestrator.engine import Orchestrator
from src.utils import pii_masker
from src.utils.config import Settings
from src.utils.logger import get_logger
from src.utils.whatsapp_signature import verify_signature

logger = get_logger(__name__)

router = APIRouter()


def get_orchestrator(
    handoff_client: BaseHandoffClient = Depends(get_handoff_client),  # noqa: B008
) -> Orchestrator:
    """Dependency to provide the shared Orchestrator instance.

    Args:
        handoff_client: BaseHandoffClient instance.

    Returns:
        Orchestrator instance.
    """
    return Orchestrator(handoff_client=handoff_client)


async def process_incoming_message(
    sender_wa_id: str,
    phone_number_id: str,
    text_content: str,
    orchestrator: Orchestrator,
    access_token: str,
    background_tasks: BackgroundTasks,
) -> None:
    """Background task to handle user messages through the Orchestrator.

    Avoids blocking the HTTP response thread.

    Args:
        sender_wa_id: The WhatsApp ID of the sender.
        phone_number_id: The phone number ID from Meta's webhook.
        text_content: Message text.
        orchestrator: The Orchestrator engine.
        access_token: WhatsApp Access Token.
        background_tasks: FastAPI BackgroundTasks runner.
    """
    try:
        # Load and update session with correct phone_number_id
        session = await orchestrator.get_or_create_session(sender_wa_id)
        session.phone_number_id = phone_number_id
        await orchestrator.save_session(session)

        # Handle message in orchestrator
        bot_response = await orchestrator.handle_message(sender_wa_id, text_content, background_tasks)

        # If there is response text, send it back via Meta API
        if bot_response.text:
            await send_whatsapp_reply(
                phone_number_id=phone_number_id,
                to=sender_wa_id,
                text_body=bot_response.text,
                access_token=access_token,
            )
    except Exception as e:
        logger.exception("Error processing incoming message in background", error=str(e))


async def send_whatsapp_reply(
    phone_number_id: str,
    to: str,
    text_body: str,
    access_token: str,
) -> None:
    """Asynchronously sends a reply back to WhatsApp using the Graph API.

    Args:
        phone_number_id: The WhatsApp Phone Number ID extracted from payload.
        to: The sender's WhatsApp ID (wa_id).
        text_body: The reply text to send.
        access_token: The WHATSAPP_ACCESS_TOKEN configuration.
    """
    url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": text_body},
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(
                "WhatsApp reply sent successfully",
                phone_number_id=phone_number_id,
                to=to,
                status_code=response.status_code,
            )
    except Exception as e:
        logger.error(
            "Failed to send WhatsApp reply",
            phone_number_id=phone_number_id,
            to=to,
            error=str(e),
        )


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    settings: Settings = Depends(get_app_settings),  # noqa: B008
) -> str:
    """Meta Webhook Verification GET endpoint.

    Args:
        hub_mode: The hub.mode query parameter.
        hub_verify_token: The hub.verify_token query parameter.
        hub_challenge: The hub.challenge query parameter.
        settings: Application Settings containing VERIFY_TOKEN.

    Returns:
        The challenge token if valid, otherwise raises a 403 HTTP Exception.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        if hub_challenge is not None:
            return hub_challenge
        else:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": 403,
                        "message": "Verification failed: hub.challenge is missing",
                    }
                },
            )

    raise HTTPException(
        status_code=403,
        detail={
            "error": {
                "code": 403,
                "message": "Verification failed: Invalid token or mode",
            }
        },
    )


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    orchestrator: Orchestrator = Depends(get_orchestrator),  # noqa: B008
) -> dict[str, Any]:
    """Meta Webhook GET endpoint to receive messages.

    Accepts raw bytes payload for X-Hub-Signature-256 verification.

    Args:
        request: FastAPI Request instance.
        background_tasks: FastAPI BackgroundTasks instance to perform async tasks.
        x_hub_signature_256: The Meta signature header.
        settings: Application Settings containing secrets.

    Returns:
        A JSON dictionary indicating success.
    """
    body_bytes = await request.body()

    # Step 1: Verify the signature
    if not verify_signature(body_bytes, x_hub_signature_256, settings.WHATSAPP_APP_SECRET):
        logger.warning("Signature verification failed", signature=x_hub_signature_256)
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": 401,
                    "message": "Invalid signature",
                }
            },
        )

    # Step 2: Parse JSON
    if not body_bytes:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": 400,
                    "message": "Empty payload body",
                }
            },
        )

    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": 400,
                    "message": f"Malformed JSON: {e!s}",
                }
            },
        ) from e

    # Step 3: Extract the message/interactive content and process
    try:
        entry = payload.get("entry", [])
        if not entry:
            # Not a typical WhatsApp notification, but return 200 OK
            return {"status": "success"}

        changes = entry[0].get("changes", [])
        if not changes:
            return {"status": "success"}

        value = changes[0].get("value", {})
        metadata = value.get("metadata", {})
        phone_number_id = metadata.get("phone_number_id")

        messages = value.get("messages", [])
        if not messages:
            # Might be a status update or other update, ignore/return 200 OK
            return {"status": "success"}

        message = messages[0]
        msg_type = message.get("type")

        text_content = None
        interactive_content = None

        if msg_type == "text":
            text_content = message.get("text", {}).get("body")
        elif msg_type == "interactive":
            interactive_content = message.get("interactive")
            # If there's list reply or button reply, we can log it or extract text
            # E.g. interactive.button_reply.title or list_reply.title
            if interactive_content:
                text_content = json.dumps(interactive_content)

        # Skip and ignore other types (statuses, errors, etc.)
        if text_content is None and interactive_content is None:
            return {"status": "success"}

        sender_wa_id = message.get("from")

        # Step 4: Log the incoming message (Must use pii_masker.mask() before logging)
        masked_text = pii_masker.mask(text_content or "")
        logger.info(
            "Received WhatsApp message",
            sender=sender_wa_id,
            msg_type=msg_type,
            body=masked_text,
        )

        # Step 5 & 6: Offload the Orchestrator call and message delivery to BackgroundTasks
        if phone_number_id and sender_wa_id and text_content:
            background_tasks.add_task(
                process_incoming_message,
                sender_wa_id,
                phone_number_id,
                text_content,
                orchestrator,
                settings.WHATSAPP_ACCESS_TOKEN,
                background_tasks,
            )

    except Exception as e:
        logger.error("Error processing webhook payload", error=str(e))
        # Keep returning 200 to prevent Meta from retrying and flooding us
        return {"status": "success"}

    return {"status": "success"}
