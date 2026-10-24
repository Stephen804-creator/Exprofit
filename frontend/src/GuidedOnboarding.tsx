import { useEffect, useState } from "react";

type SetupItem = { key: string; title: string; complete: boolean; count: number };
type SetupProgress = { completed: number; total: number; percent: number; items: SetupItem[]; note: string };
type Panel = "overview" | "transactions" | "receipts" | "insights" | "catalog" | "operations";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const destinations: Record<string, Panel> = {
  first_transaction: "transactions",
  receipt: "receipts",
  product: "catalog",
  budget: "catalog",
  recurring: "operations",
};

export default function GuidedOnboarding({ workspaceId, accessToken, onNavigate }: {
  workspaceId: string;
  accessToken: string;
  onNavigate: (panel: Panel) => void;
}) {
  const [progress, setProgress] = useState<SetupProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(() => localStorage.getItem("exprofit_setup_dismissed_" + workspaceId) === "true");
  const [error, setError] = useState("");

  useEffect(() => {
    setDismissed(localStorage.getItem("exprofit_setup_dismissed_" + workspaceId) === "true");
    setLoading(true);
    setError("");
    const controller = new AbortController();
    fetch(`${apiBase}/businesses/${workspaceId}/onboarding`, {
      headers: { Authorization: "Bearer " + accessToken },
      signal: controller.signal,
    }).then(async response => {
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Setup checklist is unavailable.");
      return body as SetupProgress;
    }).then(setProgress).catch(error => {
      if (!controller.signal.aborted) setError(error instanceof Error ? error.message : "Setup checklist is unavailable.");
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [workspaceId, accessToken]);

  function dismiss() {
    localStorage.setItem("exprofit_setup_dismissed_" + workspaceId, "true");
    setDismissed(true);
  }

  if (loading) return <section className="guided-setup guided-setup--loading" aria-label="Getting started"><p className="finance-muted">Preparing your setup checklist…</p></section>;
  if (error || !progress || progress.completed === progress.total) return null;
  if (dismissed) return <div className="guided-setup-resume"><span>Setup guide hidden · {progress.completed} of {progress.total} complete</span><button className="finance-link" type="button" onClick={() => { localStorage.removeItem("exprofit_setup_dismissed_" + workspaceId); setDismissed(false); }}>Show guide</button></div>;

  return <section className="guided-setup" aria-labelledby="guided-setup-title">
    <div className="guided-setup-heading">
      <div><p className="eyebrow">START HERE</p><h3 id="guided-setup-title">Set up your workspace</h3><p className="finance-muted">A few small steps help Exprofit give you more useful financial insights. You can skip any step.</p></div>
      <button className="finance-link" type="button" onClick={dismiss} aria-label="Hide setup guide">Hide</button>
    </div>
    <div className="guided-setup-progress"><div className="finance-progress" role="progressbar" aria-label="Workspace setup progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress.percent}><span style={{ width: progress.percent + "%" }} /></div><strong>{progress.completed}/{progress.total} complete · {progress.percent}%</strong></div>
    <div className="guided-setup-steps">{progress.items.map((item, index) => <article className={item.complete ? "guided-setup-step guided-setup-step--complete" : "guided-setup-step"} key={item.key}>
      <span className="guided-setup-number" aria-hidden="true">{item.complete ? "✓" : index + 1}</span>
      <div><strong>{item.title}</strong><small>{item.complete ? "Completed" : "Suggested next step"}</small></div>
      {!item.complete && <button className="finance-button finance-button--quiet" type="button" onClick={() => onNavigate(destinations[item.key] ?? "transactions")}>Start</button>}
    </article>)}</div>
    <p className="finance-footnote">{progress.note || "This guide is optional and does not block access to your workspace."}</p>
  </section>;
}
