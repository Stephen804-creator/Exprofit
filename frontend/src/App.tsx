import { useEffect, useState } from "react";

type ApiStatus = "checking" | "online" | "offline";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");

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

  const statusLabel: Record<ApiStatus, string> = {
    checking: "Checking API",
    online: "API connected",
    offline: "API not connected"
  };

  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Exprofit home">
          <span className="brand-mark" aria-hidden="true">e</span>
          <span>exprofit</span>
        </a>
        <span className={`connection connection--${apiStatus}`}>
          <span className="connection-dot" aria-hidden="true" />
          {statusLabel[apiStatus]}
        </span>
      </header>

      <section className="hero">
        <p className="eyebrow">YOUR BUSINESS, IN CLEARER FOCUS</p>
        <h1>Know where your money goes.<br /><em>Understand what you keep.</em></h1>
        <p className="hero-copy">
          A practical home for your business records, receipts, and profit questions.
          Built to show the evidence behind the numbers—not just another dashboard.
        </p>
        <div className="hero-actions">
          <a className="button button--primary" href="#workflow">Explore the workflow <span aria-hidden="true">↘</span></a>
          <span className="quiet-note">Early development · Your records stay yours</span>
        </div>
      </section>

      <section id="workflow" className="workflow">
        <div className="section-heading">
          <div>
            <p className="eyebrow">THE EXPROFIT WORKFLOW</p>
            <h2>From records to better questions.</h2>
          </div>
          <p>Start with what you know. Investigate what you don't.</p>
        </div>

        <div className="feature-grid">
          <article className="feature-card feature-card--featured">
            <span className="card-number">01 / RECORD</span>
            <div className="feature-icon" aria-hidden="true">↗</div>
            <h3>Track money in and out</h3>
            <p>Keep income, expenses, and categories in one place, with clear dates and currencies.</p>
            <span className="card-status">CORE FOUNDATION</span>
          </article>
          <article className="feature-card">
            <span className="card-number">02 / CAPTURE</span>
            <div className="feature-icon" aria-hidden="true">▤</div>
            <h3>Bring receipts into focus</h3>
            <p>Extract useful details, review them yourself, and correct mistakes before saving.</p>
            <span className="card-status">PLANNED</span>
          </article>
          <article className="feature-card">
            <span className="card-number">03 / INVESTIGATE</span>
            <div className="feature-icon" aria-hidden="true">⌁</div>
            <h3>Follow the margin</h3>
            <p>Inspect the figures and records behind a change instead of guessing at its cause.</p>
            <span className="card-status">PLANNED</span>
          </article>
        </div>
      </section>

      <section className="principle-strip">
        <span className="principle-symbol" aria-hidden="true">✳</span>
        <div>
          <p className="eyebrow">A NON-NEGOTIABLE PRINCIPLE</p>
          <p className="principle-copy">AI can explain the numbers. <strong>It cannot make them up.</strong></p>
        </div>
        <p className="principle-detail">Calculations stay deterministic. Missing costs and estimates stay visible.</p>
      </section>

      <footer className="footer">
        <a className="brand brand--footer" href="/"> <span className="brand-mark" aria-hidden="true">e</span> exprofit </a>
        <span>Built for the people building small businesses.</span>
        <span>v0.1 · Foundation</span>
      </footer>
    </main>
  );
}
