"""Exprofit API entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.businesses import router as businesses_router
from app.api.routes.financial import router as financial_router
from app.api.routes.invitations import router as invitations_router
from app.api.routes.intelligence import router as intelligence_router
from app.api.routes.members import router as members_router
from app.api.routes.transactions import router as transactions_router

app.include_router(intelligence_router)
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

app.include_router(auth_router)
app.include_router(businesses_router)
app.include_router(invitations_router)
app.include_router(members_router)
app.include_router(transactions_router)
app.include_router(financial_router)


@app.get("/health", tags=["operations"])
def health_check() -> dict[str, str]:
    """Liveness endpoint; it intentionally does not depend on a database."""
    return {"status": "ok", "service": "exprofit-api"}


@app.get("/", tags=["operations"])
def root() -> dict[str, str]:
    """Small discovery response for developers."""
    return {"name": settings.app_name, "docs": "/docs", "health": "/health"}
