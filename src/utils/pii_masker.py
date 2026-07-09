import re


def mask(text: str) -> str:
    """Mask sensitive PII in the given text with placeholders.

    Replaces:
    - Phone numbers (e.g. standard country-coded or local phone numbers) with [PHONE]
    - Email addresses with [EMAIL]
    - Credit card numbers (13-19 digits, optionally separated by spaces or dashes) with [CARD]

    Args:
        text: The source string containing potential PII.

    Returns:
        The masked string.
    """
    if not text:
        return text

    # Mask credit card numbers: 13 to 19 digits, possibly separated by spaces or dashes.
    card_pattern = r"\b\d(?:\s*-?\s*\d){12,18}\b"
    text = re.sub(card_pattern, "[CARD]", text)

    # Mask email addresses
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    text = re.sub(email_pattern, "[EMAIL]", text)

    # Mask phone numbers
    # To properly match optional '+' and handle boundaries:
    # 1. First target international format starting with '+'
    intl_pattern_with_plus = r"\+\d{1,4}[-.\s]?\(?\d{1,4}?\)?[-.\s]?\d{1,4}[-.\s]?\d{2,4}[-.\s]?\d{2,4}\b|\+\d{7,15}\b"
    text = re.sub(intl_pattern_with_plus, "[PHONE]", text)

    # 2. Match standard US-style or other format without plus,
    # with optional country code or optional parenthesized area codes.
    # We use a pattern with non-word boundary or start/space option.
    us_style_pattern = r"(?:\b|\()(?:\d[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    text = re.sub(us_style_pattern, "[PHONE]", text)

    return text
