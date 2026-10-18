# Exprofit API

FastAPI backend for Exprofit, an expense tracking and profitability assistant for small businesses.

## Local setup

Use Python 3.11+. From this directory, create and activate a virtual environment, copy the root `.env.example` to `.env`, replace `AUTH_SECRET_KEY` with a unique random value of at least 32 bytes, then install and run:

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
alembic upgrade head
python -m uvicorn app.main:app --reload
```

The configured `DATABASE_URL` must point to a PostgreSQL database. Do not commit `.env`, real credentials, or real financial records. The `/health` endpoint is a liveness check and does not require a database.

## Implemented API slice

- `POST /auth/register` creates an account and private Solo workspace.
- `POST /auth/login` authenticates an account.
- `GET /auth/me` returns the current identity, including whether its email is verified.
- `POST /auth/logout` revokes the current access session.
- `GET/POST /businesses` lists or creates the caller's business workspaces.
- `/businesses/{business_id}/transactions` supports authenticated transaction create/list/read/update/void operations.

Protected business and transaction endpoints require a bearer token and verify business membership server-side. Access tokens expire after 30 minutes; logout revokes the associated database session. Passwords are Argon2-hashed. Login/register rate limiting and broader production hardening are not yet implemented, so this is not yet a production release.

## Verification

```bash
python -m ruff check .
python -m pytest
alembic upgrade head
```

CI run [#97](https://github.com/Stephen804-creator/Exprofit/actions/runs/39121683770) passed Ruff, PostgreSQL migrations, 19 backend tests, frontend typecheck, and frontend production build. One third-party Starlette/AnyIO deprecation warning remains. The root README and `docs/IMPLEMENTATION_STATUS.md` track the wider product plan and current verification state.


Email verification endpoints:
- `POST /auth/request-email-verification` sends a single-use verification link to the authenticated account when SMTP is configured.
- `POST /auth/verify-email` accepts JSON with a `token` field and consumes a valid challenge.

Configure `FRONTEND_BASE_URL`, `EMAIL_VERIFICATION_TTL_MINUTES`, and the `SMTP_*` settings in the root `.env.example`. Tokens are hashed in the database and are not returned by the API. Email verification does not yet gate login; it must be required by the future invitation acceptance endpoint.


Workspace invitation endpoints:
- `POST /businesses/{business_id}/invitations` creates and emails a recipient-bound invite.
- `POST /invitations/accept` accepts a pending invite using JSON `{"token":"..." }`.
- `POST /businesses/{business_id}/invitations/{invitation_id}/revoke` revokes a pending invite.

Invitation acceptance requires the authenticated account's email to be verified and to match the invited recipient exactly. Configure SMTP, `FRONTEND_BASE_URL`, and `WORKSPACE_INVITATION_TTL_MINUTES=30`. Raw invite tokens are never returned by the API or stored in the database. The UI, rate limiting, audit events, and notification workflows are not implemented yet.
