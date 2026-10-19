"""Typed application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Exprofit API"
    app_env: str = "development"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    database_url: str = (
        "postgresql+psycopg://exprofit:change-me@localhost:5432/exprofit"
    )
    auth_secret_key: str = ""
    frontend_base_url: str = "http://localhost:5173"
    email_verification_ttl_minutes: int = 30
    workspace_invitation_ttl_minutes: int = 30
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_starttls: bool = True
    hf_token: str = ""
    hf_gemma_model: str = "google/gemma-3-12b-it:fastest"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @field_validator("database_url", mode="before")
    @classmethod
    def use_installed_postgres_driver(cls, value: str) -> str:
        """Use psycopg 3 for Render's standard PostgreSQL connection URL."""
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @property
    def email_delivery_configured(self) -> bool:
        """Return whether all required SMTP sender settings are present."""
        return bool(self.smtp_host.strip() and self.smtp_from_email.strip())

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance."""
    return Settings()
