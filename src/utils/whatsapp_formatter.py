import re


def whatsapp_formatter(text: str) -> str:
    """Formats plain text to WhatsApp format by converting basic markdown to WhatsApp markup.

    Converts bold (**text**) to WhatsApp bold (*text*).

    Args:
        text: Plain text message.

    Returns:
        Formatted WhatsApp text markup.
    """
    # Convert **bold** to *bold*
    return re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
from typing import Any


def format_text_message(recipient_wa_id: str, text: str) -> dict[str, Any]:
    """Formats a basic text message payload for the WhatsApp Cloud API.

    Truncates text to WhatsApp's 4096-character limit to avoid API errors.

    Args:
        recipient_wa_id: The recipient's WhatsApp ID.
        text: The text content of the message.

    Returns:
        A dictionary representation of the WhatsApp API payload.
    """
    truncated_text = text[:4096] if text else ""
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_wa_id,
        "type": "text",
        "text": {"body": truncated_text},
    }


def format_interactive_buttons(recipient_wa_id: str, text: str, buttons: list[dict[str, Any]]) -> dict[str, Any]:
    """Formats an interactive quick reply button payload for the WhatsApp Cloud API.

    Supports up to 3 buttons. Truncates text to 4096 characters, and button titles to 20 characters.

    Args:
        recipient_wa_id: The recipient's WhatsApp ID.
        text: The body text of the interactive message.
        buttons: A list of dicts, each with keys 'id' and 'title'.

    Returns:
        A dictionary representation of the WhatsApp API payload.
    """
    truncated_text = text[:4096] if text else ""
    # Support up to 3 buttons
    sliced_buttons = buttons[:3]

    formatted_buttons = []
    for btn in sliced_buttons:
        btn_id = btn.get("id", "")
        btn_title = btn.get("title", "")
        # Truncate button title to 20 characters
        truncated_title = btn_title[:20] if btn_title else ""
        formatted_buttons.append(
            {
                "type": "reply",
                "reply": {
                    "id": btn_id,
                    "title": truncated_title,
                },
            }
        )

    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_wa_id,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": truncated_text},
            "action": {"buttons": formatted_buttons},
        },
    }
