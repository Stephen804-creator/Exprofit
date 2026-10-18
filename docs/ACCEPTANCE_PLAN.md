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
