# Exprofit Architecture

**Status:** Target architecture; components are not all implemented yet.

## 1. Design overview

Exprofit is planned as a web application with a clear boundary between user interface, API, domain logic, and persistence.

```text
Browser (React + TypeScript)
        |
        | HTTPS / JSON
        v
FastAPI routes and request validation
        |
        v
Application services
  | transactions | receipts | summaries |
  | profitability | investigations | briefs |
        |
        +---- deterministic financial engine
        |
        +---- optional AI provider adapter
        |
        v
SQLAlchemy data access -> PostgreSQL
        |
        +---- private receipt storage adapter
```

The diagram describes the intended structure, not a claim that every component currently exists.

## 2. Frontend

React, TypeScript, and Vite provide the browser interface. Screens should support a focused solo-owner workflow: transaction entry, receipt review, financial overview, MarginGuard findings, scenario simulation, and financial brief. Browser configuration may contain public API addresses only; provider keys and database credentials must remain server-side.

## 3. API and application services

FastAPI handles HTTP, validation, authentication, authorization, and response schemas. Business logic belongs in services rather than being duplicated across route handlers. Business-scoped queries must check the current user's access on every request.

Proposed service boundaries:
- Transaction service: validate and persist ledger entries.
- Receipt service: upload, hash, extract, review, confirm, and clean up files.
- Summary service: aggregate posted records by period and currency.
- Profitability engine: calculate revenue, COGS, gross profit, margin, and supported estimates.
- MarginGuard investigator: apply transparent rules to calculated results and return evidence references.
- Scenario service: compute projections without modifying the ledger.
- Brief service: create a factual summary and optionally ask an AI provider to explain only supplied facts.

## 4. Data and financial integrity

PostgreSQL is the planned source of persisted business data. SQLAlchemy provides data access and Alembic manages schema migrations. Monetary values use fixed-precision decimal/numeric types rather than binary floating point.

Every financial record has a defined business scope and currency. Related records must have consistent ownership/business references. The transaction model must distinguish drafts, posted entries, refunds, and void/correction behavior. Historical product costs must be preserved so older profitability calculations are not silently rewritten by a later cost change.

Before implementation, settle the exact policy for discounts, tax-inclusive prices, refunds, rounding, and cost assignment. Document these policies alongside the calculation engine and test them.

## 5. Receipt lifecycle

1. Validate file size and detected file type.
2. Compute a content hash and check for likely duplicates.
3. Store the original in private storage.
4. Run best-effort OCR/extraction.
5. Present extracted candidates with confidence/uncertainty to the user.
6. Let the user edit or reject the candidates.
7. Confirm a transaction only after explicit user action.
8. On failure, roll back database changes and clean up unreferenced stored files.

OCR and AI output are untrusted input. Extraction never automatically becomes a confirmed ledger entry.

## 6. AI boundary

AI is optional and not the source of truth for arithmetic. It receives a bounded set of application-calculated facts, supporting record references, assumptions, and uncertainty labels. The result is validated and displayed as explanatory text, not as a new financial record. If the provider is unavailable, calculations and core workflows continue to work.

## 7. Security and operations

- Use secure password hashing and server-side sessions or a reviewed token strategy.
- Enforce authorization at the API/service boundary, not only in the UI.
- Keep receipt storage private and use short-lived authorized access if download links are introduced.
- Avoid logging credentials, receipt contents, or unnecessary personal data.
- Configure CORS with explicit trusted origins.
- Add rate limits to login, verification, and other abuse-sensitive endpoints.
- Keep secrets in environment variables or a secret manager.
- Provide health checks that distinguish application liveness from database readiness.
- Run tests, lint/type checks, and a production frontend build in CI.

## 8. Testing strategy

Unit tests cover arithmetic, currency grouping, refunds, zero revenue, missing costs, rounding, and historical cost policy. API tests cover authentication, authorization, validation, duplicate handling, receipt review/confirmation, and cross-business isolation. Integration tests use a real test database where practical. Frontend checks cover critical user flows and error states.

## 9. Deployment

The initial local development path should be reproducible from documented prerequisites and example environment files. Production deployment must use TLS, managed/private database access, private durable receipt storage, backups, and secret configuration outside source control. Deployment targets will be selected after a verified local baseline exists.


## Current implemented slice — Build 4

The FastAPI app registers `/auth/register`, `/auth/login`, `/auth/me`, `/auth/logout`, `/businesses`, and `/businesses/{business_id}/transactions` routes. User passwords are hashed with Argon2. Access tokens are signed with `AUTH_SECRET_KEY`, expire after 30 minutes, and identify a persisted `AuthSession` row; logout revokes that row. Every business/transaction route checks the current user’s `BusinessMembership` on the server. Registration creates the first NGN workspace using the `Africa/Lagos` timezone. Transaction listing applies status/date filters and pagination in the database query.

This is implemented code, not yet a verified release: CI and PostgreSQL migration success must be observed before acceptance. Distributed login rate limiting, broader audit-event recording, account recovery, and production deployment controls remain out of scope for this build and must be addressed before a public production launch.
