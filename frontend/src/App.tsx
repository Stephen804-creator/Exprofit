import { useEffect, useState } from "react";

type ApiStatus = "checking" | "online" | "offline";
type RouteMode = "app" | "verify-email" | "accept-invitation";
type AuthMode = "login" | "register";

type User = {
  id: string;
  email: string;
  is_active: boolean;
  email_verified: boolean;
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

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

function routeFromPath(): RouteMode {
  if (window.location.pathname === "/verify-email") return "verify-email";
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
  const [notice, setNotice] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceDisplayName, setWorkspaceDisplayName] = useState("");

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
      });
    }

    if (routeMode === "verify-email") {
      if (!pendingToken) {
        setNotice("This verification link is missing its token. Request a new email from your account.");
        return;
      }
      void apiRequest<{ message: string }>("/auth/verify-email", {
        method: "POST",
        body: JSON.stringify({ token: pendingToken }),
      })
        .then((result) => {
          setNotice(result.message);
          setPendingToken("");
          const savedToken = sessionStorage.getItem("exprofit_access_token");
          if (savedToken) void hydrate(savedToken).catch(() => undefined);
        })
        .catch((error: unknown) => setNotice(messageFromError(error)));
    }
  }, []);

  async function submitAuth(event: React.FormEvent<HTMLFormElement>): Promise<void> {
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
      setSelectedWorkspaceId("");
      setNotice("You have signed out.");
      setBusy(false);
    }
  }

  async function requestVerification(): Promise<void> {
    if (!accessToken) return;
    setBusy(true);
    setNotice("");
    try {
      const result = await apiRequest<{ message: string }>(
        "/auth/request-email-verification",
        { method: "POST" },
        accessToken,
      );
      setNotice(result.message);
    } catch (error) {
      setNotice(messageFromError(error));
    } finally {
      setBusy(false);
    }
  }

  async function acceptInvitation(): Promise<void> {
    if (!accessToken || !pendingToken) return;
    setBusy(true);
    setNotice("");
    try {
      const result = await apiRequest<{ business_id: string; role: string; status: string }>(
        "/invitations/accept",
        { method: "POST", body: JSON.stringify({ token: pendingToken }) },
        accessToken,
      );
      setPendingToken("");
      setNotice(`Invitation accepted. Your workspace role is ${result.role}.`);
      window.history.replaceState({}, "", "/");
      setRouteMode("app");
      await hydrate(accessToken);
    } catch (error) {
      setNotice(messageFromError(error));
    } finally {
      setBusy(false);
    }
  }

  async function createWorkspace(event: React.FormEvent<HTMLFormElement>): Promise<void> {
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

  function selectWorkspace(id: string): void {
    setSelectedWorkspaceId(id);
    sessionStorage.setItem("exprofit_workspace_id", id);
  }

  const selectedWorkspace = workspaces.find((item) => item.id === selectedWorkspaceId);
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

  if (routeMode === "verify-email") {
    return (
      <main className="page-shell account-page">
        <header className="topbar">
          <a className="brand" href="/" onClick={(event) => { event.preventDefault(); window.history.replaceState({}, "", "/"); setRouteMode("app"); }}>
            <span className="brand-mark" aria-hidden="true">e</span><span>exprofit</span>
          </a>
        </header>
        <section className="account-card">
          <p className="eyebrow">ACCOUNT SECURITY</p>
          <h1 className="account-title">Verify your email.</h1>
          <p className="hero-copy">{notice || "Checking your verification link…"}</p>
          <button className="button button--primary" onClick={() => { window.history.replaceState({}, "", "/"); setRouteMode("app"); }}>Return to Exprofit</button>
        </section>
      </main>
    );
  }

  if (routeMode === "accept-invitation") {
    return (
      <main className="page-shell account-page">
        <header className="topbar">
          <a className="brand" href="/" onClick={(event) => { event.preventDefault(); window.history.replaceState({}, "", "/"); setRouteMode("app"); }}>
            <span className="brand-mark" aria-hidden="true">e</span><span>exprofit</span>
          </a>
          <span className={`connection connection--${apiStatus}`}><span className="connection-dot" />{statusLabel[apiStatus]}</span>
        </header>
        <section className="account-card">
          <p className="eyebrow">BUSINESS WORKSPACE</p>
          <h1 className="account-title">You’re invited.</h1>
          <p className="hero-copy">Sign in with the verified email address that received the invitation. The invitation link is private and expires.</p>
          {user && !user.email_verified && (
            <div className="verification-notice">
              <strong>Your email needs verification.</strong>
              <p>Send a verification email, then open that message to verify this account before accepting.</p>
              <button className="button button--secondary" type="button" onClick={() => void requestVerification()} disabled={busy}>Send verification email</button>
            </div>
          )}
          {user && user.email_verified && (
            <button className="button button--primary form-submit" type="button" onClick={() => void acceptInvitation()} disabled={busy || !pendingToken}>
              {busy ? "Accepting…" : "Accept invitation"}
            </button>
          )}
          {!user && authForm}
          {user && <p className="form-hint">Signed in as {user.email}. If this is not the invited address, sign out and use the correct account.</p>}
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
          {user && <button className="text-button" type="button" onClick={() => void logout()} disabled={busy}>Sign out</button>}
        </div>
      </header>

      {user ? (
        <section className="workspace-page">
          <div className="workspace-heading">
            <div>
              <p className="eyebrow">YOUR EXPROFIT ACCOUNT</p>
              <h1 className="account-title">Your workspaces.</h1>
              <p className="hero-copy">Signed in as {user.email}. Each workspace keeps its own records and access rules.</p>
            </div>
            <span className={user.email_verified ? "status-pill status-pill--good" : "status-pill"}>{user.email_verified ? "Email verified" : "Email not verified"}</span>
          </div>

          {!user.email_verified && (
            <div className="verification-notice">
              <div><strong>Verify your email address</strong><p>Verified email is required before accepting business invitations.</p></div>
              <button className="button button--secondary" type="button" onClick={() => void requestVerification()} disabled={busy}>Send verification email</button>
            </div>
          )}
          {notice && <p className="form-message" role="status">{notice}</p>}

          <section className="workspace-picker">
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
          </section>

          <section className="create-workspace-card">
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
          </section>
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
