# Implementation Status

This file separates planned work from verified work. A requirement is not marked complete until the relevant files exist and its checks have been run.

## Repository foundation
- [x] New Exprofit repository established.
- [x] Product scope and safety principles documented.
- [x] Target architecture documented.
- [x] Acceptance checkpoints documented.
- [ ] Runnable frontend/backend baseline.
- [ ] Dependency versions pinned and lockfiles committed.
- [ ] Automated CI checks.
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

The application shell and initial database code are committed, but automated checks and PostgreSQL migration execution have not yet been confirmed. Record the date, command, environment, result, and any remaining limitation for each completed unit.


## Build 2 update — 2026-10-18

Committed PostgreSQL configuration, SQLAlchemy engine and request-scoped session dependency, a Business model, Alembic configuration, and the initial businesses-table migration. A SQLite-backed model test is present. The migration has not been run against a live PostgreSQL database, and automated CI checks have not been confirmed passing. The frontend lockfile and clean-install verification also remain outstanding.


## Build 3 update — 2026-10-18

Added a transaction ORM model with fixed-precision decimal amounts, business foreign key, income/expense direction, draft/posted/void states, currency constraints, date/status indexes, and an optional business-scoped idempotency key. Added Pydantic input/output schemas, service-layer create/list/get/update/void operations, a migration, and tests for lifecycle behavior, business scoping, currency mismatch, invalid values, and duplicate request keys.

Transaction operations are not yet exposed as public HTTP endpoints. This is deliberate: the authentication and authorization unit must be completed before routes can safely accept requests for a business ID. The new tests and PostgreSQL migration step are committed but have not yet been observed passing in GitHub Actions.


## Build 4 update — 2026-10-18 (in progress; not accepted)

Added the User and BusinessMembership ORM models, registered them in the model package, added the users/memberships Alembic migration, pinned Argon2 password-hashing and signed-token dependencies, and added an auth-secret setting plus request/response schemas. A password-hashing helper is present. This is only a partial foundation: token issuance/validation, current-user dependencies, registration/login routes, business membership enforcement, protected transaction routes, and authentication tests are not complete or verified. Do not treat Build 4 as complete or deploy this state as an authenticated finance application. The migration and CI remain unverified.
