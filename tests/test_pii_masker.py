from src.utils.pii_masker import mask


def test_mask_empty_or_none() -> None:
    """Test masking with empty string or None."""
    assert mask("") == ""


def test_mask_no_pii() -> None:
    """Test masking on text with no PII."""
    text = "Hello, world! This is a test message with zero personal data."
    assert mask(text) == text


def test_mask_email() -> None:
    """Test masking of email addresses."""
    text = "Please contact me at support@example.com or user.name+tag@sub.domain.org."
    expected = "Please contact me at [EMAIL] or [EMAIL]."
    assert mask(text) == expected


def test_mask_phone_numbers() -> None:
    """Test masking of various phone number formats."""
    # International format
    assert mask("My number is +12345678901.") == "My number is [PHONE]."
    # Local format with dashes
    assert mask("Call 123-456-7890.") == "Call [PHONE]."
    # Local format with parentheses and spaces
    assert mask("Send a text to (123) 456-7890.") == "Send a text to [PHONE]."
    # Local format with spaces
    assert mask("Reach out on +44 7911 123456.") == "Reach out on [PHONE]."


def test_mask_credit_cards() -> None:
    """Test masking of credit card numbers of 13 to 19 digits with spaces, dashes, or plain."""
    # Plain 16 digits
    assert mask("My card is 1234567890123456.") == "My card is [CARD]."
    # 16 digits with dashes
    assert mask("My card is 1234-5678-9012-3456.") == "My card is [CARD]."
    # 16 digits with spaces
    assert mask("My card is 1234 5678 9012 3456.") == "My card is [CARD]."
    # 13 digits card
    assert mask("An old card: 1234567890123.") == "An old card: [CARD]."
    # 19 digits card
    assert mask("A long card: 1234-5678-9012-3456-789.") == "A long card: [CARD]."


def test_mask_mixed_pii() -> None:
    """Test masking multiple types of PII within a single text."""
    text = (
        "Hello, I am John. My phone is +1 (555) 555-5555, "
        "my email is john.doe@gmail.com, and my Visa is 4111-1111-1111-1111."
    )
    expected = (
        "Hello, I am John. My phone is [PHONE], "
        "my email is [EMAIL], and my Visa is [CARD]."
    )
    assert mask(text) == expected
