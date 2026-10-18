# Exprofit Acceptance Plan

Use this checklist to decide whether a feature is actually complete. Record test commands and results in the implementation status log.

## Unit 1 — Reproducible baseline
- [ ] A clean checkout can install dependencies using documented commands.
- [ ] Backend starts with example configuration and exposes a health endpoint.
- [ ] Frontend starts and can reach the configured API.
- [ ] Versions are pinned and lockfiles are committed.
- [x] CI runs backend tests/lint and frontend type/build checks (CI run #97 passed).

## Unit 2 — Database
- [x] SQLAlchemy engine and request-scoped session dependency use configured database settings.
- [x] Migrations create the schema from an empty PostgreSQL 16 test database (CI run #97).
- [ ] A second migration run leaves the database at the current revision without errors (not separately verified).
- [x] The initial Business model persists UUID, name, currency code, timezone, and timestamps.
- [x] Database credentials are not committed; only example configuration is tracked.
- [x] Transaction amounts use fixed-precision `NUMERIC(14, 2)` and Python `Decimal`.
- [x] Transaction access is scoped to business IDs and authenticated membership.

## Unit 3 — Transactions
- [x] Service-level create, list, read, update, and void operations are implemented for income and expense records.
- [x] Amounts use fixed-precision decimal storage and must be greater than zero.
- [x] Invalid direction, currency codes, blank descriptions, and amounts are rejected by validation/database constraints.
- [x] Business currency is enforced for transaction creation; currency conversion is not yet supported.
- [x] Optional idempotency keys are unique within a business.
- [x] Voiding preserves the entry instead of deleting its history; void entries cannot be edited.
- [x] Authenticated HTTP endpoints enforce business membership for every transaction operation (covered by API tests).
- [ ] Refund policy, audit history, and additional correction rules still need implementation.

## Unit 4 — Authentication and authorization
- [x] Registration creates a user, first business workspace, owner membership, and access session atomically.
- [x] Passwords are Argon2-hashed and never returned in API responses.
- [x] Login rejects invalid credentials without disclosing whether an account exists.
- [x] Unauthenticated requests to business and transaction endpoints are denied.
- [x] A user cannot read or modify another business's records by changing an ID.
- [x] Access tokens expire after 30 minutes; logout revokes the associated database session.
- [x] Authentication, authorization, logout, and transaction lifecycle tests pass in CI (19 backend tests passed in run #97).
- [ ] Login/register rate limiting and security-event auditing are reviewed before production release.

## Unit 5 — Receipts
- [ ] Unsupported file types and oversized files are rejected.
- [ ] File signatures are checked.
- [ ] Receipt files remain private.
- [ ] OCR failure does not crash transaction workflows.
- [ ] Extracted fields are reviewable and editable.
- [ ] No transaction is confirmed without explicit user action.
- [ ] Likely duplicate uploads are flagged.
- [ ] Database failure does not leave unreferenced files indefinitely.

## Unit 6 — Financial overview
- [ ] Totals respect date range, business access, and transaction status.
- [ ] Different currencies are not summed together.
- [ ] Empty periods and zero totals display safely.
- [ ] Cash movement is labelled separately from profit.
- [ ] Comparisons disclose periods and incomplete data.

## Unit 7 — Profitability
- [ ] Gross profit and margin use documented formulas.
- [ ] Zero revenue does not divide by zero.
- [ ] Missing costs are surfaced instead of fabricated.
- [ ] Refunds, discounts, tax treatment, rounding, and historical cost changes have tests.
- [ ] Stock purchases and COGS are not double-counted.
- [ ] Calculations use decimal-safe arithmetic.

## Unit 8 — MarginGuard
- [ ] Every finding explains the measured pattern and period.
- [ ] Supporting records and calculation details can be inspected.
- [ ] Uncertainty and missing inputs are visible.
- [ ] The system does not state correlation as proven causation.
- [ ] A finding can be reproduced from the same records and rule version.

## Unit 9 — Simulator
- [ ] User can change supported assumptions and see recalculated results.
- [ ] Inputs and assumptions are visible.
- [ ] Running a scenario does not modify ledger records.
- [ ] Invalid or missing inputs are handled clearly.

## Unit 10 — Financial brief and AI
- [ ] A brief can be generated with AI disabled.
- [ ] AI receives only the verified facts needed for the explanation.
- [ ] Unsupported numbers and claims are rejected or clearly marked.
- [ ] Provider errors/timeouts do not break core finance workflows.
- [ ] Secrets are never exposed to the browser.

## Unit 11 — UX and security
- [ ] Main workflow works on mobile and desktop sizes.
- [ ] Forms have labels, validation feedback, and accessible focus states.
- [ ] Loading, empty, error, and success states are present.
- [ ] Authorization is enforced server-side.
- [ ] Security-sensitive endpoints have suitable abuse controls.

## Unit 12 — Release
- [ ] Setup is verified from a clean checkout.
- [ ] Tests and build checks pass.
- [ ] Environment variables and migration steps are documented.
- [ ] Demo content is synthetic and contains no personal data.
- [ ] Known limitations and supported financial assumptions are disclosed.


## Workspace collaboration foundation
- [ ] Registration without a business name creates a private Solo workspace.
- [ ] Creating a business creates a separate business workspace without copying Solo records.
- [ ] Workspace identity fields validate correctly; a configured logo URL must use HTTPS.
- [ ] Workspace listing returns only workspaces with active membership.
- [ ] Suspended and revoked memberships cannot access business-scoped transactions.
- [ ] Role/permission enforcement is tested for every protected financial operation.
- [ ] Invitations are recipient-bound, hashed at rest, single-use, revocable, and expire after the agreed 30-minute initial period.
- [ ] An invitation cannot be accepted by an account with a different verified email.
- [ ] Workspace switching never exposes another workspace's transactions, receipts, summaries, or AI retrieval.
- [ ] Membership changes create audit records and appropriate notifications.


## Email verification
- [ ] Verification challenges store only a token digest, never the raw token.
- [ ] Verification links expire and are single-use.
- [ ] A new challenge invalidates earlier unconsumed challenges.
- [ ] Missing SMTP configuration fails clearly without exposing tokens.
- [ ] Invalid, expired, and reused tokens are rejected.
- [ ] Email verification UI, delivery retry behavior, and resend abuse controls are completed before production.
- [ ] Invitation acceptance requires the authenticated account's verified email to match the invite recipient.


## Workspace invitations — remaining acceptance work
- [ ] Invitation and email-verification screens work on mobile and desktop.
- [ ] Invitation creation/revocation and verification requests have abuse controls.
- [ ] Invitation lifecycle actions are written to durable audit history.
- [ ] Expired invitations are safely cleaned up or remain unusable without a scheduled job.
- [ ] Invitation acceptance is covered by PostgreSQL-backed and end-to-end tests.
- [ ] Delivery failures, email-provider outages, and retries produce safe, understandable UI feedback.


## Frontend account and workspace context
- [ ] Authentication state recovers safely after expiry and server errors.
- [ ] Verification and invitation tokens are removed from the visible URL and never logged.
- [ ] Workspace switching cannot display data from another workspace after a denied API response.
- [ ] Sign-out clears the browser-tab bearer token and selected workspace.
- [ ] UI communicates unverified email, delivery failures, expired invitations, and permission errors accessibly.
- [ ] Production session storage/XSS trade-offs are reviewed before release.


## Member administration and audit history
- [ ] Only authorized Owner/Admin users can view member lists and audit history.
- [ ] Admins cannot manage Admin/Owner memberships or grant permissions they do not hold.
- [ ] Owner memberships and self-management cannot be changed through member endpoints.
- [ ] Suspension/revocation immediately blocks protected workspace access.
- [ ] Timed suspension automatically reinstates after expiry and records an audit event.
- [ ] Voluntary leave, if added, requires exact phrase, reason, and password re-authentication.
- [ ] Membership and invitation state changes write audit records atomically.
- [ ] Audit history has no ordinary update/delete API and paginates safely.
- [ ] Notification delivery, retention policy, export controls, and production audit integrity are reviewed before release.
