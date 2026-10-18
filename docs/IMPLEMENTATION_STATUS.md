# Implementation Status

This file separates planned work from verified work. A requirement is not marked complete until the relevant files exist and its checks have been run.

## Repository foundation
- [x] New Exprofit repository established.
- [x] Product scope and safety principles documented.
- [x] Target architecture documented.
- [x] Acceptance checkpoints documented.
- [x] Runnable frontend/backend baseline and health endpoint tests.
- [ ] Dependency versions pinned and lockfiles committed.
- [x] Automated CI checks (run #97 passed).
- [ ] Clean-clone setup verified.

## Ordered implementation units

1. **Project baseline** — repository layout, pinned dependencies, environment examples, formatting/lint configuration, health endpoint, and CI.
2. **Database foundation** — PostgreSQL configuration, models, migrations, and isolated test database.
3. **Transaction integrity** — transaction schemas, validation, CRUD lifecycle, currency handling, and audit behavior.
4. **Authentication and access control** — secure identity, business ownership, session management, and authorization tests.
5. **Receipt lifecycle** — private storage, upload validation, OCR extraction, review/confirmation, duplicate checks, and cleanup.
6. **Financial overview** — date-filtered summaries, category aggregation, currency separation, and explicit metric labels.
7. **Profitability engine** — documented financial definitions and deterministic calculations with edge-case tests.
8. **MarginGuard investigator** — transparent findings with evidence references, assumptions, and uncertainty.
9. **What-if simulator** — scenario calculations that never mutate actual records.
10. **Financial brief and optional AI** — grounded explanations with a non-AI fallback.
11. **User experience and hardening** — responsive workflows, accessibility, security review, and end-to-end tests.
12. **Release readiness** — deployment configuration, documentation, demo data that contains no personal information, and final challenge submission checklist.

## Verification log

The latest verification is GitHub Actions run #97 on commit `7af4001f429b76416928d8f27d8f911326d6475c` (2026-10-18): Ruff passed, `alembic upgrade head` passed against PostgreSQL 16, 19 pytest tests passed, and frontend typecheck/build passed. One third-party Starlette/AnyIO deprecation warning was emitted. Continue recording any new verification with the exact commit and environment.


## Build 2 update — 2026-10-18

Committed PostgreSQL configuration, SQLAlchemy engine and request-scoped session dependency, a Business model, Alembic configuration, and the initial businesses-table migration. A SQLite-backed model test is present. The migration has not been run against a live PostgreSQL database, and automated CI checks have not been confirmed passing. The frontend lockfile and clean-install verification also remain outstanding.


## Build 3 update — 2026-10-18

Added a transaction ORM model with fixed-precision decimal amounts, business foreign key, income/expense direction, draft/posted/void states, currency constraints, date/status indexes, and an optional business-scoped idempotency key. Added Pydantic input/output schemas, service-layer create/list/get/update/void operations, a migration, and tests for lifecycle behavior, business scoping, currency mismatch, invalid values, and duplicate request keys.

Transaction operations are not yet exposed as public HTTP endpoints. This is deliberate: the authentication and authorization unit must be completed before routes can safely accept requests for a business ID. The latest CI run #97 later confirmed Ruff, the PostgreSQL migration chain, and all backend tests pass.


## Build 4 update — 2026-10-18 (implemented; verification pending)

Implemented User, BusinessMembership, and revocable AuthSession models with migrations; Argon2 password hashing; signed, 30-minute access tokens bound to persisted sessions; registration, login, current-user, and logout endpoints; business workspace endpoints; and protected business-scoped transaction endpoints. Logout revokes the session in the database. Registration creates the user's first NGN/Africa-Lagos workspace and owner membership. Authorization checks membership server-side and returns 404 for workspaces the user cannot access. Added API tests for registration, login failure, duplicate email, logout revocation, cross-business isolation, and the transaction lifecycle. Added `email-validator` for Pydantic `EmailStr` and documented `AUTH_SECRET_KEY`.

The two route modules that previously existed as drafts (`backend/app/api/routes/businesses.py` and `backend/app/api/routes/transactions.py`) are now registered in `backend/app/main.py` and implemented behind authentication/authorization. The stale non-revocable `backend/app/auth_tokens.py` helper was removed; `backend/app/access_tokens.py` is the active session-bound token implementation.

**Verification result:** GitHub Actions run #97 passed Ruff, PostgreSQL 16 migrations, 19 pytest tests, frontend typecheck, and frontend production build. One third-party Starlette/AnyIO deprecation warning remains. Login/register rate limiting, security-event auditing, and broader production hardening remain follow-up work; this is not yet a production release.


## Workspace collaboration foundation — in progress

Branch: feat/workspace-collaboration-foundation.

Added a workspace collaboration design, schema fields for Solo versus Business workspaces, configurable workspace display identity, membership role/status/permissions fields, and an initial migration. Registration now creates a private Solo workspace by default; creating a shared business is a separate action. Membership listing and protected transaction access reject non-active memberships.

Not yet complete: invitation generation/verification/acceptance/expiry/revocation; granular permission enforcement; workspace switching UI; member management; password-confirmed voluntary leave; reasoned suspension/revocation; timed suspension; notifications; and audit history. Do not describe these as available until implemented and tested.

Verification status: pending CI for this branch. No passing test result is claimed for these changes yet.
