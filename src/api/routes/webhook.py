import json
from typing import Any

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from src.api.dependencies import get_app_settings
from src.bot.models import BotResponse
from src.bot.session import SessionManager
from src.orchestrator.engine import Orchestrator
from src.utils import pii_masker, whatsapp_formatter
from src.utils.config import Settings
from src.utils.logger import get_logger
from src.utils.whatsapp_signature import verify_signature

logger = get_logger(__name__)

router = APIRouter()


async def send_bot_reply(
    session_id: str,
    bot_response: BotResponse,
    recipient_wa_id: str,
    phone_number_id: str,
    access_token: str,
    redis_url: str,
) -> None:
    """Asynchronously sends the formatted bot response back to WhatsApp using the Graph API.

    Performs 24-hour window check, formats message structure, and dispatches payload.

    Args:
        session_id: The ID of the session.
        bot_response: The BotResponse instance returned by Orchestrator.
        recipient_wa_id: The recipient's WhatsApp ID.
        phone_number_id: The Phone Number ID extracted from payload.
        access_token: Meta Developer Graph API Access Token.
        redis_url: The Redis connection URL.
    """
    # Initialize connection to verify 24h window
    redis_client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        session_manager = SessionManager(redis_client)
        is_active_window = await session_manager.is_within_24h_window(session_id)
        if not is_active_window:
            logger.warning(
                "User is outside the active 24-hour window. Cannot send free-form message.",
                session_id=session_id,
                recipient_wa_id=recipient_wa_id,
            )

        # Format message depending on payload content
        if bot_response.buttons:
            payload = whatsapp_formatter.format_interactive_buttons(
                recipient_wa_id=recipient_wa_id,
                text=bot_response.text,
                buttons=bot_response.buttons,
            )
        else:
            payload = whatsapp_formatter.format_text_message(
                recipient_wa_id=recipient_wa_id,
                text=bot_response.text,
            )

        url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(
                "WhatsApp reply dispatched successfully",
                phone_number_id=phone_number_id,
                to=recipient_wa_id,
                status_code=response.status_code,
            )
    except Exception as e:
        logger.error(
            "Failed to send WhatsApp bot reply",
            session_id=session_id,
            recipient_wa_id=recipient_wa_id,
            error=str(e),
        )
    finally:
        try:
            if hasattr(redis_client, "aclose") and callable(redis_client.aclose):
                await redis_client.aclose()
            elif hasattr(redis_client, "close") and callable(redis_client.close):
                # Avoid calling synchronous close with await in async environment
                redis_client.close()
        except Exception:
            pass


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    settings: Settings = Depends(get_app_settings),  # noqa: B008
) -> str:
    """Meta Webhook Verification GET endpoint."""
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
) -> dict[str, Any]:
    """Meta Webhook POST endpoint to receive messages, routing them to the Orchestrator."""
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
            return {"status": "success"}

        changes = entry[0].get("changes", [])
        if not changes:
            return {"status": "success"}

        value = changes[0].get("value", {})
        metadata = value.get("metadata", {})
        phone_number_id = metadata.get("phone_number_id")

        messages = value.get("messages", [])
        if not messages:
            return {"status": "success"}

        message = messages[0]
        msg_type = message.get("type")

        text_content = None
        interactive_content = None

        if msg_type == "text":
            text_content = message.get("text", {}).get("body")
        elif msg_type == "interactive":
            interactive_content = message.get("interactive")
            if interactive_content:
                text_content = json.dumps(interactive_content)

        if text_content is None and interactive_content is None:
            return {"status": "success"}

        sender_wa_id = message.get("from")

        # Step 4: Log the incoming message
        masked_text = pii_masker.mask(text_content or "")
        logger.info(
            "Received WhatsApp message",
            sender=sender_wa_id,
            msg_type=msg_type,
            body=masked_text,
        )

        # Step 5 & 6: Process with the Orchestrator & Respond with placeholder in background
        if phone_number_id and sender_wa_id:
            # Connect to Redis to initialize Orchestrator and SessionManager
            redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            try:
                session_manager = SessionManager(redis_client)
                orchestrator = Orchestrator(session_manager)

                # Process the message (modifies state machine)
                bot_response = await orchestrator.process_message(sender_wa_id, text_content or "")

                # Queue asynchronous reply delivery to keep Meta webhook fast
                background_tasks.add_task(
                    send_bot_reply,
                    sender_wa_id,
                    bot_response,
                    sender_wa_id,
                    phone_number_id,
                    settings.WHATSAPP_ACCESS_TOKEN,
                    settings.REDIS_URL,
                )
            finally:
                try:
                    if hasattr(redis_client, "aclose") and callable(redis_client.aclose):
                        await redis_client.aclose()
                    elif hasattr(redis_client, "close") and callable(redis_client.close):
                        redis_client.close()
                except Exception:
                    pass

    except Exception as e:
        logger.error("Error processing webhook payload", error=str(e))
        return {"status": "success"}

    return {"status": "success"}
