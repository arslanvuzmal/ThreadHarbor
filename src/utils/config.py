from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the WhatsApp Support Bot loaded from environment variables."""

    WHATSAPP_VERIFY_TOKEN: str
    WHATSAPP_APP_SECRET: str
    WHATSAPP_ACCESS_TOKEN: str
    REDIS_URL: str = "redis://localhost:6379/0"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_settings() -> Settings:
    """Helper function to load and return the Settings instance."""
    # We ignore the type checker complaints for missing initial args because
    # pydantic-settings loads them from env vars/file at runtime.
    return Settings()  # type: ignore[call-arg]
