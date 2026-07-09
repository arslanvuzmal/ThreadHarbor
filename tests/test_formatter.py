from src.utils.whatsapp_formatter import format_interactive_buttons, format_text_message


def test_format_text_message() -> None:
    """Test standard WhatsApp API text message payload formatting with truncation."""
    recipient = "12345"
    text = "Hello!"
    payload = format_text_message(recipient, text)
    assert payload["to"] == recipient
    assert payload["type"] == "text"
    assert payload["text"]["body"] == "Hello!"

    # Test extreme character truncation (limit: 4096)
    long_text = "A" * 5000
    payload_long = format_text_message(recipient, long_text)
    assert len(payload_long["text"]["body"]) == 4096


def test_format_interactive_buttons() -> None:
    """Test standard WhatsApp API interactive buttons payload formatting with truncations."""
    recipient = "12345"
    text = "Choose an option:"
    buttons = [
        {"id": "btn_yes", "title": "Yes, absolutely!"},
        {"id": "btn_no", "title": "No way, not at all!"},
        {"id": "btn_maybe", "title": "Maybe later"},
        {"id": "btn_extra", "title": "Ignored button"},
    ]

    payload = format_interactive_buttons(recipient, text, buttons)
    assert payload["to"] == recipient
    assert payload["type"] == "interactive"

    interactive = payload["interactive"]
    assert interactive["type"] == "button"
    assert interactive["body"]["text"] == "Choose an option:"

    btns = interactive["action"]["buttons"]
    # Should slice to max 3 buttons
    assert len(btns) == 3

    # Check titles are truncated to 20 chars
    assert btns[0]["reply"]["id"] == "btn_yes"
    assert btns[0]["reply"]["title"] == "Yes, absolutely!"  # 16 chars

    assert btns[1]["reply"]["id"] == "btn_no"
    assert btns[1]["reply"]["title"] == "No way, not at all!"[:20]  # truncated
    assert len(btns[1]["reply"]["title"]) <= 20
