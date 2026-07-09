from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)

# JSON schema for OpenAI tool calling
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "check_order_status",
            "description": "Check the status of a specific order in our backend system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The unique order ID string (e.g. 12345).",
                    }
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "initiate_refund",
            "description": "Initiate a partial or full refund workflow for a specific order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The unique order ID string (e.g. 12345).",
                    },
                    "reason": {
                        "type": "string",
                        "description": "The reason explaining why the refund is being requested.",
                    },
                    "amount": {
                        "type": "number",
                        "description": "The amount in USD to refund.",
                    },
                },
                "required": ["order_id", "reason"],
            },
        },
    },
]


def execute_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """Execute a simulated backend tool call."""
    logger.info("Executing backend tool call", tool_name=tool_name, arguments=arguments)

    match tool_name:
        case "check_order_status":
            order_id = arguments.get("order_id", "")
            if not order_id:
                return "Error: order_id is required."
            # Simulate backend order search
            return f"Order status for ID '{order_id}': Shipped. Estimated delivery: 3 business days."

        case "initiate_refund":
            order_id = arguments.get("order_id", "")
            reason = arguments.get("reason", "")
            amount = arguments.get("amount", 0.0)

            if not order_id or not reason:
                return "Error: order_id and reason are required."

            # Log refund amount simulated logic
            logger.info("Processing refund simulations", order_id=order_id, reason=reason, amount=amount)
            return (
                f"Refund of ${amount:.2f} successfully initiated for Order '{order_id}'. "
                f"Reason: '{reason}'. Status: Pending Manual Approval."
            )

        case _:
            raise ValueError(f"Unknown or unsupported tool name: '{tool_name}'")
