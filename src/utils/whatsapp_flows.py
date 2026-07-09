from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)


class FlowBuilder:
    """Builder class designed to construct valid structural Meta WhatsApp Flow interactive JSON payloads."""

    def build_return_request_flow(self, recipient_wa_id: str) -> dict[str, Any]:
        """Constructs an interactive WhatsApp Flow message payload designed to collect customer return request details.

        Args:
            recipient_wa_id: WhatsApp ID (phone number) of the user receiving the flow.

        Returns:
            Dict representing the interactive flows payload according to Meta's Cloud API specifications.
        """
        logger.info("Constructing return request WhatsApp Flow payload", recipient=recipient_wa_id)

        # Build interactive structural Flow schema
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_wa_id,
            "type": "interactive",
            "interactive": {
                "type": "flow",
                "header": {
                    "type": "text",
                    "text": "Initiate Return Request",
                },
                "body": {
                    "text": "Please fill out the structured return details by clicking the button below.",
                },
                "footer": {
                    "text": "Secured & Encrypted Form",
                },
                "action": {
                    "name": "flow",
                    "parameters": {
                        "flow_message_version": "3",
                        "flow_token": f"return_flow_token_{recipient_wa_id}",
                        "flow_id": "MOCK-FLOW-ID-987654",
                        "flow_cta": "Open Return Form",
                        "flow_action": "navigate",
                        "flow_action_payload": {
                            "screen": "RETURN_FORM_SCREEN",
                        },
                    },
                },
            },
        }
        return payload
