"""Request and response schemas for financial transactions."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransactionCreate(BaseModel):
    """User-supplied transaction fields; identity and timestamps are server-generated."""

    business_id: UUID
    direction: Literal["income", "expense"]
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency_code: str = Field(default="NGN", min_length=3, max_length=3)
    transaction_date: date
    description: str = Field(min_length=1, max_length=500)
    category: str | None = Field(default=None, max_length=80)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    status: Literal["draft", "posted"] = "draft"
    product_id: UUID | None = None
    customer_id: UUID | None = None

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str) -> str:
        """Store currency codes in canonical uppercase form."""
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency_code must be a three-letter currency code")
        return normalized

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        """Reject blank descriptions after trimming whitespace."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("description cannot be blank")
        return cleaned

    @field_validator("category")
    @classmethod
    def clean_category(cls, value: str | None) -> str | None:
        """Normalize an optional category and convert blank values to None."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class TransactionUpdate(BaseModel):
    """Editable fields; changing a void entry is not supported."""

    direction: Literal["income", "expense"] | None = None
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    transaction_date: date | None = None
    description: str | None = Field(default=None, min_length=1, max_length=500)
    category: str | None = Field(default=None, max_length=80)
    product_id: UUID | None = None
    customer_id: UUID | None = None

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("description cannot be blank")
        return cleaned

    @field_validator("category")
    @classmethod
    def clean_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class TransactionRead(BaseModel):
    """Transaction representation returned by application services."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    direction: Literal["income", "expense"]
    status: Literal["draft", "posted", "void"]
    amount: Decimal
    currency_code: str
    transaction_date: date
    description: str
    category: str | None
    product_id: UUID | None
    customer_id: UUID | None
    created_at: datetime
    updated_at: datetime
