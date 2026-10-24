"""Input and output schemas for products, customers, and budgets."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    sku: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Product name cannot be blank")
        return value

    @field_validator("sku", "description")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    name: str
    sku: str | None
    description: str | None
    unit_price: Decimal | None
    unit_cost: Decimal | None
    currency_code: str
    is_active: bool
    created_at: datetime


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Customer name cannot be blank")
        return value


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    name: str
    email: str | None
    phone: str | None
    notes: str | None
    is_active: bool
    created_at: datetime


class BudgetCreate(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    period_start: date
    period_end: date
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    warning_threshold_percent: int = Field(default=80, ge=1, le=200)

    @field_validator("category")
    @classmethod
    def clean_category(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Budget category cannot be blank")
        return value


class BudgetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    category: str
    currency_code: str
    period_start: date
    period_end: date
    amount: Decimal
    warning_threshold_percent: int
    created_at: datetime


class FinancialGoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    goal_kind: str = Field(pattern="^(revenue|gross_profit)$")
    target_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    period_start: date
    period_end: date

    @field_validator("name")
    @classmethod
    def clean_goal_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Goal name cannot be blank")
        return cleaned


class FinancialGoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    name: str
    goal_kind: str
    currency_code: str
    target_amount: Decimal
    period_start: date
    period_end: date
    is_active: bool
    created_at: datetime
