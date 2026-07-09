import json
from typing import Any

from fastapi.testclient import TestClient

from src.utils.whatsapp_flows import FlowBuilder


def test_flow_builder_payload() -> None:
    """Tests that FlowBuilder correctly builds a valid structural interactive Flow JSON payload."""
    builder = FlowBuilder()
    recipient = "123456789"

    payload = builder.build_return_request_flow(recipient)

    assert payload["to"] == recipient
    assert payload["type"] == "interactive"
    assert payload["interactive"]["type"] == "flow"
    assert payload["interactive"]["action"]["name"] == "flow"
    assert "MOCK-FLOW-ID" in payload["interactive"]["action"]["parameters"]["flow_id"]


def test_webhook_parsing_nfm_reply(client: TestClient, signature_generator: Any) -> None:
    """Tests that the webhook parses interactive nfm_reply messages and formats them."""
    # Create valid WhatsApp webhook payload for a flow response
    flow_response_data = {
        "reason": "item_defective",
        "comments": "The item arrived damaged",
    }

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_id_123",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "16505553333",
                                "phone_number_id": "123456789",
                            },
                            "messages": [
                                {
                                    "from": "987654321",
                                    "id": "wamid.ID123",
                                    "timestamp": "1601234567",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "nfm_reply",
                                        "nfm_reply": {
                                            "name": "flow",
                                            "response_json": json.dumps(flow_response_data),
                                            "body": "Return Request",
                                        }
                                    }
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }

    body_bytes = json.dumps(payload).encode("utf-8")
    signature = signature_generator(body_bytes)

    headers = {
        "X-Hub-Signature-256": signature,
        "Content-Type": "application/json",
    }

    # Dispatch to webhook POST endpoint
    response = client.post("/webhook", content=body_bytes, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"status": "success"}
