# Exprofit — Product Specification

**Status:** Initial specification  
**Product category:** Small-business finance and profitability intelligence  
**Initial audience:** Nigerian microbusinesses, small retailers, and side-hustle operators

## 1. Vision

Exprofit helps a small-business owner keep usable financial records, understand profitability where the data supports it, and investigate changes using traceable evidence. It combines an Expense Tracker with MarginGuard, a structured financial investigation workflow.

## 2. Main user journey

1. Create or enter a business workspace.
2. Record income, expenses, and relevant product sales/cost information.
3. Upload or capture a receipt and review extracted details.
4. View period-based financial summaries.
5. Open a MarginGuard finding and inspect the supporting records and calculations.
6. Test a price or cost scenario in the simulator.
7. Read a concise financial brief that separates verified results from assumptions and unanswered questions.

A solo owner must be able to complete the core journey without inviting staff.

## 3. Functional requirements

### 3.1 Transactions
- Create, view, edit, and delete or void records according to the documented audit policy.
- Store transaction type, amount, currency, date, description, category, and optional notes.
- Validate positive amounts and valid dates; handle refunds and corrections explicitly.
- Search and filter by date range, type, and category.
- Prevent accidental repeated submissions and preserve audit information for sensitive changes.

### 3.2 Receipts
- Accept permitted image and PDF formats with configured size limits.
- Validate file signatures, not just filename extensions.
- Store originals privately; never expose public permanent receipt URLs.
- Extract candidate merchant, date, total, tax, and line-item details when available.
- Show uncertain or missing values clearly and require user review before confirmation.
- Detect likely duplicates using file hashes and additional receipt/transaction signals.
- Clean up uploaded files when the corresponding database operation fails.

### 3.3 Financial overview
- Show recorded income, recorded expenses, and cash movement for a selected period.
- Group totals by currency; never add amounts in unlike currencies without an explicit conversion policy.
- Show category breakdowns and period comparisons where sufficient data exists.
- Label all metrics, periods, and estimates clearly.
- Do not present cash movement as profit.

### 3.4 Deterministic financial engine
All authoritative arithmetic must run in tested application code, not in a language model.

- Revenue: defined from eligible recorded sales after the documented treatment of discounts, returns, and taxes.
- Cost of goods sold (COGS): cost assigned to units sold, using a documented cost-history policy.
- Gross profit = revenue − COGS.
- Gross margin (%) = gross profit ÷ revenue × 100 when revenue is greater than zero.
- Estimated operating profit = gross profit − applicable recorded operating expenses, with assumptions disclosed.
- Cash flow: money received and paid in the period; it is not interchangeable with profit.
- Break-even estimates are available only when required fixed-cost and contribution inputs are known.

The engine must avoid double-counting stock purchases and COGS, handle zero revenue, missing costs, refunds, discounts, rounding, and historical cost changes, and preserve currency boundaries.

### 3.5 MarginGuard investigations
Each finding should include:
- A concise description of the observed pattern.
- Comparison periods and figures.
- Links to supporting records.
- The rule and calculation used.
- Missing information and uncertainty.
- A practical next step to investigate.

A finding may report a pattern or association. It must not claim a factor caused a profit change unless the records actually support that conclusion.

### 3.6 What-if simulator
- Allow the user to adjust supported assumptions such as selling price, unit cost, or delivery cost.
- Recalculate projections through the deterministic engine.
- Show all inputs and assumptions.
- Never mutate actual ledger records.

### 3.7 Financial brief and optional AI
- Summarize verified changes and unresolved questions for a selected period.
- AI may explain application-calculated facts in plain language.
- The brief must work without AI credentials.
- AI output must not introduce unsupported figures, silently change records, or present speculation as fact.

### 3.8 Security and privacy
- Authenticate users and authorize every business-scoped operation.
- Keep receipt files private and validate uploads.
- Store passwords using an appropriate password-hashing algorithm.
- Keep secrets in environment configuration, never in committed source or frontend variables.
- Apply request validation, safe error handling, rate limits for sensitive endpoints, and auditable access to sensitive actions.

## 4. Out of scope for the first usable version

Payroll, tax filing, bank integrations, automatic payment execution, inventory forecasting, multi-country tax rules, and autonomous financial decisions are not required for the first usable version. Team collaboration may be added later but must not block the solo-owner workflow.

## 5. Success criteria

A new user can record a transaction, review a receipt extraction, understand a period summary, inspect a profitability result with traceable evidence, and run a what-if scenario. Tests demonstrate correct arithmetic for key edge cases, and documentation makes setup, limitations, and security assumptions explicit.


## 3.9 Solo Mode and Business Workspaces

Every account starts with a private Solo workspace. A user can record supported financial activity there without creating a company, adding departments, or inviting staff. The Solo workspace remains private when the user creates or joins other workspaces.

A user can create multiple Business Workspaces and join other businesses through recipient-bound invitations. The application provides one account and a workspace switcher; it must never merge records between workspaces. Every financial record and AI retrieval request is scoped to the selected workspace and authorized membership.

Business workspaces have a permanent internal identity and separately configurable display name, organization label (for example Departments, Teams, or Units), optional HTTPS logo URL, currency, and timezone. Defaults are NGN and Africa/Lagos. Financial categories are distinct from departments or teams.

Membership roles are Owner, Admin, and Worker. Role and permission checks are enforced on the backend. Financial permissions are independent of department membership and communication access. Membership lifecycle states are Active, Suspended, and Revoked; suspended or revoked members lose protected access immediately.

Invitations are recipient-bound, single-use, revocable, and expiring. The agreed initial expiry is 30 minutes. Invitees must authenticate and verify the intended email before accepting. Possession of a forwarded link alone never grants access. The full invitation lifecycle is not considered implemented until token hashing, verification, expiry, reuse/revocation checks, membership creation, and tests are complete.

See [Workspace Collaboration Design](WORKSPACE_COLLABORATION_DESIGN.md) for security rules and delivery order.
