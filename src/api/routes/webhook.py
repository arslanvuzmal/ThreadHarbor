import json
import time
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from src.api.dependencies import get_app_settings, get_handoff_client, get_http_client
from src.bot.session import SessionManager
from src.handoff.client import BaseHandoffClient
from src.orchestrator.engine import Orchestrator
from src.utils import pii_masker
from src.utils.config import Settings
from src.utils.logger import get_logger
from src.utils.whatsapp_signature import verify_signature

logger = get_logger(__name__)

router = APIRouter()


async def check_message_idempotency(message_id: str) -> bool:
    """Check if a message has already been processed using Redis-based deduplication.

    Args:
        message_id: The unique WhatsApp message ID.

    Returns:
        True if the message was already processed, False if it's new.
    """
    store = SessionManager._store_instance
    key = f"wbot:processed_msg:{message_id}"
    
    if store._redis:
        try:
            # Try to set the key with a 1-hour TTL (atomic operation)
            # Returns True if key was set (new message), False if key already exists
            result = store._redis.set(key, "1", nx=True, ex=3600)
            return result is False  # If result is False, key already existed
        except Exception as e:
            logger.warning("Redis idempotency check failed, proceeding without dedup", error=str(e))
            return False
    
    # Fallback to in-memory store (not ideal for multi-instance deployments)
    if hasattr(store, "_processed_messages"):
        if message_id in store._processed_messages:
            return True
        store._processed_messages[message_id] = time.time()
        # Clean up old entries (older than 1 hour)
        cutoff = time.time() - 3600
        store._processed_messages = {
            k: v for k, v in store._processed_messages.items() if v > cutoff
        }
        return False
    
    return False


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
    http_client: httpx.AsyncClient,
    media_id: str | None = None,
    media_mime_type: str | None = None,
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
        http_client: Shared async HTTP client with connection pooling.
        media_id: Optional ID of any uploaded media attachment.
        media_mime_type: Optional mime type of the media attachment.
    """
    try:
        import time

        from src.bot.session import SessionManager
        from src.utils.whatsapp_media import MediaManager
        from src.utils.whatsapp_templates import TemplateManager

        # Check window compliance BEFORE updating it for the new incoming message
        is_compliant = SessionManager.is_within_24h_window(sender_wa_id)

        # Load and update session with correct phone_number_id and update the interaction timestamp (24h compliance)
        session = await orchestrator.get_or_create_session(sender_wa_id)
        session.phone_number_id = phone_number_id
        session.last_interaction_timestamp = time.time()
        await orchestrator.save_session(session)

        # Handle media download asynchronously
        media_bytes: bytes | None = None
        if media_id:
            try:
                media_manager = MediaManager()
                media_bytes, downloaded_mime = await media_manager.download_media(media_id)
                if downloaded_mime:
                    media_mime_type = downloaded_mime
            except Exception as e:
                logger.error("Failed to download media in webhook process", media_id=media_id, error=str(e))
                text_content += f" (Media attachment download failed: {e!s})"

        # Handle message in orchestrator
        bot_response = await orchestrator.handle_message(
            sender_wa_id,
            text_content,
            background_tasks,
            media_bytes=media_bytes,
            mime_type=media_mime_type,
        )

        # If there is response text, verify 24h compliance window before sending
        if bot_response.text:
            if not is_compliant:
                logger.warning(
                    "Attempted to send message outside 24h window; falling back to order_update template",
                    session_id=sender_wa_id,
                )
                template_manager = TemplateManager()
                await template_manager.send_template_message(
                    recipient_wa_id=sender_wa_id,
                    template_name="order_update",
                    phone_number_id=phone_number_id,
                )
            else:
                await send_whatsapp_reply(
                    phone_number_id=phone_number_id,
                    to=sender_wa_id,
                    text_body=bot_response.text,
                    access_token=access_token,
                    http_client=http_client,
                )
    except Exception as e:
        logger.exception("Error processing incoming message in background", error=str(e))


async def send_whatsapp_reply(
    phone_number_id: str,
    to: str,
    text_body: str,
    access_token: str,
    http_client: httpx.AsyncClient,
) -> None:
    """Asynchronously sends a reply back to WhatsApp using the Graph API.

    Args:
        phone_number_id: The WhatsApp Phone Number ID extracted from payload.
        to: The sender's WhatsApp ID (wa_id).
        text_body: The reply text to send.
        access_token: The WHATSAPP_ACCESS_TOKEN configuration.
        http_client: Shared async HTTP client with connection pooling.
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
        response = await http_client.post(url, json=payload, headers=headers)
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
        message_id = message.get("id")  # Extract WhatsApp message ID for idempotency
        
        # Idempotency check: skip if this message was already processed
        if message_id:
            is_duplicate = await check_message_idempotency(message_id)
            if is_duplicate:
                logger.info("Duplicate message detected, skipping processing", message_id=message_id)
                return {"status": "success"}
        
        msg_type = message.get("type")

        text_content = None
        interactive_content = None
        media_id = None
        media_mime_type = None

        if msg_type == "text":
            text_content = message.get("text", {}).get("body")
        elif msg_type == "interactive":
            interactive_content = message.get("interactive", {})
            interactive_type = interactive_content.get("type")
            if interactive_type == "nfm_reply":
                nfm_reply = interactive_content.get("nfm_reply", {})
                response_json_str = nfm_reply.get("response_json", "{}")
                try:
                    parsed_json = json.loads(response_json_str)
                    text_content = f"User submitted Flow Data: {json.dumps(parsed_json)}"
                except Exception:
                    text_content = f"User submitted Flow Data: {response_json_str}"
            else:
                text_content = json.dumps(interactive_content)
        elif msg_type in ["image", "document", "audio"]:
            media_info = message.get(msg_type, {})
            media_id = media_info.get("id")
            media_mime_type = media_info.get("mime_type")
            caption = media_info.get("caption")
            filename = media_info.get("filename")
            text_content = caption or filename or f"Uploaded {msg_type}"

        # Skip and ignore other types (statuses, errors, etc.)
        if text_content is None and interactive_content is None and media_id is None:
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
            # Get shared HTTP client for connection pooling
            http_client = await get_http_client()
            background_tasks.add_task(
                process_incoming_message,
                sender_wa_id,
                phone_number_id,
                text_content,
                orchestrator,
                settings.WHATSAPP_ACCESS_TOKEN,
                background_tasks,
                http_client,
                media_id,
                media_mime_type,
            )

    except Exception as e:
        logger.error("Error processing webhook payload", error=str(e))
        # Keep returning 200 to prevent Meta from retrying and flooding us
        return {"status": "success"}

    return {"status": "success"}
