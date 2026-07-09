from typing import Any

import tiktoken

from src.bot.models import Message, Role
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ContextBuilder:
    """Manages context assembly, prompt formatting, and enforces the token-budget limit using tiktoken."""

    def __init__(self, encoding_name: str = "cl100k_base", max_tokens: int = 3000) -> None:
        """Initialize the ContextBuilder with default cl100k_base encoder and 3000 max tokens constraint."""
        self.encoding = tiktoken.get_encoding(encoding_name)
        self.max_tokens = max_tokens

    def _count_tokens(self, text: str) -> int:
        """Helper method to return token count of text."""
        if not text:
            return 0
        return len(self.encoding.encode(text))

    def _count_messages_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Accurate estimate of total tokens in messages format."""
        num_tokens = 0
        for message in messages:
            num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
            for _key, value in message.items():
                if isinstance(value, str):
                    num_tokens += self._count_tokens(value)
                elif isinstance(value, list):
                    # Handle nested lists if tool_calls or others exist
                    num_tokens += self._count_tokens(str(value))
        num_tokens += 2  # every reply is primed with <im_start>assistant
        return num_tokens

    def build_messages(self, session_history: list[Message], rag_context: str) -> list[dict[str, Any]]:
        """Assembles prompt payload and dynamically drops older messages to satisfy token limits."""
        system_prompt = (
            "You are a helpful WhatsApp support agent. "
            "Use the provided context to answer questions. "
            "If you don't know, say you will connect them to a human. Be concise."
        )

        # Base instructions
        base_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"Context: {rag_context}"},
        ]

        # Calculate base tokens that can never be dropped
        base_tokens = self._count_messages_tokens(base_messages)

        # Build list of user/assistant conversational messages from history
        chat_messages = []
        for msg in session_history:
            role_str = "user" if msg.role == Role.USER else "assistant"
            chat_messages.append({"role": role_str, "content": msg.content})

        # Evict oldest chat turns iteratively if the cumulative token size exceeds budget
        while chat_messages:
            total_tokens = base_tokens + self._count_messages_tokens(chat_messages)
            if total_tokens <= self.max_tokens:
                break
            # Token budget exceeded, drop oldest turn
            logger.info(
                "Evicting oldest turn in session history",
                total_tokens=total_tokens,
                limit=self.max_tokens,
            )
            chat_messages.pop(0)

        # Return full merged frames
        return base_messages + chat_messages
