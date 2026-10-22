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

Verification result: GitHub Actions run #107 passed on commit 25342ccb6bbf491dedf79c9a66fb1841848dfdc7. Ruff passed, the PostgreSQL 16 migration chain applied, all 20 backend tests passed, and frontend typecheck/production build passed. One existing third-party Starlette/AnyIO deprecation warning remains. This verifies the branch checks, not the unfinished invitation or granular-permission features.


### Permission policy slice — implementation added, CI pending

Added a centralized permission policy and applied it to transaction creation, listing, reading, editing, and voiding. Owners have workspace financial access by role; Admins and Workers require explicit domain/action grants. Transaction lists filter out domains the member cannot read. New API coverage verifies a worker with Sales-only access cannot read or mutate expense records. The implementation uses keys such as `sales:read` and `sales:write`; email verification, invitations, member administration, audit events, and workspace UI remain unfinished. Do not mark this slice verified until CI passes on the current branch head.


### Verified email infrastructure — implementation added, CI pending

Added a user email-verification flag, token model and migration, SMTP configuration/delivery adapter, authenticated request endpoint, and one-time token verification endpoint. Only a SHA-256 digest is stored; tokens expire after 30 minutes by default, older unconsumed tokens are invalidated on a new request, and a consumed token cannot be reused. Tests cover missing delivery configuration, successful verification, hashed storage, and replay rejection. Configure SMTP before using the email flow. The frontend verification page, resend throttling, password recovery, and invitation acceptance are not implemented. Do not mark this slice verified until CI passes on the latest branch head.


### Workspace invitations — implementation added; CI verified

Added the invitation model/migration, permission-validated request schemas, SMTP email delivery, and create/accept/revoke endpoints. Owner/Admin authorization is checked server-side; only the Owner can invite Admins, and Admins can only delegate Worker permissions they themselves hold. Invitations use hashed random tokens, a 30-minute default expiry, exact verified-recipient email matching, single-use acceptance, and revocation. Acceptance creates/reactivates membership without transferring Solo records.

GitHub Actions run #39136370512 passed on commit `1fbdaae4e7f186627254755bbc6357f4d917d4c9`: Ruff, backend tests (28 passed), PostgreSQL migrations, frontend typecheck, and production build passed. Frontend invitation/verification screens, rate limiting, audit events, notifications, password recovery, and production hardening are still unfinished. This CI result is not a production-readiness claim.


### Frontend account and workspace switcher — implementation added, CI pending

The React UI now supports registration/sign-in, displays email-verification state and request controls, verifies emailed tokens at `/verify-email`, accepts invitation tokens at `/accept-invitation`, lists the user's active Solo/business workspaces, switches the selected workspace, and creates a separate business workspace. The short-lived bearer token is kept in sessionStorage for the current browser tab; this is still exposed to same-origin JavaScript and is not equivalent to HttpOnly cookie storage. Email and invitation tokens are removed from the visible URL after being captured in memory. The UI is an initial functional slice, not a full financial dashboard. Confirm the latest CI run before considering this frontend slice verified.


### Member administration and audit history — implementation added, CI verified

Added a durable audit model/migration and helper, member list/update/suspend/revoke/reinstate endpoints, read-only audit history, and automatic timed-suspension reinstatement at the API boundary. Membership changes require reasons and create audit events in the same transaction. Owner membership and self-management are blocked; Admins can manage Workers only. Revoked memberships require a new invitation to rejoin.

GitHub Actions run #39137366478 passed on commit `f482f8c8b38a49854451313746c2ee80c8c29dea`: Ruff, all 32 backend tests, PostgreSQL 16 migrations, frontend typecheck, and production build passed. One third-party Starlette/AnyIO deprecation warning remains. Notifications, password recovery, rate limiting, audit retention/export controls, full financial dashboard, and production session hardening remain incomplete.


### Voluntary leave and timed departure — implementation added, CI verified

Added `POST /businesses/{business_id}/leave` with exact phrase validation (`I want to leave`), password re-authentication, required reason, immediate departure, and optional 1–720-hour notice. Scheduled departure is finalized at the API boundary when its effective time passes and produces an audit event. Owners cannot leave until ownership transfer is supported. Accepting a new invitation clears a previous departure schedule.

GitHub Actions run #39137882951 passed on commit `0fbf0b0dacf723779eb20e829ee890645d6c314d0`: Ruff, 35 backend tests, PostgreSQL 16 migrations, frontend typecheck, and production build passed. The model-index alignment follow-up triggered another CI run. Rate limiting and the frontend leave-management UI are not implemented.


