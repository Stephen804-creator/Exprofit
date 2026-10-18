# Exprofit Roadmap

This roadmap records deferred ideas so they are not lost. It is a plan, not a claim that these features already exist. Work is ordered by the needs of the first usable release and may be adjusted after challenge submission.

## Current priority — finish the core product

- [ ] Complete and verify the shareable invitation workflow: owner chooses expiry, applicant signs in, submits details and a face photo, and the owner approves or rejects before access is granted.
- [ ] Run backend lint/tests, PostgreSQL migrations, frontend typecheck/build, and manually exercise the complete invitation flow.
- [ ] Add rate limits and production security checks to authentication and sensitive endpoints.
- [ ] Commit a frontend lockfile and verify setup from a clean checkout.
- [ ] Build receipt capture and review, with private file access and explicit user confirmation before creating a transaction.
- [ ] Build date-filtered financial summaries that keep currencies separate and distinguish cash movement from profit.
- [ ] Implement the deterministic profitability engine and MarginGuard investigations with evidence, missing-cost warnings, and reproducible calculations.
- [ ] Add what-if scenarios and a plain-language financial brief. AI remains optional and cannot be the source of financial arithmetic.

## Collaboration expansion — after the core release

- [ ] Workspace switcher and member administration UX refinements.
- [ ] Customizable departments, teams, or units, with membership kept separate from financial permissions.
- [ ] Department conversations and announcements.
- [ ] Private direct messages visible only to their participants.
- [ ] Work instructions and notification preferences.
- [ ] Notification delivery and durable notification history, distinct from audit events.
- [ ] Ownership transfer and additional membership lifecycle controls.
- [ ] Searchable, paginated audit history plus retention and export policy.

## Identity and file-storage expansion — only when justified

- [ ] Review the current owner-assisted verification process and gather feedback before adding more steps.
- [ ] Consider optional liveness checks or stronger identity verification only if the product risk warrants the cost and complexity.
- [ ] Consider moving private application photos and receipts from PostgreSQL binary storage to a private Supabase Storage or Cloudflare R2 bucket, with authorization, short-lived access URLs, retention rules, and deletion tests.
- [ ] Do not introduce paid facial-recognition APIs or require external identity services for the basic invitation workflow.

## AI and product expansion — later

- [ ] Add an optional Gemma-based assistant grounded only in records the current user is authorized to access.
- [ ] Add evidence-linked investigations, user feedback, and evaluation tests for unsupported claims.
- [ ] Consider inventory, purchases, team-level reporting, and advanced financial workflows after the core data model is stable.
- [ ] Revisit advanced identity, workflow automation, and larger-team features after the first release and challenge submission.

## Explicit non-goals for the current invitation slice

The current slice does not implement departments, messaging, announcements, advanced biometric verification, facial matching, liveness detection, email delivery, or a paid verification API. The applicant's photo is for the owner to inspect manually; it is not biometric authentication. A pending application grants no workspace access. Photos are private and are deleted from application storage when the owner approves, rejects, or revokes the pending application.
