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

Protected business and transaction endpoints require a bearer token and verify business membership server-side. Access tokens expire after 30 minutes; logout revokes the associated database session. Passwords are Argon2-hashed. Database-backed login/register rate limits are implemented on the current feature branch. Proxy-aware IP handling, browser end-to-end coverage, and broader production verification remain outstanding, so passing CI alone does not make this a production release.

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


Workspace invitation and review endpoints:
- `POST /businesses/{business_id}/invitations` creates a shareable link and returns it once. The owner chooses an expiry from 1 to 720 hours.
- `POST /invitations/apply` accepts an authenticated applicant's identifying details and JPEG face photo, with explicit consent.
- `GET /businesses/{business_id}/invitation-applications` lists pending applications for the workspace Owner.
- `GET /businesses/{business_id}/invitation-applications/{application_id}/photo` streams a private pending photo to the workspace Owner.
- `POST /businesses/{business_id}/invitation-applications/{application_id}/approve` approves and grants the invitation's role/permissions.
- `POST /businesses/{business_id}/invitation-applications/{application_id}/reject` rejects the applicant and disables the link.
- `POST /businesses/{business_id}/invitations/{invitation_id}/revoke` revokes an unused link.

Raw invitation tokens are never stored; only SHA-256 digests are persisted. Application submission alone does not grant access. The workflow does not require SMTP or email verification. Photos are limited to JPEG up to 15 MiB, stored privately in PostgreSQL for pending review, and deleted after approval, rejection, revocation, or expiry cleanup. The photo supports manual owner-assisted recognition only; it is not biometric authentication. Manual browser/end-to-end checks and production rate limiting remain outstanding.


The React client includes sign-in/register, workspace selection/creation, shareable-link creation/copying, an applicant form with camera/photo input and consent, and a private owner review screen. It uses `VITE_API_BASE_URL`; the UI does not replace server-side authorization and is not yet the complete bookkeeping dashboard.


Member administration and audit endpoints:
- `GET /businesses/{business_id}/members`
- `PATCH /businesses/{business_id}/members/{membership_id}`
- `POST /businesses/{business_id}/members/{membership_id}/suspend`
- `POST /businesses/{business_id}/members/{membership_id}/revoke`
- `POST /businesses/{business_id}/members/{membership_id}/reinstate`
- `GET /businesses/{business_id}/audit-events`

All are server-authorized with Staff Administration permissions. State-changing member actions require a reason and produce audit events. Timed suspension uses `duration_hours` (1–720); when the deadline passes, a protected request or member-list read automatically reinstates the membership. Audit history is read-only through the API. Notification workflows and production audit-retention controls remain future work.


Voluntary departure endpoint:
- `POST /businesses/{business_id}/leave` with `confirmation_phrase`, `password`, `reason`, and optional `notice_hours` (1–720).

The exact phrase must be `I want to leave`. Immediate departure revokes membership; scheduled departure is finalized when its deadline passes and is recorded in audit history. Owners cannot leave until an ownership-transfer workflow exists.


The React client includes initial collaboration controls for authorized administrators and self-service departure for non-owner members. The signed-in user's own membership is available from `GET /businesses/{business_id}/membership`; this endpoint does not expose the member directory. Manual browser/end-to-end testing remains outstanding.
