# Exprofit Acceptance Plan

Use this checklist to decide whether a feature is actually complete. Record test commands and results in the implementation status log.

## Unit 1 — Reproducible baseline
- [ ] A clean checkout can install dependencies using documented commands.
- [ ] Backend starts with example configuration and exposes a health endpoint.
- [ ] Frontend starts and can reach the configured API.
- [ ] Versions are pinned and lockfiles are committed.
- [ ] CI runs backend tests/lint and frontend type/build checks.

## Unit 2 — Database
- [ ] SQLAlchemy engine and request-scoped session dependency use configured database settings.
- [ ] Migrations create the schema from an empty PostgreSQL test database.
- [ ] A second migration run leaves the database at the current revision without errors.
- [ ] The initial Business model persists UUID, name, currency code, timezone, and timestamps.
- [ ] Database credentials are not committed.
- [ ] Monetary and quantity fields use suitable decimal precision when transaction models are added.
- [ ] Business-scoped relationships cannot accidentally reference another business's records when ownership and transaction models are added.

## Unit 3 — Transactions
- [ ] Service-level create, list, read, update, and void operations are implemented for income and expense records.
- [ ] Amounts use fixed-precision decimal storage and must be greater than zero.
- [ ] Invalid direction, currency codes, blank descriptions, and amounts are rejected by validation/database constraints.
- [ ] Business currency is enforced for transaction creation; currency conversion is not yet supported.
- [ ] Optional idempotency keys are unique within a business.
- [ ] Voiding preserves the entry instead of deleting its history; void entries cannot be edited.
- [ ] HTTP endpoints remain unavailable until authentication and authorization are implemented.
- [ ] Refund policy, audit history, and additional correction rules still need implementation.

## Unit 4 — Authentication and authorization
- [ ] Passwords are securely hashed.
- [ ] Unauthenticated requests are denied where required.
- [ ] A user cannot read or modify another business's records by changing an ID.
- [ ] Session expiry and logout behave as documented.
- [ ] Sensitive actions are auditable without logging secrets.

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
