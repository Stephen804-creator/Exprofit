"""Business workspace request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BusinessCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    currency_code: str = Field(default="NGN", min_length=3, max_length=3)
    timezone: str = Field(default="Africa/Lagos", min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name cannot be blank")
        return cleaned

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise ValueError("currency_code must be a three-letter code")
        return cleaned


class BusinessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    currency_code: str
    timezone: str
    created_at: datetime
    updated_at: datetime
