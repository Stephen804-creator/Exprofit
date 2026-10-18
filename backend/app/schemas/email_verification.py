"""Request/response schemas for email verification."""

from pydantic import BaseModel, Field


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class MessageResponse(BaseModel):
    message: str
