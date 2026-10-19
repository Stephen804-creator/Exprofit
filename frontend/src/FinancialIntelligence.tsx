import { useState, type FormEvent } from "react";

type Brief = {
  brief: string;
  provider: string;
  ai_status: string;
  ai_is_authoritative: boolean;
  disclaimer: string;
  findings: Array<{ kind: string; severity: string; currency_code: string; summary: string; uncertainty: string }>;
};
type Scenario = {
  results: Array<{
    currency_code: string;
    baseline_revenue: string;
    baseline_direct_costs: string;
    baseline_gross_profit: string | null;
    estimated_revenue: string;
    estimated_direct_costs: string;
    estimated_gross_profit: string | null;
    estimated_gross_margin_percent: string | null;
    direct_cost_data_available: boolean;
  }>;
  assumptions: string[];
  disclaimer: string;
  persisted: boolean;
};
const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const today = () => {
  const d = new Date();
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
};
const money = (value: string | null, currency: string) => value === null ? "Not available" : currency + " " + Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function FinancialIntelligence({ workspaceId, accessToken }: { workspaceId: string; accessToken: string }) {
  const [endDate, setEndDate] = useState(today());
  const [periodDays, setPeriodDays] = useState("30");
  const [question, setQuestion] = useState("");
  const [useAi, setUseAi] = useState(false);
  const [price, setPrice] = useState("0");
  const [volume, setVolume] = useState("0");
  const [cost, setCost] = useState("0");
  const [brief, setBrief] = useState<Brief | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function post<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(apiBase + "/businesses/" + workspaceId + path, {
      method: "POST",
      headers: { "Authorization": "Bearer " + accessToken, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = data && typeof data.detail === "string" ? data.detail : "Request failed. Please try again.";
      throw new Error(message);
    }
    return data as T;
  }

  async function generateBrief(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const result = await post<Brief>("/financial-brief", {
        end_date: endDate, period_days: Number(periodDays), question: question || null, use_ai: useAi,
      });
      setBrief(result);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create the financial brief."); }
    finally { setBusy(false); }
  }

  async function runScenario(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const result = await post<Scenario>("/what-if", {
        end_date: endDate, period_days: Number(periodDays),
        price_change_percent: price, volume_change_percent: volume, unit_cost_change_percent: cost,
      });
      setScenario(result);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not calculate this scenario."); }
    finally { setBusy(false); }
  }

  return <section className="finance-card">
    <p className="eyebrow">06 / PLAN & EXPLAIN</p>
    <h3>Financial brief and what-if simulator</h3>
    <p className="finance-muted">Use recorded totals to investigate changes or explore hypothetical assumptions. These tools do not edit your ledger.</p>
    <div className="finance-form">
      <label>Period end date<input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} /></label>
      <label>Period length<select value={periodDays} onChange={e => setPeriodDays(e.target.value)}>{[7, 14, 30, 60, 90, 180].map(n => <option key={n} value={n}>{n} days</option>)}</select></label>
    </div>
    <form onSubmit={generateBrief}>
      <label className="finance-full">What would you like explained? (optional)<input maxLength={300} value={question} onChange={e => setQuestion(e.target.value)} placeholder="Explain the biggest recorded change" /></label>
      <label className="finance-check"><input type="checkbox" checked={useAi} onChange={e => setUseAi(e.target.checked)} /> Use optional Gemma AI via Hugging Face. A limited structured summary and this question will be sent to the provider.</label>
      <div className="finance-actions"><button className="finance-button" disabled={busy}>{busy ? "Working…" : "Generate financial brief"}</button></div>
    </form>
    {brief && <article className="guard-finding">
      <strong>Financial brief</strong><p className="finance-muted">Source: {brief.provider} · AI status: {brief.ai_status}</p>
      <pre className="finance-brief-text">{brief.brief}</pre>
      <p>{brief.disclaimer}</p>
      {brief.findings.length > 0 && <details><summary>Underlying findings ({brief.findings.length})</summary>{brief.findings.map((f, i) => <p key={f.kind + f.currency_code + i}><strong>{f.currency_code} · {f.summary}</strong><br />{f.uncertainty}</p>)}</details>}
    </article>}
    <hr />
    <h4>What if my assumptions change?</h4>
    <form onSubmit={runScenario}>
      <div className="finance-form">
        <label>Price change (%)<input type="number" min="-90" max="300" step="0.1" value={price} onChange={e => setPrice(e.target.value)} required /></label>
        <label>Sales volume change (%)<input type="number" min="-90" max="300" step="0.1" value={volume} onChange={e => setVolume(e.target.value)} required /></label>
        <label>Direct unit cost change (%)<input type="number" min="-90" max="300" step="0.1" value={cost} onChange={e => setCost(e.target.value)} required /></label>
      </div>
      <div className="finance-actions"><button className="finance-button finance-button--quiet" disabled={busy}>{busy ? "Working…" : "Calculate what-if scenario"}</button></div>
    </form>
    {scenario && <article className="guard-finding"><strong>Hypothetical results</strong>
      {scenario.results.map(row => <div key={row.currency_code} className="profitability-row">
        <div><span>Currency</span><strong>{row.currency_code}</strong></div>
        <div><span>Revenue</span><strong>{money(row.baseline_revenue, row.currency_code)} → {money(row.estimated_revenue, row.currency_code)}</strong></div>
        <div><span>Direct costs</span><strong>{money(row.baseline_direct_costs, row.currency_code)} → {money(row.estimated_direct_costs, row.currency_code)}</strong></div>
        <div><span>Gross profit</span><strong>{money(row.baseline_gross_profit, row.currency_code)} → {money(row.estimated_gross_profit, row.currency_code)}</strong></div>
        <div><span>Estimated gross margin</span><strong>{row.estimated_gross_margin_percent === null ? "Not available" : row.estimated_gross_margin_percent + "%"}</strong></div>
        {!row.direct_cost_data_available && <p className="finance-footnote">Gross profit remains unavailable because recognised direct-cost data is missing.</p>}
      </div>)}
      {!scenario.results.length && <p className="finance-empty">No posted transactions in this period.</p>}
      <details><summary>Scenario assumptions</summary><ul>{scenario.assumptions.map(item => <li key={item}>{item}</li>)}</ul></details>
      <p>{scenario.disclaimer} Persisted to ledger: {scenario.persisted ? "yes" : "no"}.</p>
    </article>}
    {error && <p role="alert" className="finance-error">{error}</p>}
  </section>;
}
