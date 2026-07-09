import os
from typing import Any

import httpx
from pydantic import BaseModel

from src.bot.session import SessionData
from src.utils.logger import get_logger

logger = get_logger(__name__)


class HandoffPayload(BaseModel):
    """Pydantic model representing the context payload sent to Zendesk/Freshdesk for human handoff."""

    user_profile: dict[str, Any]
    escalation_reason: str
    conversation_summary: str
    transcript: list[dict[str, Any]]


async def generate_summary(transcript: list[dict[str, Any]]) -> str:
    """Generates a 2-sentence summary of the conversation using gpt-4o-mini via the OpenAI Chat Completions API.

    If the API call fails or the API key is not configured, a default friendly summary is returned.

    Args:
        transcript: Full list of transcript message dictionaries.

    Returns:
        A 2-sentence string summary of the conversation.
    """
    last_10 = transcript[-10:]
    formatted_chat = "\n".join([f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" for msg in last_10])

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.info("OPENAI_API_KEY not configured; using default summary")
        return "The user requires assistance. This conversation has been escalated to a human agent."

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a customer service assistant. "
                    "Summarize the following conversation in exactly two sentences."
                ),
            },
            {
                "role": "user",
                "content": f"Here is the conversation so far:\n{formatted_chat}",
            },
        ],
        "max_tokens": 100,
        "temperature": 0.5,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                summary = str(data["choices"][0]["message"]["content"]).strip()
                logger.info("Generated conversation summary via gpt-4o-mini", summary=summary)
                return summary
            else:
                logger.warning(
                    "OpenAI API returned non-200 status code",
                    status_code=response.status_code,
                    body=response.text,
                )
    except Exception as e:
        logger.error("Failed to generate summary via LLM call", error=str(e))

    return "The user is seeking assistance with their request. The conversation has been escalated for human handoff."


async def build_payload(session_data: SessionData, reason: str) -> HandoffPayload:
    """Builds a HandoffPayload using the current SessionData and the escalation reason.

    Args:
        session_data: The active session state.
        reason: The reason for the escalation.

    Returns:
        The fully constructed HandoffPayload.
    """
    summary = await generate_summary(session_data.transcript)
    last_10_transcript = session_data.transcript[-10:]
    return HandoffPayload(
        user_profile=session_data.user_profile,
        escalation_reason=reason,
        conversation_summary=summary,
        transcript=last_10_transcript,
    )
