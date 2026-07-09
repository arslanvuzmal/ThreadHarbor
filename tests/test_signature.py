from src.utils.whatsapp_signature import verify_signature


def test_valid_signature() -> None:
    """Test that a valid signature returns True."""
    payload = b"hello world"
    secret = "my_secret"
    # Expected hex for: hmac.new(b"my_secret", b"hello world", "sha256")
    # Let's compute mathematically or use our understanding.
    import hmac

    expected_mac = hmac.new(secret.encode("utf-8"), payload, "sha256")
    signature_header = f"sha256={expected_mac.hexdigest()}"

    assert verify_signature(payload, signature_header, secret) is True


def test_invalid_signature() -> None:
    """Test that an invalid signature returns False."""
    payload = b"hello world"
    secret = "my_secret"
    signature_header = "sha256=invalidhex"

    assert verify_signature(payload, signature_header, secret) is False


def test_missing_header() -> None:
    """Test that missing signature header returns False."""
    payload = b"hello world"
    secret = "my_secret"

    assert verify_signature(payload, None, secret) is False


def test_malformed_header() -> None:
    """Test that malformed header (no sha256= prefix) returns False."""
    payload = b"hello world"
    secret = "my_secret"
    signature_header = "random_signature_string"

    assert verify_signature(payload, signature_header, secret) is False


def test_timing_safe_comparison() -> None:
    """Test timing-safe comparison on known payloads."""
    payload = b'{"object":"whatsapp_business_account","entry":[]}'
    secret = "app_secret_key"
    import hmac

    mac = hmac.new(secret.encode("utf-8"), payload, "sha256")
    valid_header = f"sha256={mac.hexdigest()}"

    # Verify signature passes
    assert verify_signature(payload, valid_header, secret) is True

    # Same signature with different payload fails
    assert verify_signature(b"different payload", valid_header, secret) is False
