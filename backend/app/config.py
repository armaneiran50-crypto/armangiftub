from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="LOGIRAD_", extra="ignore")

    env: str = "development"  # set to "production" on the server
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

    # Public URL of the site, used in notification links
    public_url: str = "http://localhost:3000"

    # Outbound email (optional). When smtp_host is empty, notifications are only logged.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Logirad <no-reply@logirad.local>"
    smtp_starttls: bool = True

    # Minimum number of providers dispatched per RFQ (doc §12: 2–3 comparable quotes)
    dispatch_top_n: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
