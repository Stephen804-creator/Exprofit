# Units 18–23: Financial operations

Status: implementation branch; do not treat as deployed until CI and live verification pass.

## Unit 18 — recurring transactions and expected payments
Recurring income/expense schedules support weekly, monthly, and yearly intervals. Schedules represent expectations only; they never auto-post or mutate actual ledger transactions. Monthly dates clamp to the last valid day (for example, the 31st advances to the last day of shorter months). Schedules are workspace-currency only and may be paused/resumed.

## Unit 19 — cash-flow forecast
The forecast uses posted ledger totals over a configurable 7–180 day history, projects average daily income and expense over 7–90 days, and separately overlays dated recurring expectations. The response lists scheduled items so users can inspect the assumptions. It is an estimate, not a guarantee; unrecorded obligations and irregular events are unknown. Currency buckets are never combined or converted.

## Unit 20 — alerts and notifications
Alerts are generated from current-period budget threshold breaches and recurring payments due within seven days. They are persisted idempotently per workspace/event key and can be marked read or dismissed. Acknowledgement is not proof that a payment was made. Email, SMS, push notifications, and background scheduling are not included in this unit.

## Unit 21 — exports and accountant reporting
A permission-checked CSV export contains at most 5,000 transactions per request. The accountant-report endpoint groups posted records by currency and category over an inclusive date range, with a record cap and truncation flag. It does not convert currencies, calculate tax, or claim to be an audited statement.

## Unit 22 — onboarding and usability
The onboarding checklist reports transaction, receipt, product, budget, and recurring-schedule milestones. It is guidance only and never blocks core workspace use. Counts are workspace-scoped and permission-checked.

## Unit 23 — financial copilot
The copilot starts with a deterministic summary grounded in posted transactions and explicit evidence counts. Hugging Face AI is optional, only used when the user explicitly checks the option and a token is configured. Provider output is not authoritative; a bounded request timeout and deterministic fallback apply. No ledger mutation or financial action is performed.

## Verification gate
- Run Ruff, backend tests, PostgreSQL migrations, frontend typecheck/build.
- Test recurrence date boundaries (month-end, leap day, end date), workspace isolation, currency checks, forecast math, alert idempotency and acknowledgement, CSV escaping/caps, onboarding counts, and AI fallback.
- Verify the migration and Render deployment before calling these units production-ready.
