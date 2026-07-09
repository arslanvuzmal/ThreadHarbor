from src.bot.models import Message, Role
from src.intelligence.context import ContextBuilder


def test_context_builder_within_limit() -> None:
    """Test generating standard contextual messages within the 3000 token budget limit."""
    builder = ContextBuilder(max_tokens=3000)

    history = [
        Message(role=Role.USER, content="Hello!"),
        Message(role=Role.BOT, content="How can I help you today?"),
        Message(role=Role.USER, content="I want to check my order status"),
    ]

    rag_context = "FAQ: To track your order, send 'check order' along with your order ID."

    messages = builder.build_messages(history, rag_context)

    # 1 System instructions, 1 system context, 3 history messages (total: 5)
    assert len(messages) == 5
    assert messages[0]["role"] == "system"
    assert "helpful WhatsApp support agent" in messages[0]["content"]

    assert messages[1]["role"] == "system"
    assert "FAQ: To track" in messages[1]["content"]

    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "Hello!"

    assert messages[3]["role"] == "assistant"
    assert messages[3]["content"] == "How can I help you today?"


def test_context_builder_token_truncation() -> None:
    """Test dropping old conversation history iteratively to fit inside the token budget."""
    # Set limit to be very small, forcing truncation of older turns
    builder = ContextBuilder(max_tokens=100)

    history = [
        Message(role=Role.USER, content="A" * 150),  # Old turn that should get dropped
        Message(role=Role.BOT, content="B" * 150),   # Old turn that should get dropped
        Message(role=Role.USER, content="Short query"),  # Fits
    ]

    rag_context = "Brief FAQ"

    messages = builder.build_messages(history, rag_context)

    # System prompts must remain intact, older user messages should have popped out to satisfy the limit
    assert len(messages) >= 2
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "Short query"

    # Verify that the history messages are within limits
    # System prompt is about 156 characters and is NOT truncated
    history_messages = [m for m in messages if m["role"] in ("user", "assistant")]
    for m in history_messages:
        assert len(m["content"]) < 100
