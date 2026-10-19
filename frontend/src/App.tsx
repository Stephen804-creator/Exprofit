import { useEffect, useState, type FormEvent } from "react";
import FinancialWorkspace from "./FinancialWorkspace";

type ApiStatus = "checking" | "online" | "offline";
type RouteMode = "app" | "accept-invitation";
type AuthMode = "login" | "register";

type User = {
  id: string;
  email: string;
  is_active: boolean;
};

type Member = {
  membership_id: string;
  user_id: string;
  email: string;
  role: "owner" | "admin" | "worker";
  status: "active" | "suspended" | "revoked";
  permissions: Record<string, boolean>;
  suspended_until: string | null;
  revoked_at: string | null;
  leave_effective_at: string | null;
};

type AuditEvent = {
  id: string;
  event_type: string;
  target_type: string;
  target_id: string;
  reason: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

type Workspace = {
  id: string;
  name: string;
  display_name: string | null;
  workspace_type: "solo" | "business";
  organization_label: string;
  currency_code: string;
  timezone: string;
};

type InvitationApplication = {
  id: string;
  invitation_id: string;
  full_name: string;
  email: string;
  phone: string | null;
  identifying_details: string;
  role: "admin" | "worker";
  status: string;
  created_at: string;
};

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

function routeFromPath(): RouteMode {
  if (window.location.pathname === "/accept-invitation") return "accept-invitation";
  return "app";
}

function messageFromError(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  accessToken?: string | null,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const response = await fetch(`${apiBase}${path}`, { ...options, headers });
  if (response.status === 204) return undefined as T;

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : "Request failed.";
    throw new Error(detail);
  }
  return payload as T;
}

