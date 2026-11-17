"""Exprofit API entry point and single-origin frontend hosting."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.auth import router as auth_router
from app.api.routes.businesses import router as businesses_router
from app.api.routes.catalog_finance import router as catalog_finance_router
from app.api.routes.financial import router as financial_router
from app.api.routes.financial_operations import router as financial_operations_router
from app.api.routes.intelligence import router as intelligence_router
from app.api.routes.invitations import router as invitations_router
from app.api.routes.members import router as members_router
from app.api.routes.transactions import router as transactions_router
from app.config import get_settings


class RequestBodyTooLarge(Exception):
    """Internal signal used to stop oversized request bodies while streaming."""


class RequestSizeLimitMiddleware:
    """Bound request bodies before FastAPI parses multipart uploads or JSON."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "").rstrip("/")
        if path == "/invitations/apply":
            limit = 22 * 1024 * 1024
        elif path.endswith("/receipts"):
            limit = 5 * 1024 * 1024 + 64 * 1024
        else:
            limit = 2 * 1024 * 1024

        headers = dict(scope.get("headers", []))
        raw_length = headers.get(b"content-length")
        if raw_length:
            try:
                if int(raw_length) > limit:
                    response = JSONResponse(
                        {"detail": "Request body exceeds the configured size limit."},
                        status_code=413,
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                response = JSONResponse(
                    {"detail": "Invalid Content-Length header."},
                    status_code=400,
                )
                await response(scope, receive, send)
                return

        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > limit:
                    raise RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLarge:
            response = JSONResponse(
                {"detail": "Request body exceeds the configured size limit."},
                status_code=413,
            )
            await response(scope, receive, send)


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Expense tracking and evidence-backed profitability insights for small businesses.",
)

app.add_middleware(RequestSizeLimitMiddleware)

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
app.include_router(financial_operations_router)


@app.middleware("http")
async def browser_security_headers(request, call_next):
    """Set baseline browser protections without blocking the camera or model CDN."""
    response = await call_next(request)
    if request.url.path.startswith(("/auth", "/businesses", "/invitations")):
        response.headers.setdefault("Cache-Control", "private, no-store")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(self), microphone=(), geolocation=()"
    )
    response.headers.setdefault("X-Frame-Options", "DENY")
    if request.url.scheme == "https":
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


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
