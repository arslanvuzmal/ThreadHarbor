import pytest

from src.intelligence.tools import execute_tool


def test_execute_tool_check_order_status() -> None:
    """Test checking valid/invalid order statuses."""
    res = execute_tool("check_order_status", {"order_id": "12345"})
    assert "Shipped" in res
    assert "12345" in res

    # Missing parameter
    res_err = execute_tool("check_order_status", {})
    assert "Error" in res_err


def test_execute_tool_initiate_refund() -> None:
    """Test initiating order refunds with parameters."""
    res = execute_tool("initiate_refund", {"order_id": "9999", "reason": "damaged item", "amount": 150.0})
    assert "Pending Manual Approval" in res
    assert "$150.00" in res
    assert "9999" in res

    # Missing parameters
    res_err = execute_tool("initiate_refund", {"order_id": "9999"})
    assert "Error" in res_err


def test_execute_tool_unknown() -> None:
    """Test executing an unsupported tool raising ValueError."""
    with pytest.raises(ValueError, match="Unknown or unsupported tool name"):
        execute_tool("cancel_subscription", {"subscription_id": "abc"})
