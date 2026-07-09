from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel

from src.api.dependencies import get_app_settings, get_handoff_client
from src.api.routes.webhook import send_whatsapp_reply
from src.handoff.client import BaseHandoffClient
from src.orchestrator.engine import Orchestrator
from src.utils.config import Settings
from src.utils.logger import get_logger
from src.utils.whatsapp_formatter import whatsapp_formatter

logger = get_logger(__name__)

router = APIRouter()


class AgentMessagePayload(BaseModel):
    """Payload model for the Human Agent inbound webhook."""

    session_id: str
    agent_id: str
    text: str = ""
    action: Literal["reply", "close"]


async def verify_agent_token(
    request: Request,
    settings: Settings = Depends(get_app_settings),  # noqa: B008
) -> str:
    """Dependency to verify the Bearer token in the Authorization header against AGENT_API_SECRET.

    Args:
        request: FastAPI Request instance.
        settings: Application Settings containing the secret.

    Returns:
        The validated token string, or raises 401 Unauthorized if invalid.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": 401,
                    "message": "Missing Authorization header",
                }
            },
        )

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": 401,
                    "message": "Invalid Authorization header format",
                }
            },
        )

    token = parts[1]
    if token != settings.AGENT_API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": 401,
                    "message": "Invalid agent API secret",
                }
            },
        )

    return token


# Dependencies to obtain the global handoff client and session store/orchestrator
# We use lazy instantiation to ensure the global instances in dependencies.py are loaded.


def get_orchestrator_instance(
    handoff_client: BaseHandoffClient = Depends(get_handoff_client),  # noqa: B008
) -> Orchestrator:
    """Dependency providing the Orchestrator instance."""
    # We initialize it with the same shared/mocked dependencies
    return Orchestrator(handoff_client=handoff_client)


@router.post("/agent/message")
async def receive_agent_message(
    payload: AgentMessagePayload,
    background_tasks: BackgroundTasks,
    _token: str = Depends(verify_agent_token),
    orchestrator: Orchestrator = Depends(get_orchestrator_instance),  # noqa: B008
    handoff_client: BaseHandoffClient = Depends(get_handoff_client),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
) -> dict[str, Any]:
    """Receives inbound messages and commands from human agents.

    Supports action 'reply' and action 'close'.
    Uses BackgroundTasks to communicate with Meta Graph APIs so HTTP responses are non-blocking.

    Args:
        payload: The AgentMessagePayload request body.
        background_tasks: FastAPI BackgroundTasks instance.
        _token: Token validation indicator.
        orchestrator: Current Orchestrator.
        handoff_client: CCaaS system client.
        settings: Application Settings.

    Returns:
        A success JSON object.
    """
    session = await orchestrator.get_or_create_session(payload.session_id)
    phone_number_id = session.phone_number_id or "default_phone_number_id"

    if payload.action == "reply":
        # Format the agent's response using the whatsapp_formatter
        formatted_reply = whatsapp_formatter(payload.text)

        # Append assistant's reply to the transcript
        session.transcript.append({"role": "assistant", "content": formatted_reply})
        await orchestrator.save_session(session)

        # Queue the outgoing WhatsApp API message
        background_tasks.add_task(
            send_whatsapp_reply,
            phone_number_id,
            payload.session_id,
            formatted_reply,
            settings.WHATSAPP_ACCESS_TOKEN,
        )
        logger.info("Queued agent reply dispatch to WhatsApp", session_id=payload.session_id)

    elif payload.action == "close":
        # Transition session state back to AWAITING_INPUT
        session.state = "AWAITING_INPUT"

        # Close the active ticket in CCaaS if we have it
        if session.ticket_id:
            try:
                await handoff_client.close_ticket(session.ticket_id)
            except Exception as e:
                logger.error("Failed to close ticket in handoff client", ticket_id=session.ticket_id, error=str(e))
            session.ticket_id = None

        # Reset tracking elements
        session.low_confidence_consecutive_count = 0
        session.last_user_message = None

        # Append system/assistant notice of closure
        csat_text = "The chat has been closed. How would you rate your experience? [1-5]"
        session.transcript.append({"role": "assistant", "content": csat_text})
        await orchestrator.save_session(session)

        # Queue the CSAT closure message to WhatsApp
        background_tasks.add_task(
            send_whatsapp_reply,
            phone_number_id,
            payload.session_id,
            csat_text,
            settings.WHATSAPP_ACCESS_TOKEN,
        )
        logger.info("Queued chat closure and CSAT template dispatch to WhatsApp", session_id=payload.session_id)

    return {"status": "success"}
