# Exprofit Roadmap

This roadmap preserves deferred ideas and distinguishes plans from implemented, tested features. Items are not considered complete until code and verification support that claim.

## Current release — core priorities

- [x] FastAPI API and React/TypeScript frontend foundation.
- [x] PostgreSQL migrations and isolated backend tests.
- [x] Transaction records with workspace scoping and validation.
- [x] Account registration/login and separate private Solo and business workspaces.
- [x] Workspace roles, server-side permission checks, membership lifecycle controls, and audit events.
- [x] Owner-generated invitation links with owner-selected expiry; no invitation email service or paid provider required.
- [x] Applicants sign in, submit their name/contact details/identifying context, and explicitly consent to a face photo.
- [x] Application remains pending until the workspace owner reviews it; link possession alone never grants membership.
- [x] Owner can view the pending photo and approve or reject; approval creates/activates membership.
- [x] Tokens are random and stored as hashes; expired, revoked, or used invitations cannot be reused.
- [x] Applicant photo is removed after approval, rejection, or revocation of a pending application.
- [x] Verify the newest invitation/consent changes against GitHub Actions CI (Ruff, backend tests, PostgreSQL migrations, frontend typecheck, and production build).
- [x] Implement private receipt capture/review, date-filtered currency-separated summaries, deterministic gross-profit calculations, and evidence-backed MarginGuard comparisons.
- [x] Implement the deterministic what-if simulator and evidence-backed plain-language financial brief; AI is optional and never the source of arithmetic.
- [x] Add database-backed rate limits for authentication, email-verification resend, invitations, receipt uploads, and optional external AI calls.
- [x] Add production secret/database validation, streamed request-size limits, and stronger receipt/invitation-file validation.
- [ ] Complete manual mobile and deployed end-to-end testing for invitations, receipt lifecycle, permission boundaries, and provider failure states.
- [ ] Commit a frontend lockfile and verify clean reproducible installs.
- [ ] Verify durable private receipt storage, backups, retention, and restore behaviour before production.

## Collaboration expansion — later

- [x] Workspace switching, member administration, reasoned suspension/revocation/reinstatement, voluntary leave, and audit history are implemented.
- [ ] Further workspace-switcher and member-administration UX refinements.
- [ ] Customizable departments, teams, or units; department membership stays separate from financial permissions.
- [ ] Department conversations and announcements.
- [ ] Private direct messages visible only to their participants.
- [ ] Work instructions, notification preferences, and durable notification history distinct from audit events.
- [ ] Ownership transfer, searchable/paginated audit history, and retention/export policies.

## Identity and storage expansion — later, only if justified

- [ ] Review owner-assisted verification with real users before adding more steps.
- [ ] Consider stronger optional verification or liveness checks only if the product risk justifies the cost and complexity.
- [ ] Consider private Supabase Storage or Cloudflare R2 for photos and receipts, with access controls, short-lived URLs, retention rules, and deletion tests.
- [ ] Do not require paid facial-recognition APIs or external identity services for the basic invitation workflow.

## AI and product expansion — later

- [x] Optional Gemma-based explanations grounded in server-calculated facts and protected by explicit per-request opt-in.
- [x] Evidence-linked investigations and deterministic what-if calculations.
- [ ] Expand inventory, purchases, team reporting, and advanced financial workflows after the core data model stabilizes.

## Invitation flow in this release

1. The owner generates a link and selects its expiry.
2. The owner copies and shares the link privately through any channel. Exprofit does not send invitation emails.
3. The invited person signs in or creates an account, opens the link, supplies identity details, and gives explicit consent before submitting a photo.
4. The application remains pending. Only the workspace owner can review the details/photo and decide.
5. Approval grants workspace membership. Rejection or revocation blocks the invitation. The photo is deleted when the application is decided or revoked.
6. The photo and self-reported details support manual owner review only. This is not biometric matching, liveness detection, government-ID verification, or a guarantee against impersonation.

Photos are currently held temporarily in the application database, not a dedicated object-storage service. This workflow is a lightweight owner review, not a formal identity-proofing service.


## Builds 9–14 implementation status

The branch `feat/intelligence-simulator-builds-9-14` and PR #3 add a deterministic brief, opt-in Hugging Face Gemma explanations, a non-persistent what-if simulator, and focused tests. Do not mark this release-ready until PR checks pass and manual authorization, provider-failure, mobile, and deployed end-to-end tests are complete. See `docs/BUILDS_9_14_IMPLEMENTATION.md`.



## Production-hardening follow-up

The current hardening branch adds production startup checks, request-size limits, rate limits for sensitive workflows, invitation JPEG validation, receipt permission boundaries, AI data-sharing disclosures, and audit protection for shared alert status. See [PR #21](https://github.com/Stephen804-creator/Exprofit/pull/21) and [Implementation Status](IMPLEMENTATION_STATUS.md). Automated CI does not replace manual mobile testing, hosted-provider checks, or durable receipt-storage verification.
