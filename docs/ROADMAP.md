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
- [ ] Manually test the complete invitation flow on mobile before calling this slice release-ready.
- [ ] Add focused security tests for invalid/replayed links, expiry, duplicate applications, owner-only review, and privilege escalation.
- [ ] Add auth/sensitive-route rate limits, production security checks, and a frontend lockfile.
- [ ] Verify on branch `feat/core-financial-workflow-builds-1-8`: private receipt capture and review, date-filtered currency-separated summaries, deterministic gross-profit calculations, and evidence-backed MarginGuard comparisons. Do not mark complete until CI, PostgreSQL migrations, access-control tests, and manual end-to-end checks pass.
- [ ] Add the what-if simulator and evidence-backed plain-language financial brief. AI is optional and never the source of arithmetic.

## Collaboration expansion — later

- [ ] Workspace-switcher and member-administration UX refinements.
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

- [ ] Optional Gemma-based explanations grounded only in records the current user is authorized to access.
- [ ] Evidence-linked investigations and evaluation tests for unsupported claims.
- [ ] Inventory, purchases, team reporting, and advanced financial workflows after the core data model stabilizes.

## Invitation flow in this release

1. The owner generates a link and selects its expiry.
2. The owner copies and shares the link privately through any channel. Exprofit does not send invitation emails.
3. The invited person signs in or creates an account, opens the link, supplies identity details, and gives explicit consent before submitting a photo.
4. The application remains pending. Only the workspace owner can review the details/photo and decide.
5. Approval grants workspace membership. Rejection or revocation blocks the invitation. The photo is deleted when the application is decided or revoked.
6. The photo and self-reported details support manual owner review only. This is not biometric matching, liveness detection, government-ID verification, or a guarantee against impersonation.

Photos are currently held temporarily in the application database, not a dedicated object-storage service. This workflow is a lightweight owner review, not a formal identity-proofing service.
