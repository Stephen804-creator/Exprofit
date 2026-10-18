"""Workspace request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator


class BusinessCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    currency_code: str = Field(default="NGN", min_length=3, max_length=3)
    timezone: str = Field(default="Africa/Lagos", min_length=1, max_length=64)
    display_name: str | None = Field(default=None, max_length=120)
    organization_label: str = Field(default="Departments", min_length=1, max_length=32)
    logo_url: AnyHttpUrl | None = None

    @field_validator("name", "organization_label")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value cannot be blank")
        return cleaned

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise ValueError("currency_code must be a three-letter code")
        return cleaned

    @field_validator("logo_url")
    @classmethod
    def require_https_logo(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is not None and value.scheme != "https":
            raise ValueError("logo_url must use HTTPS")
        return value


class BusinessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    display_name: str | None
    workspace_type: str
    organization_label: str
    logo_url: str | None
    currency_code: str
    timezone: str
    created_at: datetime
    updated_at: datetime
