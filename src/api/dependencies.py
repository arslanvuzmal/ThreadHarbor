import httpx

from src.handoff.client import BaseHandoffClient, MockZendeskClient
from src.utils.config import Settings, get_settings

# Global shared HTTP client with connection pooling for efficient reuse
_global_http_client: httpx.AsyncClient | None = None

# Global Mock CCaaS client instance so that it acts as our ticketing database
_global_handoff_client = MockZendeskClient()


async def get_http_client() -> httpx.AsyncClient:
    """Dependency to provide a shared async HTTP client with connection pooling.
    
    Returns:
        A shared httpx.AsyncClient instance.
    """
    global _global_http_client
    if _global_http_client is None or _global_http_client.is_closed:
        _global_http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        )
    return _global_http_client


def get_app_settings() -> Settings:
    """Dependency to provide application Settings."""
    return get_settings()


def get_handoff_client() -> BaseHandoffClient:
    """Dependency to provide the global BaseHandoffClient instance."""
    return _global_handoff_client
