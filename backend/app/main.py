"""Exprofit API entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Expense tracking and evidence-backed profitability insights for small businesses.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)


@app.get("/health", tags=["operations"])
def health_check() -> dict[str, str]:
    """Liveness endpoint; it intentionally does not depend on a database."""
    return {"status": "ok", "service": "exprofit-api"}


@app.get("/", tags=["operations"])
def root() -> dict[str, str]:
    """Small discovery response for developers."""
    return {"name": settings.app_name, "docs": "/docs", "health": "/health"}
