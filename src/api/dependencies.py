from src.utils.config import Settings, get_settings


def get_app_settings() -> Settings:
    """Dependency to provide application Settings."""
    return get_settings()