export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [routeMode, setRouteMode] = useState<RouteMode>(routeFromPath);
  const [pendingToken, setPendingToken] = useState(
    () => new URLSearchParams(window.location.search).get("token") ?? "",
  );
  // The API currently uses bearer sessions; sessionStorage limits persistence to this browser tab.
  const [accessToken, setAccessToken] = useState<string | null>(
    () => sessionStorage.getItem("exprofit_access_token"),
  );
  const [user, setUser] = useState<User | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState(
    () => sessionStorage.getItem("exprofit_workspace_id") ?? "",
  );
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authError, setAuthError] = useState("");
  const [busy, setBusy] = useState(false);
  const [activePage, setActivePage] = useState<"finance" | "workspaces" | "team">("finance");
  const [menuOpen, setMenuOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceDisplayName, setWorkspaceDisplayName] = useState("");
  const [members, setMembers] = useState<Member[]>([]);
  const [myMembership, setMyMembership] = useState<Member | null>(null);
  const [membershipResolved, setMembershipResolved] = useState(false);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [collaborationError, setCollaborationError] = useState("");
  const [collaborationLoading, setCollaborationLoading] = useState(false);
  const [inviteRole, setInviteRole] = useState<"admin" | "worker">("worker");
  const [invitationExpiryHours, setInvitationExpiryHours] = useState("");
  const [createdInviteUrl, setCreatedInviteUrl] = useState("");
  const [applications, setApplications] = useState<InvitationApplication[]>([]);
  const [applicationPhotos, setApplicationPhotos] = useState<Record<string, string>>({});
  const [applicationFullName, setApplicationFullName] = useState("");
  const [applicationPhone, setApplicationPhone] = useState("");
  const [applicationDetails, setApplicationDetails] = useState("");
  const [applicationPhoto, setApplicationPhoto] = useState("");
  const [applicationConsent, setApplicationConsent] = useState(false);
  const [invitePermissions, setInvitePermissions] = useState<Record<string, boolean>>({ "sales:read": true });
  const [memberReason, setMemberReason] = useState("");
  const [suspensionHours, setSuspensionHours] = useState("24");
  const [editingMemberId, setEditingMemberId] = useState("");
  const [editRole, setEditRole] = useState<"admin" | "worker">("worker");
  const [editPermissions, setEditPermissions] = useState<Record<string, boolean>>({});
  const [leavePhrase, setLeavePhrase] = useState("");
  const [leavePassword, setLeavePassword] = useState("");
  const [leaveReason, setLeaveReason] = useState("");
  const [leaveNoticeHours, setLeaveNoticeHours] = useState("");

  async function hydrate(token: string): Promise<void> {
    const [identity, availableWorkspaces] = await Promise.all([
      apiRequest<User>("/auth/me", {}, token),
      apiRequest<Workspace[]>("/businesses", {}, token),
    ]);
    setUser(identity);
    setWorkspaces(availableWorkspaces);
    const remembered = sessionStorage.getItem("exprofit_workspace_id");
    const nextId = availableWorkspaces.some((item) => item.id === remembered)
      ? remembered ?? ""
      : availableWorkspaces[0]?.id ?? "";
    setSelectedWorkspaceId(nextId);
    if (nextId) sessionStorage.setItem("exprofit_workspace_id", nextId);
  }

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 3500);
    fetch(`${apiBase}/health`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("API health check failed");
        return response.json();
      })
      .then((data: { status?: string }) => setApiStatus(data.status === "ok" ? "online" : "offline"))
      .catch(() => setApiStatus("offline"))
      .finally(() => window.clearTimeout(timeout));
    return () => {
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, []);

  useEffect(() => {
    // Remove one-time tokens from browser history immediately after capturing them in memory.
    if (routeMode !== "app") {
      window.history.replaceState({}, "", window.location.pathname);
    }

    if (accessToken) {
      void hydrate(accessToken).catch(() => {
        sessionStorage.removeItem("exprofit_access_token");
        sessionStorage.removeItem("exprofit_workspace_id");
        setAccessToken(null);
        setUser(null);
        setWorkspaces([]);
        setMembers([]);
        setMyMembership(null);
        setMembershipResolved(false);
        setAuditEvents([]);
      });
    }

  }, []);

  async function submitAuth(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setAuthError("");
    setNotice("");
    try {
      const endpoint = authMode === "register" ? "/auth/register" : "/auth/login";
      const result = await apiRequest<{ access_token: string }>(endpoint, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      sessionStorage.setItem("exprofit_access_token", result.access_token);
      setAccessToken(result.access_token);
      await hydrate(result.access_token);
      setPassword("");
      setAuthError("");
    } catch (error) {
      setAuthError(messageFromError(error));
    } finally {
      setBusy(false);
    }
  }

  async function logout(): Promise<void> {
    const currentToken = accessToken;
    setBusy(true);
    try {
      if (currentToken) {
        await apiRequest<void>("/auth/logout", { method: "POST" }, currentToken);
      }
    } catch {
      // Clear the local session even if the API is unavailable.
    } finally {
      sessionStorage.removeItem("exprofit_access_token");
      sessionStorage.removeItem("exprofit_workspace_id");
      setAccessToken(null);
      setUser(null);
      setWorkspaces([]);
      setMembers([]);
      setMyMembership(null);
      setMembershipResolved(true);
      setAuditEvents([]);
      setCollaborationError("");
      setSelectedWorkspaceId("");
      setNotice("You have signed out.");
      setBusy(false);
    }
  }

  async function submitInvitationApplication(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!accessToken || !pendingToken) return;
    if (!applicationPhoto) {
      setNotice("Capture or select a JPEG face photo before submitting.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await apiRequest<InvitationApplication>(
        "/invitations/apply",
        {
          method: "POST",
          body: JSON.stringify({
            token: pendingToken,
            full_name: applicationFullName,
            phone: applicationPhone || null,
            identifying_details: applicationDetails,
            photo_data_url: applicationPhoto,
            consent: applicationConsent,
          }),
        },
        accessToken,
      );
      setPendingToken("");
      setApplicationPhoto("");
      setApplicationConsent(false);
      setNotice("Application submitted. Workspace access will be granted only if the owner approves it.");
    } catch (error) {
      setNotice(messageFromError(error));
    } finally {
      setBusy(false);
    }
  }

  async function loadApplicationPhoto(applicationId: string): Promise<void> {
    if (!accessToken || !selectedWorkspaceId) return;
    try {
      const response = await fetch(
        `${apiBase}/businesses/${selectedWorkspaceId}/invitation-applications/${applicationId}/photo`,
        { headers: { Authorization: `Bearer ${accessToken}` } },
      );
      if (!response.ok) throw new Error("Could not load this private photo.");
      const objectUrl = URL.createObjectURL(await response.blob());
      setApplicationPhotos((current) => {
        const previous = current[applicationId];
        if (previous) URL.revokeObjectURL(previous);
        return { ...current, [applicationId]: objectUrl };
      });
    } catch (error) {
      setCollaborationError(messageFromError(error));
    }
  }

  async function reviewApplication(applicationId: string, decision: "approve" | "reject"): Promise<void> {
    if (!accessToken || !selectedWorkspaceId) return;
    setBusy(true);
    setCollaborationError("");
    try {
      await apiRequest(
        `/businesses/${selectedWorkspaceId}/invitation-applications/${applicationId}/${decision}`,
        { method: "POST", body: JSON.stringify({}) },
        accessToken,
      );
      setNotice(decision === "approve" ? "Applicant approved and added to the workspace." : "Application rejected.");
      setApplicationPhotos((current) => {
        if (current[applicationId]) URL.revokeObjectURL(current[applicationId]);
        const next = { ...current };
        delete next[applicationId];
        return next;
      });
      await refreshCollaboration();
    } catch (error) {
      setCollaborationError(messageFromError(error));
    } finally {
      setBusy(false);
    }
  }

  async function createWorkspace(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!accessToken) return;
    setBusy(true);
    setNotice("");
    try {
      const created = await apiRequest<Workspace>(
        "/businesses",
        {
          method: "POST",
          body: JSON.stringify({
            name: workspaceName,
            display_name: workspaceDisplayName || null,
            currency_code: "NGN",
            timezone: "Africa/Lagos",
          }),
        },
        accessToken,
      );
      const refreshed = await apiRequest<Workspace[]>("/businesses", {}, accessToken);
      setWorkspaces(refreshed);
      setSelectedWorkspaceId(created.id);
      sessionStorage.setItem("exprofit_workspace_id", created.id);
      setWorkspaceName("");
      setWorkspaceDisplayName("");
      setNotice("Business workspace created. Your Solo workspace remains separate.");
    } catch (error) {
      setNotice(messageFromError(error));
    } finally {
      setBusy(false);
    }
  }


  async function refreshCollaboration(): Promise<void> {
    if (!accessToken || !selectedWorkspaceId) return;
    try {
      const [availableMembers, events, pendingApplications] = await Promise.all([
        apiRequest<Member[]>(`/businesses/${selectedWorkspaceId}/members`, {}, accessToken),
        apiRequest<AuditEvent[]>(`/businesses/${selectedWorkspaceId}/audit-events?limit=12`, {}, accessToken),
        apiRequest<InvitationApplication[]>(`/businesses/${selectedWorkspaceId}/invitation-applications`, {}, accessToken),
      ]);
      setMembers(availableMembers);
      setAuditEvents(events);
      setApplications(pendingApplications);
      setCollaborationError("");
    } catch (error) {
      setMembers([]);
      setAuditEvents([]);
      setApplications([]);
      setCollaborationError(messageFromError(error));
    }
  }

  async function createInvitation(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!accessToken || !selectedWorkspaceId) return;
    setBusy(true);
    setNotice("");
    setCollaborationError("");
    const permissions = Object.fromEntries(
      Object.entries(invitePermissions).filter(([, granted]) => granted),
    );
    try {
      const result = await apiRequest<{ id: string; invitation_url: string; expires_at: string }>(
        `/businesses/${selectedWorkspaceId}/invitations`,
        {
          method: "POST",
          body: JSON.stringify({
            role: inviteRole,
            permissions,
            expires_in_hours: Number(invitationExpiryHours),
          }),
        },
        accessToken,
      );
      setCreatedInviteUrl(result.invitation_url);
      setNotice(`Invitation link generated. It expires at ${new Date(result.expires_at).toLocaleString()}. Copy and send it yourself.`);
      await refreshCollaboration();
    } catch (error) {
      setCollaborationError(messageFromError(error));
    } finally {
      setBusy(false);
    }
  }

  function beginMemberEdit(member: Member): void {
    setEditingMemberId(member.membership_id);
    setEditRole(member.role === "admin" ? "admin" : "worker");
    setEditPermissions({ ...member.permissions });
    setMemberReason("");
    setCollaborationError("");
  }

  async function saveMemberEdit(event: FormEvent<HTMLFormElement>, member: Member): Promise<void> {
    event.preventDefault();
    if (!accessToken || !selectedWorkspaceId) return;
    if (!memberReason.trim()) {
      setCollaborationError("Enter a reason for changing this member's access.");
      return;
    }
    setBusy(true);
    setCollaborationError("");
    try {
      await apiRequest<Member>(
        `/businesses/${selectedWorkspaceId}/members/${member.membership_id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            role: editRole,
            permissions: editPermissions,
            reason: memberReason,
          }),
        },
        accessToken,
      );
      setEditingMemberId("");
      setNotice(`Access updated for ${member.email}.`);
      await refreshCollaboration();
    } catch (error) {
      setCollaborationError(messageFromError(error));
    } finally {
      setBusy(false);
    }
  }

  async function runMemberAction(member: Member, action: "suspend" | "revoke" | "reinstate"): Promise<void> {
    if (!accessToken || !selectedWorkspaceId) return;
    if (!memberReason.trim()) {
      setCollaborationError("Enter a reason before changing a member's status.");
      return;
    }
    if (action === "suspend" && suspensionHours && (!Number.isInteger(Number(suspensionHours)) || Number(suspensionHours) < 1 || Number(suspensionHours) > 720)) {
      setCollaborationError("Suspension duration must be 1–720 hours, or blank for indefinite suspension.");
      return;
    }
    setBusy(true);
    setCollaborationError("");
    try {
      const body = action === "suspend"
        ? { reason: memberReason, duration_hours: suspensionHours ? Number(suspensionHours) : null }
        : { reason: memberReason };
      await apiRequest<Member>(
        `/businesses/${selectedWorkspaceId}/members/${member.membership_id}/${action}`,
        { method: "POST", body: JSON.stringify(body) },
        accessToken,
      );
      setNotice(`${member.email}'s membership was ${action === "revoke" ? "revoked" : action === "reinstate" ? "reinstated" : "suspended"}.`);
      setMemberReason("");
      await refreshCollaboration();
    } catch (error) {
      setCollaborationError(messageFromError(error));
    } finally {
      setBusy(false);
    }
  }


  async function requestLeave(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!accessToken || !selectedWorkspaceId) return;
    setBusy(true);
    setNotice("");
    setCollaborationError("");
    try {
      const result = await apiRequest<{ status: string; effective_at: string | null; message: string }>(
        `/businesses/${selectedWorkspaceId}/leave`,
        {
          method: "POST",
          body: JSON.stringify({
            confirmation_phrase: leavePhrase,
            password: leavePassword,
            reason: leaveReason,
            notice_hours: leaveNoticeHours ? Number(leaveNoticeHours) : null,
          }),
        },
        accessToken,
      );
      setNotice(result.message);
      setLeavePassword("");
      setLeavePhrase("");
      setLeaveReason("");
      setLeaveNoticeHours("");
      if (result.status === "revoked") {
        await hydrate(accessToken);
      } else {
        if (isWorkspaceOwner || currentMembership?.permissions["staff_administration:read"] === true) {
          await refreshCollaboration();
        }
        const membership = await apiRequest<Member>(`/businesses/${selectedWorkspaceId}/membership`, {}, accessToken);
        setMyMembership(membership);
      }
    } catch (error) {
      setCollaborationError(messageFromError(error));
    } finally {
      setBusy(false);
    }
  }

  function selectWorkspace(id: string): void {
    setSelectedWorkspaceId(id);
    sessionStorage.setItem("exprofit_workspace_id", id);
  }

  const selectedWorkspace = workspaces.find((item) => item.id === selectedWorkspaceId);
  const currentMembership = myMembership;
  const isWorkspaceOwner = currentMembership?.role === "owner";
  const canManageMembers = isWorkspaceOwner || (
    currentMembership?.permissions["staff_administration:read"] === true &&
    currentMembership?.permissions["staff_administration:write"] === true
  );

  useEffect(() => {
    if (!accessToken || !selectedWorkspaceId || selectedWorkspace?.workspace_type !== "business") {
      setMembers([]);
      setMyMembership(null);
      setMembershipResolved(true);
      setAuditEvents([]);
      setCollaborationError("");
      return;
    }
    let cancelled = false;
    setCollaborationLoading(true);
    setMyMembership(null);
    setMembershipResolved(false);
    apiRequest<Member>(`/businesses/${selectedWorkspaceId}/membership`, {}, accessToken)
      .then((membership) => {
        if (!cancelled) {
          setMyMembership(membership);
          setMembershipResolved(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMyMembership(null);
          setMembershipResolved(true);
        }
      });
    Promise.all([
      apiRequest<Member[]>(`/businesses/${selectedWorkspaceId}/members`, {}, accessToken),
      apiRequest<AuditEvent[]>(`/businesses/${selectedWorkspaceId}/audit-events?limit=12`, {}, accessToken),
      apiRequest<InvitationApplication[]>(`/businesses/${selectedWorkspaceId}/invitation-applications`, {}, accessToken),
    ])
      .then(([availableMembers, events, pendingApplications]) => {
        if (cancelled) return;
        setMembers(availableMembers);
        setAuditEvents(events);
        setApplications(pendingApplications);
        setCollaborationError("");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setMembers([]);
        setApplications([]);
        setCollaborationError(messageFromError(error));
      })
      .finally(() => {
        if (!cancelled) setCollaborationLoading(false);
      });
    return () => { cancelled = true; };
  }, [accessToken, selectedWorkspaceId, workspaces]);
  const statusLabel: Record<ApiStatus, string> = {
    checking: "Checking API",
    online: "API connected",
    offline: "API not connected",
  };

  const authForm = (
    <form className="auth-form" onSubmit={submitAuth}>
      <div className="auth-switch" role="group" aria-label="Account action">
        <button type="button" className={authMode === "login" ? "selected" : ""} onClick={() => setAuthMode("login")}>Sign in</button>
        <button type="button" className={authMode === "register" ? "selected" : ""} onClick={() => setAuthMode("register")}>Create account</button>
      </div>
      <label htmlFor="email">Email address</label>
      <input id="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
      <label htmlFor="password">Password <span>{authMode === "register" ? "(at least 12 characters)" : ""}</span></label>
      <input id="password" type="password" autoComplete={authMode === "register" ? "new-password" : "current-password"} minLength={authMode === "register" ? 12 : 1} value={password} onChange={(event) => setPassword(event.target.value)} required />
      {authError && <p className="form-message form-message--error" role="alert">{authError}</p>}
      <button className="button button--primary form-submit" type="submit" disabled={busy}>
        {busy ? "Please wait…" : authMode === "register" ? "Create private Solo workspace" : "Sign in"}
      </button>
      <p className="form-hint">New accounts start with a private Solo workspace. Joining a business never moves your Solo records.</p>
    </form>
  );

  if (routeMode === "accept-invitation") {
    return (
      <main className="page-shell account-page">
        <header className="topbar">
          <a className="brand" href="/" onClick={(event) => { event.preventDefault(); window.history.replaceState({}, "", "/"); setRouteMode("app"); }}>
            <span className="brand-mark" aria-hidden="true">e</span><span>exprofit</span>
          </a>
          <span className={`connection connection--${apiStatus}`}><span className="connection-dot" />{statusLabel[apiStatus]}</span>
        </header>
        <section className="account-card invitation-application-card">
          <p className="eyebrow">BUSINESS WORKSPACE</p>
          <h1 className="account-title">Apply to join.</h1>
          <p className="hero-copy">The owner will review your details and face photo before granting access. This link alone never grants workspace access.</p>
          {!pendingToken && <p className="form-message form-message--error" role="alert">The invitation link is missing its token. Ask the owner for a new link.</p>}
          {!user && authForm}
          {user && pendingToken && (
            <>
              <p className="form-hint">Signed in as {user.email}. No email verification or paid verification service is required.</p>
              <form className="collaboration-form invitation-application-form" onSubmit={submitInvitationApplication}>
                <label htmlFor="application-full-name">Your full name</label>
                <input id="application-full-name" autoComplete="name" value={applicationFullName} onChange={(event) => setApplicationFullName(event.target.value)} maxLength={160} required />
                <label htmlFor="application-phone">Phone number <span>(optional)</span></label>
                <input id="application-phone" type="tel" autoComplete="tel" value={applicationPhone} onChange={(event) => setApplicationPhone(event.target.value)} maxLength={40} />
                <label htmlFor="application-details">Details the owner can use to recognize you</label>
                <textarea id="application-details" value={applicationDetails} onChange={(event) => setApplicationDetails(event.target.value)} maxLength={1200} rows={4} placeholder="For example, where you met or the role you discussed." required />
                <label htmlFor="application-photo">Face photo (JPEG, up to 2 MB)</label>
                <input id="application-photo" type="file" accept="image/jpeg" capture="user" onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (!file) { setApplicationPhoto(""); return; }
                  if (file.size > 2 * 1024 * 1024 || file.type !== "image/jpeg") {
                    setApplicationPhoto("");
                    setNotice("Choose a JPEG photo no larger than 2 MB.");
                    return;
                  }
                  const reader = new FileReader();
                  reader.onload = () => setApplicationPhoto(typeof reader.result === "string" ? reader.result : "");
                  reader.onerror = () => setNotice("Could not read the selected photo. Please try again.");
                  reader.readAsDataURL(file);
                }} required />
                {applicationPhoto && <p className="form-hint">Photo ready to submit. The owner can view it privately while the application is pending.</p>}
                <label className="consent-option">
                  <input type="checkbox" checked={applicationConsent} onChange={(event) => setApplicationConsent(event.target.checked)} required />
                  <span>I consent to the workspace owner reviewing my submitted details and face photo for this invitation. The photo is stored privately while the application is pending and deleted after a decision or expiry cleanup.</span>
                </label>
                <button className="button button--primary form-submit" type="submit" disabled={busy || !pendingToken || !applicationPhoto || !applicationConsent}>{busy ? "Submitting…" : "Submit for owner review"}</button>
              </form>
            </>
          )}
          {notice && <p className="form-message" role="status">{notice}</p>}
          {user && <button className="text-button" type="button" onClick={() => void logout()}>Sign out</button>}
        </section>
      </main>
    );
  }

  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Exprofit home">
          <span className="brand-mark" aria-hidden="true">e</span><span>exprofit</span>
        </a>
        <div className="topbar-actions">
          <span className={`connection connection--${apiStatus}`}>
            <span className="connection-dot" aria-hidden="true" />{statusLabel[apiStatus]}
          </span>
          {user && <button className="menu-toggle" type="button" aria-expanded={menuOpen} aria-controls="app-navigation" onClick={() => setMenuOpen((open) => !open)}><span aria-hidden="true">{menuOpen ? "×" : "☰"}</span><span>{menuOpen ? "Close menu" : "Menu"}</span></button>}
          {user && <button className="text-button" type="button" onClick={() => void logout()} disabled={busy}>Sign out</button>}
        </div>
      </header>

      {user ? (
        <section className="workspace-page">
          <div className={`app-navigation-wrap${menuOpen ? " app-navigation-wrap--open" : ""}`}>
            <nav id="app-navigation" className="app-navigation" aria-label="Main navigation" hidden={!menuOpen}>
              <p className="eyebrow">YOUR WORKSPACE</p>
              <button type="button" className={activePage === "finance" ? "app-nav-item app-nav-item--active" : "app-nav-item"} onClick={() => { setActivePage("finance"); setMenuOpen(false); }}>⌂ <span><strong>Financial overview</strong><small>Transactions, receipts and insights</small></span></button>
              <button type="button" className={activePage === "workspaces" ? "app-nav-item app-nav-item--active" : "app-nav-item"} onClick={() => { setActivePage("workspaces"); setMenuOpen(false); }}>▦ <span><strong>Workspaces</strong><small>Private Solo and business spaces</small></span></button>
              {selectedWorkspace?.workspace_type === "business" && <button type="button" className={activePage === "team" ? "app-nav-item app-nav-item--active" : "app-nav-item"} onClick={() => { setActivePage("team"); setMenuOpen(false); }}>♧ <span><strong>People & access</strong><small>Members, invitations and audit history</small></span></button>}
              <div className="app-nav-current"><small>Currently viewing</small><strong>{selectedWorkspace?.display_name || selectedWorkspace?.name || "Your workspace"}</strong><span>{selectedWorkspace?.workspace_type === "solo" ? "Private Solo workspace" : "Business workspace"}</span></div>
            </nav>
          </div>
          <div className="workspace-heading">
            <div>
              <p className="eyebrow">YOUR EXPROFIT ACCOUNT</p>
              <h1 className="account-title">{activePage === "finance" ? "Financial overview." : activePage === "workspaces" ? "Your workspaces." : "People and access."}</h1>
              <p className="hero-copy">{activePage === "finance" ? "Your financial activity, receipts, margin signals and planning tools in one organized workspace." : activePage === "workspaces" ? `Signed in as ${user.email}. Each workspace keeps its own records and access rules.` : "Manage who can access this business workspace and review membership activity."}</p>
            </div>
          </div>

          {notice && <p className="form-message" role="status">{notice}</p>}

          {activePage === "workspaces" && <section className="workspace-picker">
            <label htmlFor="workspace-select">Current workspace</label>
            <select id="workspace-select" value={selectedWorkspaceId} onChange={(event) => selectWorkspace(event.target.value)}>
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.workspace_type === "solo" ? "Solo Mode" : "Business"} · {workspace.display_name || workspace.name}
                </option>
              ))}
            </select>
            {selectedWorkspace && (
              <div className="workspace-detail">
                <span className="workspace-type">{selectedWorkspace.workspace_type === "solo" ? "PRIVATE SOLO WORKSPACE" : "BUSINESS WORKSPACE"}</span>
                <h2>{selectedWorkspace.display_name || selectedWorkspace.name}</h2>
                <p>{selectedWorkspace.currency_code} · {selectedWorkspace.timezone}</p>
                {selectedWorkspace.workspace_type === "solo" && <p className="form-hint">Only your account has access to this workspace. Creating or joining a business does not share these records.</p>}
              </div>
            )}
          </section>}

          {activePage === "finance" && selectedWorkspace && accessToken && <FinancialWorkspace workspace={selectedWorkspace} accessToken={accessToken} membership={currentMembership} membershipResolved={membershipResolved} />}

          {activePage === "workspaces" && <section className="create-workspace-card">
            <div>
              <p className="eyebrow">GROW WITH YOUR BUSINESS</p>
              <h2>Create a business workspace</h2>
              <p className="form-hint">This creates a separate workspace. It does not copy transactions, receipts, or other Solo records.</p>
            </div>
            <form className="workspace-form" onSubmit={createWorkspace}>
              <label htmlFor="workspace-name">Workspace name</label>
              <input id="workspace-name" value={workspaceName} onChange={(event) => setWorkspaceName(event.target.value)} maxLength={120} required />
              <label htmlFor="workspace-display-name">Display name <span>(optional)</span></label>
              <input id="workspace-display-name" value={workspaceDisplayName} onChange={(event) => setWorkspaceDisplayName(event.target.value)} maxLength={120} />
              <button className="button button--primary form-submit" type="submit" disabled={busy}>{busy ? "Working…" : "Create workspace"}</button>
            </form>
          </section>}

          {activePage === "team" && selectedWorkspace?.workspace_type === "business" && (
            <section className="collaboration-panel">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">BUSINESS COLLABORATION</p>
                  <h2>People and access</h2>
                </div>
                <p>Permissions are checked by the API, not just this screen.</p>
              </div>

              {collaborationLoading && <p className="form-hint">Loading members and audit history…</p>}
              {collaborationError && <p className="form-message form-message--error" role="alert">{collaborationError}</p>}
              {!collaborationLoading && !collaborationError && (
                <div className="member-list">
                  {members.map((member) => (
                    <article className="member-card" key={member.membership_id}>
                      <div className="member-summary">
                        <div>
                          <strong>{member.email}</strong>
                          <p>{member.role} · {member.status}</p>
                          {member.leave_effective_at && member.status !== "revoked" && (
                            <p className="form-hint">Departure scheduled: {new Date(member.leave_effective_at).toLocaleString()}</p>
                          )}
                        </div>
                        <div className="member-permission-summary">
                          {Object.entries(member.permissions).filter(([, granted]) => granted).map(([key]) => (
                            <span key={key}>{key}</span>
                          ))}
                          {member.role === "owner" && <span>owner access</span>}
                        </div>
                      </div>
                      {canManageMembers && member.role !== "owner" && member.user_id !== user.id && member.status !== "revoked" && (
                        <div className="member-actions">
                          <button className="button button--secondary" type="button" onClick={() => beginMemberEdit(member)}>Edit access</button>
                          {member.status === "active" && <button className="button button--secondary" type="button" onClick={() => void runMemberAction(member, "suspend")} disabled={busy}>Suspend</button>}
                          {member.status === "suspended" && <button className="button button--secondary" type="button" onClick={() => void runMemberAction(member, "reinstate")} disabled={busy}>Reinstate</button>}
                          <button className="button button--danger" type="button" onClick={() => void runMemberAction(member, "revoke")} disabled={busy}>Revoke</button>
                        </div>
                      )}
                      {editingMemberId === member.membership_id && canManageMembers && (
                        <form className="member-edit-form" onSubmit={(event) => void saveMemberEdit(event, member)}>
                          <label htmlFor={`role-${member.membership_id}`}>Role</label>
                          <select
                            id={`role-${member.membership_id}`}
                            value={editRole}
                            onChange={(event) => {
                              const role = event.target.value as "admin" | "worker";
                              setEditRole(role);
                              if (role === "worker") {
                                setEditPermissions((current) => ({
                                  ...current,
                                  "staff_administration:read": false,
                                  "staff_administration:write": false,
                                }));
                              }
                            }}
                            disabled={!isWorkspaceOwner}
                          >
                            <option value="worker">Worker</option>
                            <option value="admin" disabled={!isWorkspaceOwner}>Admin (Owner only)</option>
                          </select>
                          <p className="form-hint">Grant only the access this person needs.</p>
                          <div className="permission-grid">
                            {[
                              ["sales:read", "Read sales"],
                              ["sales:write", "Write sales"],
                              ["expenses:read", "Read expenses"],
                              ["expenses:write", "Write expenses"],
                              ...(isWorkspaceOwner && editRole === "admin" ? [
                                ["staff_administration:read", "Read member directory and audit"],
                                ["staff_administration:write", "Manage members and invitations"],
                              ] : []),
                            ].map(([key, label]) => (
                              <label className="permission-option" key={key}>
                                <input
                                  type="checkbox"
                                  checked={editPermissions[key] === true}
                                  onChange={(event) => setEditPermissions((current) => ({ ...current, [key]: event.target.checked }))}
                                />
                                <span>{label}</span>
                              </label>
                            ))}
                          </div>
                          <label htmlFor="member-reason-edit">Reason for change</label>
                          <input id="member-reason-edit" value={memberReason} onChange={(event) => setMemberReason(event.target.value)} maxLength={500} required />
                          <div className="member-actions">
                            <button className="button button--primary" type="submit" disabled={busy}>Save access</button>
                            <button className="button button--secondary" type="button" onClick={() => setEditingMemberId("")}>Cancel</button>
                          </div>
                        </form>
                      )}
                    </article>
                  ))}
                  {members.length === 0 && <p className="form-hint">No member records are available for this workspace.</p>}
                </div>
              )}

              {canManageMembers && (
                <div className="collaboration-columns">
                  {isWorkspaceOwner && (
                  <form className="collaboration-form" onSubmit={createInvitation}>
                    <p className="eyebrow">INVITE A PERSON</p>
                    <h3>Generate a shareable link</h3>
                    <label htmlFor="invite-role">Role</label>
                    <select id="invite-role" value={inviteRole} onChange={(event) => {
                        const role = event.target.value as "admin" | "worker";
                        setInviteRole(role);
                        if (role === "worker") {
                          setInvitePermissions((current) => ({
                            ...current,
                            "staff_administration:read": false,
                            "staff_administration:write": false,
                          }));
                        }
                      }}>
                      <option value="worker">Worker</option>
                      <option value="admin" disabled={!isWorkspaceOwner}>Admin (Owner only)</option>
                    </select>
                    <label htmlFor="invite-expiry">Link expires after (hours)</label>
                    <input id="invite-expiry" type="number" min="1" max="720" value={invitationExpiryHours} onChange={(event) => setInvitationExpiryHours(event.target.value)} required />
                    <p className="form-hint">You choose the expiry period. Anyone with the link may apply, but only the owner can approve access.</p>
                    <div className="permission-grid">
                      {[
                        ["sales:read", "Read sales"],
                        ["sales:write", "Write sales"],
                        ["expenses:read", "Read expenses"],
                        ["expenses:write", "Write expenses"],
                        ...(isWorkspaceOwner && inviteRole === "admin" ? [
                          ["staff_administration:read", "Read member directory and audit"],
                          ["staff_administration:write", "Manage members and invitations"],
                        ] : []),
                      ].map(([key, label]) => (
                        <label className="permission-option" key={key}>
                          <input
                            type="checkbox"
                            checked={invitePermissions[key] === true}
                            onChange={(event) => setInvitePermissions((current) => ({ ...current, [key]: event.target.checked }))}
                          />
                          <span>{label}</span>
                        </label>
                      ))}
                    </div>
                    <button className="button button--primary form-submit" type="submit" disabled={busy}>{busy ? "Generating…" : "Generate invitation link"}</button>
                    {createdInviteUrl && (
                      <div className="generated-invitation">
                        <label htmlFor="generated-invitation-url">Copy this link and send it yourself</label>
                        <input id="generated-invitation-url" value={createdInviteUrl} readOnly onFocus={(event) => event.currentTarget.select()} />
                        <button className="button button--secondary" type="button" onClick={() => {
                          void navigator.clipboard?.writeText(createdInviteUrl).then(() => setNotice("Invitation link copied. Send it using your preferred app."));
                        }}>Copy link</button>
                      </div>
                    )}
                  </form>
                  )}

                  <div className="member-action-settings">
                    <p className="eyebrow">MEMBERSHIP SAFETY</p>
                    <h3>Suspend or revoke access</h3>
                    <label htmlFor="suspension-hours">Suspension duration in hours <span>(blank = indefinite)</span></label>
                    <input id="suspension-hours" type="number" min="1" max="720" value={suspensionHours} onChange={(event) => setSuspensionHours(event.target.value)} />
                    <label htmlFor="member-action-reason">Reason for member action</label>
                    <input id="member-action-reason" value={memberReason} onChange={(event) => setMemberReason(event.target.value)} maxLength={500} placeholder="Explain why access is changing" />
                    <p className="form-hint">Suspension and revocation take effect immediately. A timed suspension is reinstated automatically after its deadline. Revoked members need a new invitation to return.</p>
                  </div>
                </div>
              )}

              {isWorkspaceOwner && (
                <section className="application-review-panel">
                  <div className="section-heading">
                    <div><p className="eyebrow">OWNER REVIEW</p><h3>Applications waiting for approval</h3></div>
                    <p>Review each person's details and photo before granting workspace access.</p>
                  </div>
                  {applications.length === 0 && <p className="form-hint">No pending applications.</p>}
                  <div className="member-list">
                    {applications.map((application) => (
                      <article className="member-card" key={application.id}>
                        <div className="member-summary">
                          <div>
                            <strong>{application.full_name}</strong>
                            <p>{application.email} · {application.role}</p>
                            {application.phone && <p>{application.phone}</p>}
                            <p>{application.identifying_details}</p>
                          </div>
                        </div>
                        {applicationPhotos[application.id] ? (
                          <img className="application-face-photo" src={applicationPhotos[application.id]} alt={`Face photo submitted by ${application.full_name}`} />
                        ) : (
                          <button className="button button--secondary" type="button" onClick={() => void loadApplicationPhoto(application.id)}>View private face photo</button>
                        )}
                        <div className="member-actions">
                          <button className="button button--primary" type="button" onClick={() => void reviewApplication(application.id, "approve")} disabled={busy}>Approve and grant access</button>
                          <button className="button button--danger" type="button" onClick={() => void reviewApplication(application.id, "reject")} disabled={busy}>Reject</button>
                        </div>
                      </article>
                    ))}
                  </div>
                </section>
              )}

              {currentMembership?.role === "owner" && (
                <div className="verification-notice">
                  <div><strong>Owner departure is restricted</strong><p>Transfer workspace ownership first. Ownership transfer is not available in this release.</p></div>
                </div>
              )}
              {currentMembership && currentMembership.role !== "owner" && (
                <section className="leave-workspace-card">
                  <p className="eyebrow">YOUR MEMBERSHIP</p>
                  <h3>Leave this workspace</h3>
                  {currentMembership.leave_effective_at ? (
                    <p className="form-hint">Your departure is scheduled for {new Date(currentMembership.leave_effective_at).toLocaleString()}. An administrator can still revoke access immediately.</p>
                  ) : (
                    <>
                      {currentMembership.status === "suspended" && <p className="form-hint">Your access is currently suspended, but you can still request to leave.</p>}
                      <p className="form-hint">Confirm with your password. Leaving does not delete historical financial records.</p>
                      <form className="leave-form" onSubmit={requestLeave}>
                        <label htmlFor="leave-phrase">Type exactly: I want to leave</label>
                        <input id="leave-phrase" value={leavePhrase} onChange={(event) => setLeavePhrase(event.target.value)} autoCapitalize="off" spellCheck={false} required />
                        <label htmlFor="leave-password">Confirm your password</label>
                        <input id="leave-password" type="password" autoComplete="current-password" value={leavePassword} onChange={(event) => setLeavePassword(event.target.value)} required />
                        <label htmlFor="leave-reason">Reason for leaving</label>
                        <textarea id="leave-reason" value={leaveReason} onChange={(event) => setLeaveReason(event.target.value)} maxLength={500} rows={3} required />
                        <label htmlFor="leave-notice">Notice period in hours <span>(blank = leave immediately)</span></label>
                        <input id="leave-notice" type="number" min="1" max="720" value={leaveNoticeHours} onChange={(event) => setLeaveNoticeHours(event.target.value)} />
                        <button className="button button--danger form-submit" type="submit" disabled={busy}>{busy ? "Processing…" : "Confirm departure"}</button>
                      </form>
                    </>
                  )}
                </section>
              )}

              <section className="audit-panel">
                <div className="section-heading">
                  <div><p className="eyebrow">ACCOUNTABILITY</p><h3>Recent audit events</h3></div>
                </div>
                {auditEvents.length === 0 && !collaborationError && <p className="form-hint">No audit events to show.</p>}
                {auditEvents.map((event) => (
                  <div className="audit-row" key={event.id}>
                    <div><strong>{event.event_type.replace(/\./g, " ")}</strong><p>{event.reason || event.target_type}</p></div>
                    <time dateTime={event.created_at}>{new Date(event.created_at).toLocaleString()}</time>
                  </div>
                ))}
              </section>
            </section>
          )}
        </section>
      ) : (
        <>
          <section className="hero">
            <p className="eyebrow">YOUR BUSINESS, IN CLEARER FOCUS</p>
            <h1>Know where your money goes.<br /><em>Understand what you keep.</em></h1>
            <p className="hero-copy">A practical home for your business records, receipts, and profit questions. Built to show the evidence behind the numbers—not just another dashboard.</p>
            <div className="hero-actions">
              <a className="button button--primary" href="#account">Start with your private workspace <span aria-hidden="true">↘</span></a>
              <span className="quiet-note">Early development · Your records stay yours</span>
            </div>
          </section>

          <section id="account" className="auth-layout">
            <div className="auth-intro">
              <p className="eyebrow">START PRIVATE. COLLABORATE WHEN READY.</p>
              <h2>Your account, your choice.</h2>
              <p className="hero-copy">Begin in Solo Mode with a private workspace. Add a business workspace only when you need to work with other people.</p>
            </div>
            <div className="auth-card">{authForm}</div>
          </section>

          <section className="workflow">
            <div className="section-heading">
              <div><p className="eyebrow">THE EXPROFIT WORKFLOW</p><h2>From records to better questions.</h2></div>
              <p>Start with what you know. Investigate what you don't.</p>
            </div>
            <div className="feature-grid">
              <article className="feature-card feature-card--featured">
                <span className="card-number">01 / RECORD</span><div className="feature-icon" aria-hidden="true">↗</div>
                <h3>Track money in and out</h3><p>Keep income, expenses, and categories in one place, with clear dates and currencies.</p><span className="card-status">CORE FOUNDATION</span>
              </article>
              <article className="feature-card">
                <span className="card-number">02 / CAPTURE</span><div className="feature-icon" aria-hidden="true">▤</div>
                <h3>Bring receipts into focus</h3><p>Extract useful details, review them yourself, and correct mistakes before saving.</p><span className="card-status">PLANNED</span>
              </article>
              <article className="feature-card">
                <span className="card-number">03 / INVESTIGATE</span><div className="feature-icon" aria-hidden="true">⌁</div>
                <h3>Follow the margin</h3><p>Inspect the figures and records behind a change instead of guessing at its cause.</p><span className="card-status">PLANNED</span>
              </article>
            </div>
          </section>
          <section className="principle-strip">
            <span className="principle-symbol" aria-hidden="true">✳</span>
            <div><p className="eyebrow">A NON-NEGOTIABLE PRINCIPLE</p><p className="principle-copy">AI can explain the numbers. <strong>It cannot make them up.</strong></p></div>
            <p className="principle-detail">Calculations stay deterministic. Missing costs and estimates stay visible.</p>
          </section>
        </>
      )}

      <footer className="footer">
        <a className="brand brand--footer" href="/"><span className="brand-mark" aria-hidden="true">e</span> exprofit</a>
        <span>Built for the people building small businesses.</span>
        <span>v0.1 · Foundation</span>
      </footer>
    </main>
  );
}
