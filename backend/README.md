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

- `POST /auth/register` creates an account and first NGN business workspace.
- `POST /auth/login` authenticates an account.
- `GET /auth/me` returns the current identity.
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

The repository CI is configured to run backend lint/tests and PostgreSQL migrations, but a passing run has not yet been confirmed. The root README and `docs/IMPLEMENTATION_STATUS.md` track the wider product plan and current verification state.
