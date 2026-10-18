# Workspace Collaboration Design

**Status:** Agreed product direction; implementation is being delivered in small, testable slices.

## Core model

Exprofit uses one account per person and multiple isolated workspaces. A user can keep private Solo Mode records, own one or more Business Workspaces, and join other businesses with explicit permission. Switching workspaces changes the active data scope; it does not merge or copy records.

### Solo Mode
- Created by default at registration.
- Fully usable without staff, departments, invitations, or a registered company.
- Private to its owner.
- Uses the same financial workflows as business workspaces as those workflows are implemented.
- Joining a business never grants that business access to the user's Solo Mode.

### Business Workspace
- Created separately from Solo Mode.
- Has a permanent internal ID and a customizable display identity.
- Defaults to NGN and Africa/Lagos, while keeping currency and timezone configurable.
- Supports Owner, Admin, and Worker membership roles.
- Financial permissions are independent from department/team assignment.
- Every API request must check active membership and the required permission on the server.

## Invitations

Invitations are restricted, recipient-bound invitations to one business—not public join links. The initial policy is a 30-minute expiry. Each invitation must:
- identify one business and one intended email address;
- carry a role and an explicit permission set;
- store only a hash of its high-entropy token;
- be single-use, expiring, and revocable;
- require the invitee to authenticate and verify the invited email before acceptance;
- avoid revealing private business data before membership is created;
- record creation, acceptance, expiry/revocation, and membership changes for accountability.

Possession of a forwarded link alone must never grant access. Verification questions are not a substitute for email/account verification.

## Membership lifecycle

Membership states are Active, Suspended, and Revoked. Authorization checks must deny suspended/revoked memberships immediately. The owner cannot be removed through ordinary worker-management actions. Important membership changes require a reason and audit history. Voluntary leave can require the exact confirmation phrase “I want to leave”, a written reason, and password re-authentication; notice periods and timed suspension are later workflow enhancements.

## Roles and permissions

Roles describe a member's broad administrative position:
- Owner: full workspace control; ownership cannot be silently transferred or removed.
- Admin: only explicitly granted management capabilities.
- Worker: only explicitly granted operational capabilities.

Financial permission domains include Sales, Purchases, Expenses, Inventory, and Staff Administration. For API grants, use explicit boolean keys in the form `domain:action`, for example `sales:read` or `expenses:write`; absent or false keys deny access. Owners receive financial access by role, while Admins and Workers require explicit grants. The current transaction API maps income records to Sales and expense records to Expenses; Purchases and Inventory need dedicated workflows before they can be granted through those routes. Staff administration is restricted to the owner or explicitly authorized administrators. Department membership and communication access never imply financial access.

## Workspace identity and organization

Keep a permanent workspace ID and original name separate from its display name. Optional logo configuration uses an HTTPS URL initially. An organization label may be “Departments”, “Teams”, or “Units”. Business currency and timezone are workspace-specific. Financial categories remain separate from departments/teams.

## Privacy and communication

Business records, receipts, summaries, AI retrieval, and messages are scoped to the active authorized workspace. Solo Mode is never exposed to business owners. Direct messages are visible to their participants; managers do not automatically gain access. Notifications inform users; audit events provide accountability. Neither bypasses authorization.

## Delivery sequence

1. Workspace type and membership lifecycle foundation; keep Solo Mode private by default.
2. Explicit permission checks and workspace switching API.
3. Recipient-bound invitation creation, verification, acceptance, expiry, and revocation.
4. Member administration and audit history.
5. Frontend workspace switcher and invitation UX.
6. Departments, communication, notifications, and advanced workflows after the core boundary is verified.

## Security and verification gates

- Test cross-workspace isolation for transactions and every future data type.
- Test suspended/revoked membership denial at the API boundary.
- Test expired, reused, revoked, and wrong-recipient invitations.
- Do not log raw invitation tokens or expose them after creation.
- Do not claim invitation or collaboration features are complete until automated tests and CI verify them.


## Verified email foundation

The current feature branch adds an email-verification state to accounts and a persisted challenge table. Challenges use a cryptographically random token, store only its SHA-256 digest, expire according to `EMAIL_VERIFICATION_TTL_MINUTES` (30 minutes by default), and are consumed once. Requesting a new challenge invalidates older unconsumed challenges for that account. SMTP delivery is configured through environment variables; the raw token is sent only in the verification email and is not returned by the API.

