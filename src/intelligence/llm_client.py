from typing import Any

from openai import AsyncOpenAI

from src.utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """Wrapper around the official asynchronous OpenAI SDK for chat completions and embeddings generation."""

    def __init__(
        self,
        api_key: str,
        chat_model: str = "gpt-4o-mini",
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        """Initialize the LLMClient with AsyncOpenAI API Key and defaults."""
        self.client = AsyncOpenAI(api_key=api_key)
        self.chat_model = chat_model
        self.embedding_model = embedding_model

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Request a chat completion from the OpenAI API."""
        logger.debug("Triggering LLM chat completion", message_count=len(messages), model=self.chat_model)
        kwargs: dict[str, Any] = {
            "model": self.chat_model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        # Extract message and serialize manually to avoid raw Pydantic model usage outside
        msg = choice.message
        result: dict[str, Any] = {
            "role": msg.role,
            "content": msg.content,
        }
        if msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]

        # Return format expected by the Orchestrator with the choice finish_reason
        return {
            "message": result,
            "finish_reason": choice.finish_reason,
        }

    async def get_embedding(self, text: str) -> list[float]:
        """Request a vector representation of the source string using the Embedding Model."""
        logger.debug("Generating document embedding", model=self.embedding_model)
        response = await self.client.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        return response.data[0].embedding
