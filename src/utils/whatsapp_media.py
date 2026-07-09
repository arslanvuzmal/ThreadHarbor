
import httpx

from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MediaTooLargeError(Exception):
    """Custom exception raised when an inbound WhatsApp media attachment exceeds the maximum allowed size limit."""

    pass


class MediaManager:
    """Handles querying and downloading inbound WhatsApp media attachments via Meta's Graph API."""

    def __init__(self) -> None:
        """Initializes MediaManager with app settings."""
        self.settings = get_settings()

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        """Downloads active media from WhatsApp using the two-step Meta Cloud API flow.

        1. Queries the media metadata endpoint for the transient download URL and file size.
        2. Performs size boundary verification against configured thresholds.
        3. Downloads and returns the binary stream alongside the file mime type.

        Args:
            media_id: The unique ID representing the uploaded WhatsApp attachment.

        Returns:
            A tuple of (binary_bytes: bytes, mime_type: str).

        Raises:
            MediaTooLargeError: If file size exceeds the configured max limit (5MB by default).
        """
        metadata_url = f"https://graph.facebook.com/v21.0/{media_id}"
        headers = {
            "Authorization": f"Bearer {self.settings.WHATSAPP_ACCESS_TOKEN}",
        }

        # Step 1: Query Metadata
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(metadata_url, headers=headers, timeout=10.0)
                resp.raise_for_status()
                metadata = resp.json()
        except Exception as e:
            logger.error("Failed to query media metadata from Meta API", media_id=media_id, error=str(e))
            raise

        download_url = metadata.get("url")
        mime_type = metadata.get("mime_type", "application/octet-stream")
        file_size = metadata.get("file_size")

        if not download_url:
            raise ValueError(f"Metadata for media_id {media_id} did not contain a valid URL")

        # Step 2: Safety Check on file size
        max_bytes = self.settings.MAX_MEDIA_SIZE_MB * 1024 * 1024
        if file_size is not None:
            try:
                size_val = int(file_size)
                if size_val > max_bytes:
                    logger.warning("Media size limit exceeded", media_id=media_id, size=size_val, limit=max_bytes)
                    raise MediaTooLargeError(
                        f"Media file size ({size_val} bytes) exceeds the allowed limit ({max_bytes} bytes)."
                    )
            except ValueError:
                pass

        # Step 3: Perform actual binary download
        try:
            async with httpx.AsyncClient() as client:
                binary_resp = await client.get(download_url, headers=headers, timeout=20.0)
                binary_resp.raise_for_status()
                content = binary_resp.content
        except Exception as e:
            logger.error("Failed to download media binary stream", url=download_url, error=str(e))
            raise

        # Post-download safety size check (to cover files without size in metadata)
        if len(content) > max_bytes:
            logger.warning("Downloaded media size limit exceeded", media_id=media_id, size=len(content))
            raise MediaTooLargeError(
                f"Media file size ({len(content)} bytes) exceeds the allowed limit ({max_bytes} bytes)."
            )

        logger.info(
            "Media downloaded successfully",
            media_id=media_id,
            mime_type=mime_type,
            size_bytes=len(content),
        )
        return content, mime_type
