# Exprofit

**Exprofit** is an open-source finance and profitability assistant for small businesses and side hustles. It combines expense tracking with MarginGuard: a workflow that helps owners investigate profitability changes using evidence from their own records.

> Record your money. Understand your margins. Investigate what affects your profit.

## The problem

Small-business owners often record sales and expenses in notebooks, spreadsheets, transaction alerts, and paper receipts. It can be difficult to keep those records consistent, capture receipt details, distinguish cash flow from profit, or understand why a product's margin changed.

Exprofit aims to make those tasks easier without hiding the calculations behind AI-generated answers.

## Core scope

1. **Expense Tracker** — record and review income, expenses, categories, and transactions.
2. **Receipt scanning** — extract candidate details from receipt images or PDFs, then let the user review and correct them before saving.
3. **Financial overview** — summarize recorded income, spending, and cash movement by date range and currency.
4. **Profit and margin engine** — calculate supported financial measures with deterministic, tested application code.
5. **MarginGuard investigations** — highlight changes and show the records, calculations, uncertainties, and next steps behind each finding.
6. **What-if simulator** — test price and cost assumptions without changing real financial records.
7. **Financial brief** — explain verified changes in plain language. AI is optional and must be grounded in application-calculated results.

The first target users are Nigerian microbusinesses, small retailers, and side-hustle operators. Every account starts in private Solo Mode and can later create or join separate Business Workspaces under the same login. Joining a business must never expose the user's Solo Mode records.

## Principles

- **Calculations are the source of truth.** AI may explain results but must not invent amounts or perform authoritative financial arithmetic.
- **Evidence before conclusions.** Findings should link to the period, records, assumptions, and calculations behind them.
- **Uncertainty is visible.** Missing costs and estimates must be labelled. Correlation is not proof of cause.
- **Receipts need human review.** OCR output never silently becomes a confirmed financial record.
- **Cash flow is not profit.** The interface must explain which measure is shown and how it is calculated.
- **Privacy by default.** Financial records and receipt files are private and access-controlled.
- **Solo-first.** Team setup must not block an owner from using the core product.

## Planned technology

The current baseline uses React + TypeScript + Vite, Python + FastAPI, and a PostgreSQL data layer built with SQLAlchemy and Alembic. Optional AI and OCR are not implemented yet and will sit behind explicit boundaries.

## Project status

This repository is the new Exprofit project home. The application shell, database foundation, transaction service, and authentication/API slice are committed. Receipt scanning, financial summaries, the profitability engine, MarginGuard, and what-if simulation remain unimplemented. The latest GitHub Actions run passed the configured checks, including PostgreSQL migrations and backend tests; production hardening remains outstanding.

See:
- [Workspace collaboration design](docs/WORKSPACE_COLLABORATION_DESIGN.md)
- [Product specification](docs/PRODUCT_SPECIFICATION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Acceptance plan](docs/ACCEPTANCE_PLAN.md)


## Build 1 — application foundation

The initial application shell and verification workflow are now committed. This is a starting point, not a production-ready financial application.

### Requirements

- Python 3.11+
- Node.js 20+
- npm

### Start the API

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
# Copy the root .env.example to backend/.env and replace AUTH_SECRET_KEY.
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; check `/health` and open `/docs` for the API schema. The health endpoint is a liveness check and does not require a database.

### Start the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal. The frontend checks the API at `http://127.0.0.1:8000` by default. To change it, copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE_URL`. Only public browser configuration belongs in variables prefixed with `VITE_`; never put credentials there.

### Checks

```bash
cd backend
python -m ruff check .
python -m pytest
```

In another terminal:

```bash
cd frontend
npm run typecheck
npm run build
```

GitHub Actions runs backend lint/tests and frontend type/build checks on pushes and pull requests to `main`. Run [#97](https://github.com/Stephen804-creator/Exprofit/actions/runs/39121683770) passed: Ruff, PostgreSQL migrations, 19 backend tests, frontend typecheck, and production build. The run included one third-party Starlette/AnyIO deprecation warning. The npm lockfile is not yet committed; CI currently uses `npm install`, so lockfile-based installs remain a reproducibility follow-up.


## Development status and contributions

The project is under active development. Until a runnable baseline and automated checks are committed, treat this repository as an early project foundation rather than a production-ready finance application.

When reusing or adapting code from earlier experiments, retain appropriate authorship and licensing notices and review the code before importing it. Never commit API keys, passwords, real customer records, or receipt images containing personal information.

## License

MIT. See [LICENSE](LICENSE).


## Build 2 — database foundation

The database layer includes SQLAlchemy engine/session plumbing, a shared ORM base, a Business model, and Alembic migrations. The default currency is NGN and timezone is Africa/Lagos. Configure PostgreSQL using `DATABASE_URL`, then from the backend directory run `alembic upgrade head`. The complete migration chain was subsequently verified against PostgreSQL 16 in CI run #97.


## Build 3 — transaction integrity

The first transaction layer is committed: SQLAlchemy model and migration, validated Pydantic schemas, and service operations for creating, listing, retrieving, updating, and voiding income/expense entries. Amounts use `NUMERIC(14, 2)`/Python `Decimal`, must be positive, and have a separate income/expense direction. Each entry is tied to a business and must use that business's currency; currency conversion is not implemented. Optional idempotency keys are unique per business. Voiding preserves the record rather than deleting it.

Authenticated transaction HTTP routes are now registered. Every route requires a valid bearer session and checks membership in the requested business before reading or changing its records. Tests and PostgreSQL migrations are configured but have not yet been confirmed passing.


## Build 4 — authentication and access control (implemented; verification pending)

The API now includes registration, login, current-user, logout, business-workspace, and business-scoped transaction routes. Passwords are Argon2-hashed; signed access tokens expire after 30 minutes and are linked to database sessions that can be revoked on logout. Registration creates an NGN/Africa-Lagos workspace and owner membership. Business and transaction routes check membership server-side. A test suite covers registration, login failures, logout revocation, duplicate email, cross-business isolation, and a transaction lifecycle. CI run #97 passed the PostgreSQL migrations, Ruff, all 19 backend tests, frontend typecheck, and production build. Rate limiting and broader production security hardening remain follow-up work. Set `AUTH_SECRET_KEY` to a unique random value of at least 32 bytes; do not reuse the example placeholder or commit a real secret.
