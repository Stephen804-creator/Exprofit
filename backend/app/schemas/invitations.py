"""Request and response schemas for workspace invitations."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

ALLOWED_PERMISSION_KEYS = {
    f"{domain}:{action}"
    for domain in ("sales", "purchases", "expenses", "inventory", "staff_administration")
    for action in ("read", "write")
}


class InvitationCreate(BaseModel):
    recipient_email: EmailStr
    role: Literal["admin", "worker"]
    permissions: dict[str, bool] = Field(default_factory=dict)

    @field_validator("recipient_email")
    @classmethod
    def normalize_recipient_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: dict[str, bool]) -> dict[str, bool]:
        unknown = set(value) - ALLOWED_PERMISSION_KEYS
        if unknown:
            raise ValueError(f"Unsupported permission keys: {', '.join(sorted(unknown))}")
        return value


class InvitationAcceptRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    recipient_email: EmailStr
    role: str
    permissions: dict[str, bool]
    expires_at: datetime


class InvitationAccepted(BaseModel):
    business_id: UUID
    role: str
    status: str
