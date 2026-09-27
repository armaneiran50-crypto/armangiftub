from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="LOGIRAD_", extra="ignore")

    database_url: str = "sqlite:///./logirad.db"
    jwt_secret: str = "change-me-in-production"
    jwt_ttl_minutes: int = 60 * 12
    cors_origins: str = "http://localhost:3000"

    # Seed admin (only created when no users exist)
    admin_email: str = "admin@logirad.local"
    admin_password: str = "change-me"

    # AI (optional). The SDK reads ANTHROPIC_API_KEY itself.
    ai_enabled: bool = False
    ai_model: str = "claude-opus-5"

    # Minimum number of providers dispatched per RFQ (doc §12: 2–3 comparable quotes)
    dispatch_top_n: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
