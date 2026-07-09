from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the WhatsApp Support Bot loaded from environment variables."""

    WHATSAPP_VERIFY_TOKEN: str
    WHATSAPP_APP_SECRET: str
    WHATSAPP_ACCESS_TOKEN: str
    REDIS_URL: str = "redis://localhost:6379/0"
    LOG_LEVEL: str = "INFO"

    # Phase 03 additions
    OPENAI_API_KEY: str
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    LLM_CHAT_MODEL: str = "gpt-4o-mini"
    LLM_EMBEDDING_MODEL: str = "text-embedding-3-small"

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
