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

The current invitation slice is a simple, owner-controlled application flow with no required email delivery or paid identity service.

1. The workspace Owner creates a unique shareable link, chooses the role and permissions, and selects an expiry from 1 to 720 hours.
2. The owner copies and sends the link through any channel. Exprofit does not send email for this workflow.
3. The recipient signs in or creates an account, submits their name, optional phone, identifying details, and a JPEG face photo.
4. The application remains pending. Link possession and application submission do not grant workspace access.
5. Only the workspace Owner reviews the submitted details and photo, then approves or rejects. Approval creates membership with only the role and permissions attached to the invitation.
6. Links are hashed at rest, single-use after approval, expiring, and revocable. Rejection/revocation disables the link and deletes the pending photo.

The photo is stored as a private binary value in the application database for this first version; only the workspace Owner can retrieve a pending photo. The photo is deleted after a decision. This is owner-assisted visual review, not biometric authentication or proof of liveness. No email verification is required to apply or be approved.

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


## Account email verification

Legacy account email-verification endpoints remain separate from workspace invitations. They are not required to create, apply for, or approve a workspace invitation. The invitation workflow does not depend on SMTP, email verification, or a paid external service.



## Invitation API implementation slice

The invitation endpoints now generate shareable links, accept applications, expose private pending photos to authorized reviewers, and support approval/rejection/revocation:
- `POST /businesses/{business_id}/invitations` — create a link and choose expiry.
- `POST /invitations/apply` — authenticated applicant submits details and a JPEG photo.
- `GET /businesses/{business_id}/invitation-applications` — authorized administrators list pending applications.
- `GET /businesses/{business_id}/invitation-applications/{application_id}/photo` — authorized administrators view a pending photo.
- `POST /businesses/{business_id}/invitation-applications/{application_id}/approve` — approve and create membership.
- `POST /businesses/{business_id}/invitation-applications/{application_id}/reject` — reject and revoke the invitation.
- `POST /businesses/{business_id}/invitations/{invitation_id}/revoke` — revoke a pending link.

The raw invitation token is returned only with the creation response; only its SHA-256 digest is stored. The owner chooses an expiry between 1 and 720 hours. The database stores a pending JPEG up to 2 MB; the photo endpoint is private and sends no-store headers. The photo is deleted after approval, rejection, or revocation. Application submission does not grant access, and the link becomes used only when approved. Automated CI and manual browser checks still need confirmation on the latest branch head.



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

The React interface now provides a business-workspace collaboration panel for authorized administrators: member list, role/permission editing, suspension, revocation, reinstatement, and recent audit events. Invitation creation and applicant review controls are reserved for the workspace Owner. A signed-in member can view their own membership without gaining access to the full directory and can request voluntary departure with exact-phrase confirmation, password re-authentication, reason, and optional notice period. Owners see the ownership-transfer restriction.

The UI hides management controls unless the current membership grants both Staff Administration read and write (Owners are authorized by role). API permissions remain authoritative. These screens have typecheck/build coverage but still require manual browser/end-to-end verification and accessibility review.


See [the roadmap](ROADMAP.md) for departments, messaging, notifications, advanced identity checks, private object-storage migration, receipt scanning, financial summaries, MarginGuard, and other deferred work.
