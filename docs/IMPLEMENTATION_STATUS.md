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

No application behavior is marked verified in this initial documentation commit. As implementation proceeds, record the date, command, environment, result, and any remaining limitation for each completed unit.


## Build 2 update — 2026-10-18

Committed PostgreSQL configuration, SQLAlchemy engine and request-scoped session dependency, a Business model, Alembic configuration, and the initial businesses-table migration. A SQLite-backed model test is present. The migration has not been run against a live PostgreSQL database, and automated CI checks have not been confirmed passing. The frontend lockfile and clean-install verification also remain outstanding.
