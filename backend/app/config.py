"""Typed application settings loaded from environment variables."""

import os
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Exprofit API"
    app_env: str = "development"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    database_url: str = (
        "postgresql+psycopg://exprofit:change-me@localhost:5432/exprofit"
    )
    auth_secret_key: str = ""
    frontend_base_url: str = ""
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

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Fail at startup rather than issuing tokens with weak production secrets."""
        if self.app_env.strip().lower() == "production":
            secret = self.auth_secret_key.strip()
            if (
                len(secret) < 32
                or secret.lower() in {
                    "replace-with-a-random-secret-at-least-32-bytes-long",
                    "change-me",
                    "changeme",
                }
                or secret.lower().startswith(("replace-with-", "your-secret-", "change-me-"))
            ):
                raise ValueError(
                    "AUTH_SECRET_KEY must be a non-placeholder value of at least 32 characters in production"
                )
            database = urlparse(self.database_url)
            if (
                "change-me" in self.database_url.lower()
                or database.hostname in {None, "localhost", "127.0.0.1", "::1"}
            ):
                raise ValueError(
                    "DATABASE_URL must point to a configured production database"
                )
        return self

    @field_validator("database_url", mode="before")
    @classmethod
    def use_installed_postgres_driver(cls, value: str) -> str:
        """Use psycopg 3 for Render's standard PostgreSQL connection URL."""
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @field_validator("frontend_base_url", mode="before")
    @classmethod
    def default_frontend_url(cls, value: str) -> str:
        """Use Render's own public URL for links when no explicit URL is configured."""
        if not value:
            return os.getenv("RENDER_EXTERNAL_URL", "http://localhost:5173")
        return value

    @property
    def missing_email_settings(self) -> list[str]:
        """List missing SMTP setting names without exposing their values."""
        missing = []
        if not self.smtp_host.strip():
            missing.append("SMTP_HOST")
        if not self.smtp_username.strip():
            missing.append("SMTP_USERNAME")
        if not self.smtp_password.strip():
            missing.append("SMTP_PASSWORD")
        if not self.smtp_from_email.strip():
            missing.append("SMTP_FROM_EMAIL")
        if self.smtp_port <= 0:
            missing.append("SMTP_PORT")
        return missing

    @property
    def email_delivery_configured(self) -> bool:
        """Return whether all required SMTP sender settings are present."""
        return not self.missing_email_settings

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance."""
    return Settings()
