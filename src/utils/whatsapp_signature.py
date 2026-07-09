import hmac


def verify_signature(payload: bytes, signature_header: str | None, app_secret: str) -> bool:
    """Verify that the payload matches the X-Hub-Signature-256 header sent by Meta.

    Meta's X-Hub-Signature-256 header format is: sha256=<hex_digest>

    Args:
        payload: The raw bytes payload of the request.
        signature_header: The X-Hub-Signature-256 header string.
        app_secret: The Meta developer App Secret.

    Returns:
        True if the signature matches, False otherwise.
    """
    if not signature_header:
        return False

    # Check for malformed header (must start with "sha256=")
    prefix = "sha256="
    if not signature_header.startswith(prefix):
        return False

    # Extract the hex digest
    hex_digest = signature_header[len(prefix) :].strip()

    # Compute expected signature
    expected_mac = hmac.new(
        app_secret.encode("utf-8"),
        payload,
        "sha256",
    )
    expected_hex = expected_mac.hexdigest()

    # Use hmac.compare_digest to protect against timing attacks
    return hmac.compare_digest(expected_hex, hex_digest)
