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

The first target users are Nigerian microbusinesses, small retailers, and side-hustle operators. The product should be useful to a solo owner before team features are introduced.

## Principles

- **Calculations are the source of truth.** AI may explain results but must not invent amounts or perform authoritative financial arithmetic.
- **Evidence before conclusions.** Findings should link to the period, records, assumptions, and calculations behind them.
- **Uncertainty is visible.** Missing costs and estimates must be labelled. Correlation is not proof of cause.
- **Receipts need human review.** OCR output never silently becomes a confirmed financial record.
- **Cash flow is not profit.** The interface must explain which measure is shown and how it is calculated.
- **Privacy by default.** Financial records and receipt files are private and access-controlled.
- **Solo-first.** Team setup must not block an owner from using the core product.

## Planned technology

The implementation plan currently targets React + TypeScript + Vite for the web interface, Python + FastAPI for the API, PostgreSQL for persistence, SQLAlchemy and Alembic for data access and migrations, and open-source OCR where practical. Optional AI should sit behind a provider adapter so the core product remains usable without a model API key.

Technology and versions will be pinned in project configuration as implementation begins.

## Project status

This repository is the new Exprofit project home. Initial work establishes the product specification, architecture, implementation checkpoints, and acceptance criteria before the core application is built. Features are not considered implemented merely because they appear in the plan.

See:
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

GitHub Actions runs the backend lint/tests and frontend type/build checks on pushes and pull requests to `main`. These checks have been configured but have not yet been observed passing in GitHub Actions. The npm lockfile is not yet committed; dependency versions are pinned in `frontend/package.json`, and lockfile-based installs are a follow-up reproducibility task.


## Development status and contributions

The project is under active development. Until a runnable baseline and automated checks are committed, treat this repository as an early project foundation rather than a production-ready finance application.

When reusing or adapting code from earlier experiments, retain appropriate authorship and licensing notices and review the code before importing it. Never commit API keys, passwords, real customer records, or receipt images containing personal information.

## License

MIT. See [LICENSE](LICENSE).