API endpoints:
- `POST /auth/request-email-verification` — authenticated; sends a verification email when SMTP is configured.
- `POST /auth/verify-email` — consumes a supplied token and marks the account email as verified.
- `GET /auth/me` — includes the `email_verified` state.

This does not yet add email verification UI, resend throttling, account recovery, or invitation acceptance. Collaboration invitations must remain disabled until verified-email identity is enforced in the invitation acceptance path and delivery is configured in the deployment.


## Invitation API implementation slice

The feature branch now includes:
- `POST /businesses/{business_id}/invitations` to create and email a recipient-bound invite.
- `POST /invitations/accept` to accept it while authenticated.
- `POST /businesses/{business_id}/invitations/{invitation_id}/revoke` to revoke a pending invite.

Only Owner/Admin actors with `staff_administration:write` may create or revoke invitations. Only the Owner may invite an Admin. Admins can invite Workers only with permissions they themselves hold, and cannot delegate Staff Administration. Workers cannot hold Staff Administration access. The request schema rejects unknown permission keys.

Invitations store only a SHA-256 token digest, expire after 30 minutes by default, invalidate earlier pending invitations for the same workspace/email, and are single-use and revocable. Acceptance requires an active authenticated account, verified email, an exact normalized email match, a valid unexpired non-revoked invitation, and a business workspace. Acceptance creates or reactivates the recipient's membership without moving Solo records. The raw token is sent by email and is not included in the API response.

Still outstanding: invitation and verification frontend screens, abuse/rate limiting, durable audit events, notification UX, and broader end-to-end tests. SMTP must be configured. Do not expose these endpoints as production-ready until those remaining security and UX controls are reviewed.


## Member administration and audit implementation slice

The API now supports:
- `GET /businesses/{business_id}/members` for authorized administrators.
- `PATCH /businesses/{business_id}/members/{membership_id}` for reasoned role/permission updates.
- `POST /businesses/{business_id}/members/{membership_id}/suspend` for immediate or timed suspension (1–720 hours when timed).
- `POST /businesses/{business_id}/members/{membership_id}/revoke` for immediate access revocation.
- `POST /businesses/{business_id}/members/{membership_id}/reinstate` for suspended members.
- `GET /businesses/{business_id}/audit-events` for read-only, paginated audit history.

Only Owner/Admin actors with explicit Staff Administration permissions may use these endpoints. Admins may manage Worker memberships only; Owner memberships cannot be changed through these routes, and an actor cannot change their own membership. Revoked members must accept a new invitation rather than use the suspension-reinstatement endpoint. Timed suspensions are checked at the API boundary and automatically reinstate when their deadline passes.

The new append-only audit table records workspace creation, invitation lifecycle actions, membership updates, suspension, revocation, manual reinstatement, and timed reinstatement. Audit records are committed with the corresponding state change. Notifications, audit retention/exports, and broader tamper-resistance controls are still future work.


## Voluntary leave implementation slice

`POST /businesses/{business_id}/leave` now requires the exact phrase `I want to leave`, password re-authentication, and a written reason. The user may leave immediately or set a notice period of 1–720 hours. Immediate departure revokes membership access immediately; scheduled departure remains recorded and is finalized at the deadline when a protected request or authorized member-list read reaches the API. Finalization is audited. Workspace Owners cannot leave through this route until ownership transfer is supported, preventing an accidental orphaned workspace. A new valid invitation can re-establish a previously revoked membership and clears any old leave schedule.

Password re-authentication is implemented, but abuse throttling and a frontend leave screen remain outstanding.


## Collaboration UI implementation slice

The React interface now provides a business-workspace collaboration panel for authorized administrators: member list, invitation creation, role/permission editing, suspension, revocation, reinstatement, and recent audit events. A signed-in member can view their own membership without gaining access to the full directory and can request voluntary departure with exact-phrase confirmation, password re-authentication, reason, and optional notice period. Owners see the ownership-transfer restriction.

The UI hides management controls unless the current membership grants both Staff Administration read and write (Owners are authorized by role). API permissions remain authoritative. These screens have typecheck/build coverage but still require manual browser/end-to-end verification and accessibility review.
