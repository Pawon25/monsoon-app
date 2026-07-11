"""
Application configuration loaded from environment variables.

All secrets (API keys) live server-side only and are never sent to the
frontend. See .env.example for the full list of required variables.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized app settings, populated from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Anthropic ---
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    # --- Weather ---
    openweather_api_key: str = ""
    openweather_base_url: str = "https://api.openweathermap.org/data/2.5"

    # --- CORS ---
    # Comma-separated list of allowed frontend origins in production.
    allowed_origins: str = "http://localhost:5500,http://127.0.0.1:5500"

    # --- Caching ---
    weather_cache_ttl_seconds: int = 300  # 5 min: avoid hammering weather API
    alert_poll_interval_seconds: int = 900  # 15 min, matches frontend polling

    # --- Rate limiting ---
    rate_limit_per_minute: int = 20

    # --- Supported languages surfaced to the frontend as suggestions.
    # NOTE: the backend does NOT hard-restrict to this list; Claude can
    # render output_language as free text (any language/dialect the user
    # requests), this is just what we advertise as first-class options.
    suggested_languages: List[str] = [
        "English",
        "Hindi",
        "Kannada",
        "Marathi",
        "Bengali",
        "Tamil",
        "Telugu",
        "Malayalam",
    ]

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