### Collaboration and voluntary-leave UI — implementation added, CI verified

The React business workspace panel now shows members and recent audit events to authorized users, creates invitations, edits role/permission grants, and supports suspend/revoke/reinstate actions. It includes a self-service leave form with exact phrase, password re-authentication, reason, and optional notice period. The frontend calls a dedicated own-membership endpoint so a Worker can view their own status without access to the member directory.

GitHub Actions run #39138684168 passed on commit `2884462c60bd233878f4e446dc9db2e3b1bdd764`: Ruff, 35 backend tests, PostgreSQL migrations, frontend typecheck, and production build passed. This is build/test verification, not manual browser or production verification. Rate limiting, notifications, ownership transfer, full transaction/receipt dashboard, audit retention/export controls, and production session hardening remain incomplete.


### Shareable invitation and owner-review flow — implemented; CI verified

The invitation workflow no longer requires SMTP or verified-email matching. Only the workspace Owner can create/revoke invitation links and review applications. The Owner chooses an expiry from 1 to 720 hours and shares the generated link through any channel. The applicant signs in, submits a name, identifying details, optional phone, a JPEG photo up to 2 MB, and explicit consent. The application remains pending until the Owner approves or rejects it; approval grants the invitation's assigned role/permissions. The raw link token is returned only at creation and only its SHA-256 digest is stored. Photos are private in PostgreSQL and are cleared after approval, rejection, revocation, or expiry cleanup. This is manual visual review, not biometric authentication.

GitHub Actions run #39140188754 passed on commit c8476b4e267865d4ab412a4c2013c2acdb85bd4d: Ruff, 36 backend tests, PostgreSQL 16 migrations, frontend typecheck, and production build passed. Manual mobile/browser testing, rate limiting, and production privacy/security review remain outstanding.

See [ROADMAP.md](ROADMAP.md) for deferred departments, messaging, notifications, advanced identity verification, private object storage, receipts, financial summaries, profitability, MarginGuard, simulation, and optional AI.


## Units 14–17 update — 2026-10-22 (merged; CI verified, production verification pending)

See [UNITS_14_17_IMPLEMENTATION.md](UNITS_14_17_IMPLEMENTATION.md) for scope, limitations, and acceptance gates.

- Unit 14: camera permission diagnosis/retry, baseline browser security headers, and database-backed authentication rate limits are implemented on the feature branch. CI and live Android/Render verification are pending.
- Unit 15: product/customer/budget models, migration, protected catalog APIs, and optional transaction attribution are implemented on the feature branch. Migration and cross-workspace validation tests are pending CI.
- Unit 16: product/customer gross-profitability endpoints and UI are implemented on the feature branch. Reports use explicitly attributed posted ledger transactions and do not estimate missing direct costs.
- Unit 17: category budget creation, budget-vs-actual calculation, threshold statuses, UI, and a multi-transaction regression test are implemented on the feature branch.
- Current feature-branch migration head is `20261022_0013`. Merged to `main` via PR #9 at commit `7923bd0d0d3780d20674043e4aac6bbe9f2824e6`. PR CI passed, including PostgreSQL migrations and the frontend build. Render/mobile acceptance checks and real Brevo email delivery remain unverified.


## Units 18–23 implementation branch — 2026-10-22

Branch: `feat/units-18-23-financial-operations`. These units are implemented on a feature branch and are not production-verified until CI and deployed checks pass.

- **18 Recurring payments:** workspace-scoped expected income/expense schedules; weekly/monthly/yearly recurrence; pause/resume; schedules never auto-post.
- **19 Cash-flow forecast:** projects historical daily averages and separately overlays dated expected recurring payments. Forecasts remain estimates, grouped by currency without conversion.
- **20 Alerts:** persistent idempotent budget-threshold and upcoming-payment alerts with read/dismiss actions. No email/SMS/push delivery or background scheduler is claimed.
- **21 Exports:** permission-checked posted-transaction CSV and date-bounded accountant summary grouped by currency/category; no tax filing or audit claims.
- **22 Onboarding:** non-blocking checklist based on existing workspace records.
- **23 Financial copilot:** deterministic recorded-data answer with optional Hugging Face explanation only when explicitly enabled; fallback remains available.

Verification pending on this branch: Ruff, backend tests, PostgreSQL migration chain through `20261022_0014`, frontend typecheck/build, and endpoint/workspace-isolation checks. Production deployment and live workflow checks are not yet verified.
