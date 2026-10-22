# Units 14–17 implementation and verification

Status date: 2026-10-22. Changes are on branch `feat/units-14-17-face-capture-budget-profitability`. Do not describe this work as production-verified until CI, deployment, and manual browser checks pass.

## Unit 14 — security and release readiness

Implemented in this branch:
- Face capture now maps common camera failures to actionable messages, distinguishes browser permission denial from missing hardware/network loading errors, and offers a retry control.
- The camera flow explicitly requests the front-facing camera, uses a secure-context check, and retains the face-presence positioning gate.
- API responses receive baseline `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `X-Frame-Options`, and HTTPS HSTS headers.
- Login and registration use hashed, database-backed fixed-window counters so limits are shared across instances using the same PostgreSQL database. Limits are 30 login attempts per IP per 15 minutes, 10 login attempts per normalized email per 15 minutes, 5 registrations per IP per hour, and 3 registrations per email per hour.
- Automated coverage checks the security headers.

Still required:
- Run CI, migration checks, and auth tests on this branch.
- Verify camera access on a real Android browser. The website cannot override a browser/device permission that the user has denied. Open the HTTPS site directly in Chrome, set Site settings → Camera → Allow for `exprofit.onrender.com`, then return/reload and retry.
- Test the invitation flow and actual Brevo delivery on the deployed Render service.
- Review production proxy/IP handling, add end-to-end browser tests, verify dependency lockfiles, and perform a clean-clone setup.
- Confirm HTTPS HSTS behaviour behind Render's reverse proxy. Do not add a restrictive Content Security Policy without allowing the MediaPipe module, WASM, and model origins.

## Unit 15 — product/customer data foundation

Implemented in this branch:
- Added workspace-scoped `products`, `customers`, and `budgets` tables and migration `20261022_0012`.
- Transactions can optionally reference a product and customer.
- Service validation rejects product/customer references that are inactive or belong to another workspace.
- Added permission-checked product/customer create/list endpoints.
- Added catalog input/output schemas and a UI to create and review products and customers.
- Transaction entry now offers optional product and customer attribution fields.

Data rules:
- Product unit price and unit cost are reference metadata; the profitability report does not invent revenue or cost from these fields.
- Transactions remain the source of actual recorded amounts.
- Product/customer attribution is optional, so historical transactions are not automatically assigned.

## Unit 16 — profitability by product/customer

Implemented in this branch:
- Added `GET /businesses/{business_id}/product-profitability`.
- Added `GET /businesses/{business_id}/customer-profitability`.
- Both endpoints are workspace-scoped, permission checked, date-filterable, and use posted transactions only.
- Revenue comes from income transactions explicitly attributed to the product/customer.
- Direct costs include only expenses whose category matches the configured direct-cost categories. Gross profit remains unavailable if no qualifying direct-cost record exists.
- Added product/customer profitability UI and tests for a recorded sale and direct cost.

Limitations:
- There is no quantity, returns, shared-cost allocation, or cost-of-goods-sold inventory engine yet.
- This is gross profitability from explicitly attributed ledger entries, not final net profit.
- Direct costs must be assigned to the same product/customer to appear in the report.

## Unit 17 — budget versus actual

Implemented in this branch:
- Added a budget model with category, currency, inclusive date period, amount, and configurable warning threshold.
- Added migration `20261022_0012` for budget and catalog tables, and `20261022_0013` for shared rate-limit buckets.
- Added create/list budget endpoints and a budget-versus-actual endpoint.
- Actual spending sums all posted expense records matching the budget category, currency, and inclusive period.
- The UI displays budget, actual spend, remaining amount, percent used, warning status, and over-budget status.
- Added a regression test with multiple expenses to ensure actuals are summed rather than using a single transaction.

Limitations:
- Category matching is exact after the user's category input is stored; inconsistent category spelling can undercount spending.
- Current release does not include recurring budget schedules, forecasts to period end, push/email alerts, budget editing, or deletion.
- No currencies are converted; all budgets use the workspace currency.

## Verification gate

1. GitHub Actions must pass backend lint/tests, PostgreSQL migrations, frontend typecheck, and production build.
2. Inspect failing job logs and fix failures before merge.
3. After merge, verify Render deployed the intended commit and that the migration ran successfully.
4. On mobile, test invitation URL, camera permission grant, permission denial/recovery, face positioning, capture, retake, application submission, owner review, and actual invitation email delivery.
5. Test product/customer attribution, cross-workspace reference rejection, profitability calculations, duplicate budget handling, threshold boundaries, and budget totals against real API responses.
6. Only then mark the units production-verified.
