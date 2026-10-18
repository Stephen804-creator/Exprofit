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
