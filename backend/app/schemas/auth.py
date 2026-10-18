"""Request and response schemas for account access."""

from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    business_name: str = Field(min_length=1, max_length=120)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("business_name")
    @classmethod
    def normalize_business_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("business_name cannot be blank")
        return value

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 1800

class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    is_active: bool
