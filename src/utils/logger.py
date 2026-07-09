import logging
import sys
from typing import cast

import structlog


def configure_logger(log_level: str = "INFO") -> None:
    """Configure structured logging using structlog and standard library logging.

    Args:
        log_level: The logging level to set (e.g., DEBUG, INFO, WARNING, ERROR).
    """
    # Map string log levels to standard library logging levels
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure the standard library logging to use structlog's processor
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a configured structured logger.

    Args:
        name: Name of the logger (typically __name__).

    Returns:
        A structlog bound logger.
    """
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
