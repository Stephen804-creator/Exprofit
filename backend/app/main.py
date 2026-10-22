"""Exprofit API entry point and single-origin frontend hosting."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.auth import router as auth_router
from app.api.routes.businesses import router as businesses_router
from app.api.routes.catalog_finance import router as catalog_finance_router
from app.api.routes.financial import router as financial_router
from app.api.routes.intelligence import router as intelligence_router
from app.api.routes.invitations import router as invitations_router
from app.api.routes.members import router as members_router
from app.api.routes.transactions import router as transactions_router
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
app.include_router(catalog_finance_router)
app.include_router(invitations_router)
app.include_router(members_router)
app.include_router(transactions_router)
app.include_router(financial_router)
app.include_router(intelligence_router)


@app.get("/health", tags=["operations"])
def health_check() -> dict[str, str]:
    """Liveness endpoint; it intentionally does not depend on a database."""
    return {"status": "ok", "service": "exprofit-api"}


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@app.get("/", tags=["operations"], include_in_schema=False, response_model=None)
def root() -> FileResponse | dict[str, str]:
    """Serve the frontend in a combined deployment, or API info during local development."""
    index_file = FRONTEND_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {"name": settings.app_name, "docs": "/docs", "health": "/health"}


@app.get("/accept-invitation", tags=["operations"], include_in_schema=False)
def accept_invitation_page() -> FileResponse:
    """Serve the SPA entry point for shareable invitation links.

    This explicit route must be registered before the catch-all frontend mount;
    otherwise StaticFiles returns 404 for this client-side React route.
    """
    index_file = FRONTEND_DIST / "index.html"
    if not index_file.is_file():
        raise HTTPException(status_code=503, detail="Frontend build is unavailable")
    return FileResponse(index_file)


if FRONTEND_DIST.is_dir():
    # API routes and explicit frontend routes are registered first.
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
