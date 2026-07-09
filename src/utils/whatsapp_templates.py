from typing import Any, cast

import httpx

from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TemplateManager:
    """Manages pre-approved Meta WhatsApp Message Templates and dispatches template messages to the Cloud API."""

    def __init__(self) -> None:
        """Initializes TemplateManager with a mock registry of pre-approved WhatsApp templates."""
        self.settings = get_settings()
        self.registry: dict[str, dict[str, str]] = {
            "order_update": {"name": "order_update_01", "language": "en_US"},
            "welcome": {"name": "welcome_01", "language": "en_US"},
        }

    async def send_template_message(
        self,
        recipient_wa_id: str,
        template_name: str,
        components: list[dict[str, Any]] | None = None,
        phone_number_id: str | None = None,
    ) -> dict[str, Any]:
        """Constructs and sends a pre-approved template message payload to the WhatsApp Cloud API.

        Args:
            recipient_wa_id: WhatsApp ID (phone number) of the user.
            template_name: Short name of the template from the registry (e.g. 'order_update').
            components: Optional list of component arguments (header, body, buttons) for the template.
            phone_number_id: Optional WhatsApp business phone number ID. Fallback used if None.

        Returns:
            The HTTP response JSON dictionary.
        """
        if template_name not in self.registry:
            logger.error("Template name not found in registry", template_name=template_name)
            raise ValueError(f"Template '{template_name}' is not registered.")

        template_config = self.registry[template_name]
        p_num_id = phone_number_id or "default_phone_number_id"

        url = f"https://graph.facebook.com/v21.0/{p_num_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

        # Build Meta template schema
        template_payload: dict[str, Any] = {
            "name": template_config["name"],
            "language": {"code": template_config["language"]},
        }
        if components:
            template_payload["components"] = components

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_wa_id,
            "type": "template",
            "template": template_payload,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "WhatsApp template message sent successfully",
                    template_name=template_name,
                    recipient=recipient_wa_id,
                    status_code=response.status_code,
                )
                return cast(dict[str, Any], data)
        except Exception as e:
            logger.error(
                "Failed to send template message via WhatsApp API",
                template_name=template_name,
                recipient=recipient_wa_id,
                error=str(e),
            )
            # For robustness in tests/mock setups, return mock response dict if call fails
            return {"status": "failed", "error": str(e)}
