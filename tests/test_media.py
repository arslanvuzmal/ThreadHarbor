from unittest.mock import MagicMock, patch

import pytest
import respx

from src.bot.session import SessionData
from src.handoff.client import MockZendeskClient
from src.orchestrator.engine import Orchestrator
from src.utils.whatsapp_media import MediaManager, MediaTooLargeError


@pytest.mark.asyncio
async def test_media_manager_download_success() -> None:
    """Tests that MediaManager performs the correct two-step download logic and returns binary bytes."""
    manager = MediaManager()
    media_id = "media_123"
    download_url = "https://cdn.facebook.com/download/media_123"

    with respx.mock:
        # Step 1: Mock metadata GET endpoint
        respx.get(f"https://graph.facebook.com/v21.0/{media_id}").respond(
            status_code=200,
            json={
                "url": download_url,
                "mime_type": "image/jpeg",
                "file_size": 2048,
            },
        )

        # Step 2: Mock binary GET endpoint
        respx.get(download_url).respond(
            status_code=200,
            content=b"fake-binary-content-data",
        )

        content, mime_type = await manager.download_media(media_id)
        assert content == b"fake-binary-content-data"
        assert mime_type == "image/jpeg"


@pytest.mark.asyncio
async def test_media_manager_metadata_too_large() -> None:
    """Tests that MediaManager raises MediaTooLargeError if file_size in metadata exceeds 5MB limit."""
    manager = MediaManager()
    media_id = "media_large"

    with respx.mock:
        respx.get(f"https://graph.facebook.com/v21.0/{media_id}").respond(
            status_code=200,
            json={
                "url": "https://cdn.facebook.com/large_media",
                "mime_type": "application/pdf",
                "file_size": 6 * 1024 * 1024,  # 6MB
            },
        )

        with pytest.raises(MediaTooLargeError, match="exceeds the allowed limit"):
            await manager.download_media(media_id)


@pytest.mark.asyncio
async def test_media_manager_download_too_large() -> None:
    """Tests that MediaManager raises MediaTooLargeError if downloaded content exceeds limit."""
    manager = MediaManager()
    media_id = "media_large_no_metadata_size"
    download_url = "https://cdn.facebook.com/no_size"

    with respx.mock:
        respx.get(f"https://graph.facebook.com/v21.0/{media_id}").respond(
            status_code=200,
            json={
                "url": download_url,
                "mime_type": "audio/ogg",
            },
        )

        # Download content is actually 6MB of null bytes
        respx.get(download_url).respond(
            status_code=200,
            content=b"\x00" * (6 * 1024 * 1024),
        )

        with pytest.raises(MediaTooLargeError, match="exceeds the allowed limit"):
            await manager.download_media(media_id)


@pytest.mark.asyncio
async def test_orchestrator_image_vision_handling() -> None:
    """Tests that passing image bytes to Orchestrator triggers vision logic and invokes gpt-4o."""
    client = MockZendeskClient()
    orchestrator = Orchestrator(handoff_client=client)

    session = SessionData(session_id="user-xyz")
    image_bytes = b"fake-image-bytes"
    mime_type = "image/png"

    # Call LLM method under orchestrator directly
    response_text, tool_calls, model_used, _ = await orchestrator.call_llm(
        text="What is this receipt?",
        _session=session,
        media_bytes=image_bytes,
        mime_type=mime_type,
    )

    assert model_used == "gpt-4o"
    assert "GPT-4o Vision" in response_text
    assert tool_calls is None


@pytest.mark.asyncio
async def test_orchestrator_pdf_text_extraction() -> None:
    """Tests that passing PDF bytes triggers text extraction using pypdf."""
    client = MockZendeskClient()
    orchestrator = Orchestrator(handoff_client=client)
    session = SessionData(session_id="user-xyz")

    pdf_bytes = b"fake-pdf-content"
    mime_type = "application/pdf"

    # Mock pypdf.PdfReader
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "ORDER-NUM-999"
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with patch("pypdf.PdfReader", return_value=mock_reader):
        response_text, tool_calls, model_used, _ = await orchestrator.call_llm(
            text="Verify order details",
            _session=session,
            media_bytes=pdf_bytes,
            mime_type=mime_type,
        )

        assert model_used == "gpt-4o-mini"
        assert "ORDER-NUM-999" in response_text
        assert tool_calls is None
