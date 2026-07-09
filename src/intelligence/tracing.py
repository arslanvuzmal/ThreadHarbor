from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Optional

from langfuse import Langfuse

from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Global Tracing Manager instance
_tracing_manager_instance: Optional["TracingManager"] = None


class TracingManager:
    """Manages the Langfuse client initialization and trace dispatching."""

    def __init__(self) -> None:
        """Initializes the TracingManager from application configuration."""
        settings = get_settings()
        self.public_key = settings.LANGFUSE_PUBLIC_KEY
        self.secret_key = settings.LANGFUSE_SECRET_KEY
        self.host = settings.LANGFUSE_HOST

        self.enabled = bool(self.public_key and self.secret_key)
        self.langfuse: Langfuse | None = None

        if self.enabled:
            try:
                self.langfuse = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=self.host,
                )
                logger.info("Langfuse tracing client successfully initialized")
            except Exception as e:
                logger.warning(
                    "Failed to initialize Langfuse client; disabling observability tracing",
                    error=str(e),
                )
                self.enabled = False
        else:
            logger.info("Langfuse keys not configured; tracing is in no-op mode")


def get_tracing_manager() -> TracingManager:
    """Provides a singleton-like instance of TracingManager."""
    global _tracing_manager_instance
    if _tracing_manager_instance is None:
        _tracing_manager_instance = TracingManager()
    return _tracing_manager_instance


class TraceSpan:
    """Represents an active trace span and allows recording generation steps and exceptions."""

    def __init__(self, trace: Any | None = None) -> None:
        """Initializes the TraceSpan.

        Args:
            trace: Active Langfuse trace object if tracing is enabled, otherwise None.
        """
        self.trace = trace

    def record_generation(
        self,
        prompt: str,
        completion: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        _latency_ms: int | None = None,
    ) -> None:
        """Records an LLM generation node inside the active trace.

        Args:
            prompt: Text prompt input to LLM.
            completion: Output completion text from LLM.
            model: Name of the LLM model.
            prompt_tokens: Tokens used in prompt.
            completion_tokens: Tokens used in completion.
            _latency_ms: Total latency of generation in milliseconds.
        """
        if not self.trace:
            return

        try:
            # Records a generation span in Langfuse
            # usage dict must be fully formatted according to Langfuse spec
            self.trace.generation(
                name="llm-generation",
                model=model,
                input=prompt,
                output=completion,
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
            )
            logger.debug(
                "Recorded generation in Langfuse trace",
                model=model,
                total_tokens=prompt_tokens + completion_tokens,
            )
        except Exception as e:
            logger.error("Failed to append generation to Langfuse trace", error=str(e))

    def record_exception(self, exc: Exception) -> None:
        """Records an error event node inside the active trace.

        Args:
            exc: Caught exception.
        """
        if not self.trace:
            return

        try:
            self.trace.event(
                name="exception",
                input=str(exc),
                metadata={
                    "error_class": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            logger.debug("Recorded exception event in Langfuse trace", exc_class=type(exc).__name__)
        except Exception as e:
            logger.error("Failed to append exception event to Langfuse trace", error=str(e))


@asynccontextmanager
async def trace_llm_call(session_id: str, user_input: str) -> AsyncIterator[TraceSpan]:
    """An asynchronous context manager that wraps an LLM and RAG call lifecycle.

    Silently no-ops if Langfuse is disabled or unconfigured.

    Args:
        session_id: The active user's conversation session ID.
        user_input: Raw text query input.

    Yields:
        A TraceSpan instance to record generation details or exceptions.
    """
    manager = get_tracing_manager()
    trace = None

    if manager.enabled and manager.langfuse:
        try:
            # Initialize a new trace via Langfuse SDK
            trace = manager.langfuse.trace(  # type: ignore[attr-defined]
                name="whatsapp-orchestrator-call",
                session_id=session_id,
                input=user_input,
            )
            logger.debug("Started Langfuse trace", session_id=session_id)
        except Exception as e:
            logger.error("Failed to initialize trace in Langfuse", error=str(e))

    span = TraceSpan(trace=trace)

    try:
        yield span
    except Exception as exc:
        span.record_exception(exc)
        raise exc
    finally:
        if manager.enabled and manager.langfuse:
            try:
                # Flush traces asynchronously
                manager.langfuse.flush()
                logger.debug("Flushed Langfuse trace batch", session_id=session_id)
            except Exception as e:
                logger.error("Failed to flush Langfuse trace", error=str(e))
