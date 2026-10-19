# Builds 1–8: baseline audit and implementation record

## Baseline inspected

The feature work started from commit `4de7ba59ee90db1992b128cfac01dd739cc67c5a` on `main`. The existing stack is React 18 + TypeScript + Vite, FastAPI, SQLAlchemy, Alembic and PostgreSQL. Existing authenticated transaction endpoints already support workspace-scoped create/list/read/update/void operations, decimal amounts, currency matching and permission checks. The Solo/business workspace and membership foundation is retained; this work does not replace authentication or rewrite the data layer.

## Builds included in this branch

- **Build 1 — baseline:** documented the inspected architecture and retained the existing stack and API boundary.
- **Build 2 — expense UI:** added a workspace financial panel for creating, filtering, viewing, editing and voiding income/expense entries.
- **Build 3 — integrity:** uses existing workspace-scoped APIs, decimal transaction amounts and server-side permissions. Voided entries remain visible but are excluded from totals. The UI gates create/edit/void actions, receipt review and combined summaries by the current workspace membership permissions. The UI does not convert currencies.
- **Build 4 — receipt capture:** added private receipt storage in PostgreSQL, a 5 MiB limit, allowed-type checks plus file-signature validation, authenticated workspace-scoped retrieval, and a per-workspace duplicate-file guard enforced by a partial unique index (rejected receipts may be uploaded again). PDF text extraction is capped at 50 pages and image OCR skips images above 20 million pixels.
- **Build 5 — extraction and review:** PDF text extraction and optional local image OCR are best-effort. Candidate merchant/date/amount/currency values are untrusted suggestions. A human must edit/review and explicitly confirm before a posted transaction is created; rejecting a receipt clears its stored bytes and extracted text. Receipt confirmation checks the direction-specific permission and commits the transaction plus receipt link atomically.
- **Build 6 — summaries:** added date filters, currency-separated income/expense/net-cash-movement totals and category totals. Draft and void entries are excluded.
- **Build 7 — calculations:** added deterministic revenue/direct-cost/gross-profit/gross-margin calculations. Only explicitly recognised direct-cost categories count as direct costs; operating expenses are not silently treated as cost of goods sold. Gross profit and margin remain unavailable when direct-cost data is absent.
- **Build 8 — MarginGuard:** compares the latest 7–180-day period with the preceding equal-length period; the UI uses 30 days. Findings include current-period record evidence and uncertainty statements. A change is not presented as proof of its cause.

## Important limits and verification gates

1. OCR depends on the local Tesseract executable for images; if unavailable, the receipt remains usable for manual entry. PDF extraction works only where the PDF contains extractable text; image-only PDFs may produce no text.
2. Receipts are stored as database binary data. Production deployments still need retention policy, storage-capacity controls, backup/deletion policy and operational monitoring.
3. Summary and MarginGuard routes require read access to both sales and expenses. Receipt confirmation separately checks permission for the selected transaction direction.
4. MarginGuard compares recorded transactions, not inventory or individual product unit economics. Gross margin is only shown when direct-cost records are explicitly categorised.
5. This branch has not been declared production-ready. Required gates: CI (Ruff, tests, PostgreSQL migrations, frontend typecheck/build), PostgreSQL migration verification, cross-workspace and permission tests, upload abuse tests, mobile usability, and a manual full workflow.
6. Builds 9–14 (evidence-backed explanations, open-weight Gemma integration, and security/QA hardening) remain separate work. No AI provider or AI-generated arithmetic was added in Builds 1–8.

## Acceptance checklist

- [ ] CI passes on this branch.
- [ ] PostgreSQL migration chain upgrades cleanly from the current head.
- [ ] Owner can create/edit/void transactions; voids never contribute to totals.
- [ ] Non-member cannot read transactions, receipts, summaries or MarginGuard data.
- [ ] A user without the required financial permission cannot read or write that domain.
- [ ] Upload rejects mismatched MIME/signature, unsupported types and files above 5 MiB.
- [ ] Receipt candidate values are not saved as a transaction without explicit confirmation.
- [ ] Currency totals remain separate and cash movement is not labelled profit.
- [ ] Missing direct-cost data produces an unavailable gross-profit result rather than a misleading number.
- [ ] MarginGuard shows evidence and uncertainty for detected changes.
- [ ] Duplicate receipt upload is rejected within the same workspace, while a previously rejected receipt can be uploaded again.
- [ ] Restricted business members see only permitted transaction domains; combined summaries are hidden without both sales and expense read permissions.
