import os

# Set environment variables BEFORE importing the app or Settings so they are loaded successfully.
os.environ["WHATSAPP_VERIFY_TOKEN"] = "test_verify_token_123"
os.environ["WHATSAPP_APP_SECRET"] = "test_app_secret_abc"
os.environ["WHATSAPP_ACCESS_TOKEN"] = "test_access_token_xyz"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["LOG_LEVEL"] = "DEBUG"

import hmac
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.utils.config import Settings, get_settings


@pytest.fixture(autouse=True)
def mock_env_vars() -> Generator[None, None, None]:
    """Fixture to ensure consistent mock environment variables for settings."""
    old_env = dict(os.environ)
    os.environ["WHATSAPP_VERIFY_TOKEN"] = "test_verify_token_123"
    os.environ["WHATSAPP_APP_SECRET"] = "test_app_secret_abc"
    os.environ["WHATSAPP_ACCESS_TOKEN"] = "test_access_token_xyz"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    os.environ["LOG_LEVEL"] = "DEBUG"
    yield
    os.environ.clear()
    os.environ.update(old_env)


@pytest.fixture
def app_settings() -> Settings:
    """Fixture returning the application settings loaded from mock environment."""
    return get_settings()


@pytest.fixture
def client() -> TestClient:
    """Fixture providing a TestClient for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def signature_generator(app_settings: Settings) -> Any:
    """Fixture that generates a valid X-Hub-Signature-256 header for arbitrary payloads."""

    def _generate(payload: bytes, secret: str | None = None) -> str:
        app_secret = secret or app_settings.WHATSAPP_APP_SECRET
        mac = hmac.new(app_secret.encode("utf-8"), payload, "sha256")
        return f"sha256={mac.hexdigest()}"

    return _generate
