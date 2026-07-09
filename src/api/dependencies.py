from src.handoff.client import BaseHandoffClient, MockZendeskClient
from src.utils.config import Settings, get_settings

# Global Mock CCaaS client instance so that it acts as our ticketing database
_global_handoff_client = MockZendeskClient()


def get_app_settings() -> Settings:
    """Dependency to provide application Settings."""
    return get_settings()


def get_handoff_client() -> BaseHandoffClient:
    """Dependency to provide the global BaseHandoffClient instance."""
    return _global_handoff_client
