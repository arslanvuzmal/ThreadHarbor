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
