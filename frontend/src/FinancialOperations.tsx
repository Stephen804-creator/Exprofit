import { useEffect, useState, type FormEvent } from "react";

type Recurring = { id: string; direction: "income" | "expense"; description: string; category: string | null; amount: string; currency_code: string; interval: "weekly" | "monthly" | "yearly"; start_date: string; next_due_date: string; end_date: string | null; is_active: boolean };
type Forecast = { currency_code: string; average_daily_income: string; average_daily_expenses: string; baseline_projected_net_movement: string; scheduled_income: string; scheduled_expenses: string; forecast_net_movement_with_schedules: string; forecast_end: string };
type Alert = { id: string; kind: string; severity: string; title: string; message: string; status: string; created_at: string };
type Onboarding = { completed: number; total: number; percent: number; items: Array<{ key: string; title: string; complete: boolean; count: number }>; note: string };
type Copilot = { answer: string; provider: string; ai_status: string; evidence_count: number; disclaimer: string };
type SpeechAlternative = { transcript: string };
type SpeechResultEvent = { results: ArrayLike<ArrayLike<SpeechAlternative>> };
type BrowserSpeechRecognition = { lang: string; interimResults: boolean; maxAlternatives: number; onresult: ((event: SpeechResultEvent) => void) | null; onerror: (() => void) | null; onend: (() => void) | null; start: () => void };
type SpeechWindow = Window & { SpeechRecognition?: new () => BrowserSpeechRecognition; webkitSpeechRecognition?: new () => BrowserSpeechRecognition };
const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const today = () => { const d = new Date(); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); };
const monthStart = () => today().slice(0, 8) + "01";
const cash = (value: string, currency: string) => currency + " " + Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const errorText = (value: unknown) => value && typeof value === "object" && "detail" in value && typeof value.detail === "string" ? value.detail : "Request failed. Please try again.";

export default function FinancialOperations({ workspaceId, accessToken, currencyCode }: { workspaceId: string; accessToken: string; currencyCode: string }) {
  const [recurring, setRecurring] = useState<Recurring[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [onboarding, setOnboarding] = useState<Onboarding | null>(null);
  const [forecast, setForecast] = useState<Forecast[]>([]);
  const [scheduledItems, setScheduledItems] = useState<Array<{date:string;direction:string;amount:string;currency_code:string;description:string}>>([]);
  const [direction, setDirection] = useState<"income" | "expense">("expense");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [amount, setAmount] = useState("");
  const [interval, setInterval] = useState<"weekly" | "monthly" | "yearly">("monthly");
  const [startDate, setStartDate] = useState(today());
  const [nextDueDate, setNextDueDate] = useState(today());
  const [endDate, setEndDate] = useState("");
  const [forecastDays, setForecastDays] = useState("30");
  const [reportStart, setReportStart] = useState(monthStart());
  const [reportEnd, setReportEnd] = useState(today());
  const [question, setQuestion] = useState("");
  const [voiceListening, setVoiceListening] = useState(false);
  const [voiceError, setVoiceError] = useState("");
  const [useAi, setUseAi] = useState(false);
  const [copilot, setCopilot] = useState<Copilot | null>(null);
  const [accountantReport, setAccountantReport] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Authorization", "Bearer " + accessToken);
    if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBase + path, { ...init, headers });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(errorText(body));
    }
    return response.json() as Promise<T>;
  }
  async function refresh() {
    setError("");
    try {
      const [schedules, alertRows, progress] = await Promise.all([
        request<Recurring[]>("/businesses/" + workspaceId + "/recurring-transactions"),
        request<Alert[]>("/businesses/" + workspaceId + "/alerts"),
        request<Onboarding>("/businesses/" + workspaceId + "/onboarding"),
      ]);
      setRecurring(schedules); setAlerts(alertRows); setOnboarding(progress);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load financial operations."); }
  }
  useEffect(() => { void refresh(); }, [workspaceId, accessToken]);

  async function addRecurring(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      await request("/businesses/" + workspaceId + "/recurring-transactions", { method: "POST", body: JSON.stringify({
        direction, description, category: category || null, amount, currency_code: currencyCode, interval,
        start_date: startDate, next_due_date: nextDueDate, end_date: endDate || null,
      }) });
      setDescription(""); setCategory(""); setAmount(""); setNotice("Expected payment schedule saved. No ledger entry was created."); await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save schedule."); }
    finally { setBusy(false); }
  }
  async function toggleSchedule(item: Recurring) {
    setBusy(true); setError("");
    try {
      await request("/businesses/" + workspaceId + "/recurring-transactions/" + item.id, { method: "PATCH", body: JSON.stringify({ is_active: !item.is_active }) });
      setNotice(item.is_active ? "Schedule paused." : "Schedule resumed."); await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not update schedule."); }
    finally { setBusy(false); }
  }
  async function runForecast() {
    setBusy(true); setError("");
    try {
      const result = await request<{forecasts: Forecast[]; scheduled_items: typeof scheduledItems}>("/businesses/" + workspaceId + "/cash-flow-forecast?forecast_days=" + forecastDays);
      setForecast(result.forecasts); setScheduledItems(result.scheduled_items);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not calculate forecast."); }
    finally { setBusy(false); }
  }
  async function acknowledgeAlert(alert: Alert, status: "read" | "dismissed") {
    setError("");
    try {
      await request("/businesses/" + workspaceId + "/alerts/" + alert.id, { method: "PATCH", body: JSON.stringify({ status }) });
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not update alert."); }
  }
  async function downloadCsv() {
    setBusy(true); setError("");
    try {
      const response = await fetch(apiBase + "/businesses/" + workspaceId + "/transactions-export.csv?start_date=" + reportStart + "&end_date=" + reportEnd + "&status=posted", { headers: { Authorization: "Bearer " + accessToken } });
      if (!response.ok) throw new Error(errorText(await response.json().catch(() => ({}))));
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a"); link.href = url; link.download = "exprofit-transactions.csv"; link.click();
      URL.revokeObjectURL(url); setNotice("CSV export downloaded.");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not export transactions."); }
    finally { setBusy(false); }
  }
  async function loadAccountantReport() {
    setBusy(true); setError("");
    try {
      const data = await request<unknown>("/businesses/" + workspaceId + "/accountant-report?start_date=" + reportStart + "&end_date=" + reportEnd);
      setAccountantReport(data);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not prepare report."); }
    finally { setBusy(false); }
  }
  function downloadAccountantReport() {
    if (accountantReport === null) return;
    const blob = new Blob([JSON.stringify(accountantReport, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "exprofit-accountant-summary.json";
    link.click();
    URL.revokeObjectURL(url);
  }
  function startVoiceInput() {
    const speechWindow = window as SpeechWindow;
    const SpeechRecognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceError("Voice input is not supported in this browser. Type your question instead.");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = navigator.language || "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = event => {
      const transcript = event.results[0]?.[0]?.transcript?.trim();
      if (transcript) setQuestion(current => current.trim() ? current.trim() + " " + transcript : transcript);
    };
    recognition.onerror = () => setVoiceError("Microphone input failed. Check browser permission or type your question.");
    recognition.onend = () => setVoiceListening(false);
    setVoiceError("");
    setVoiceListening(true);
    try { recognition.start(); } catch {
      setVoiceListening(false);
      setVoiceError("Could not start voice input. Please type your question.");
    }
  }

  async function askCopilot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setCopilot(null);
    try {
      const data = await request<Copilot>("/businesses/" + workspaceId + "/financial-copilot", { method: "POST", body: JSON.stringify({ question, end_date: today(), period_days: 30, use_ai: useAi }) });
      setCopilot(data);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not answer this question."); }
    finally { setBusy(false); }
  }

  return <div className="finance-operations">
    <div className="finance-card">
      <p className="eyebrow">07 / PLAN AHEAD</p><h3>Recurring income and expenses</h3>
      <p className="finance-muted">Record expected payments separately from actual transactions. Exprofit will never post a scheduled payment to your ledger automatically.</p>
      <form onSubmit={addRecurring} className="finance-form">
        <label>Type<select value={direction} onChange={e => setDirection(e.target.value as "income" | "expense")}><option value="expense">Expected expense</option><option value="income">Expected income</option></select></label>
        <label>Description<input maxLength={160} required value={description} onChange={e => setDescription(e.target.value)} placeholder="Shop rent, customer retainer…" /></label>
        <label>Amount ({currencyCode})<input type="number" min="0.01" step="0.01" required value={amount} onChange={e => setAmount(e.target.value)} /></label>
        <label>Category (optional)<input maxLength={80} value={category} onChange={e => setCategory(e.target.value)} /></label>
        <label>Repeat<select value={interval} onChange={e => setInterval(e.target.value as typeof interval)}><option value="weekly">Weekly</option><option value="monthly">Monthly</option><option value="yearly">Yearly</option></select></label>
        <label>Schedule starts<input type="date" required value={startDate} onChange={e => setStartDate(e.target.value)} /></label>
        <label>Next due date<input type="date" required value={nextDueDate} onChange={e => setNextDueDate(e.target.value)} /></label>
        <label>End date (optional)<input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} /></label>
        <div className="finance-actions"><button className="finance-button" disabled={busy}>Save expected payment</button></div>
      </form>
      {recurring.length === 0 ? <p className="finance-empty">No recurring schedules yet.</p> : recurring.map(item => <article className="guard-finding" key={item.id}>
        <strong>{item.description}</strong><p>{item.direction} · {cash(item.amount, item.currency_code)} · {item.interval} · next due {item.next_due_date}{item.end_date ? " · ends " + item.end_date : ""}</p>
        <button type="button" className="finance-button finance-button--quiet" disabled={busy} onClick={() => void toggleSchedule(item)}>{item.is_active ? "Pause schedule" : "Resume schedule"}</button>
      </article>)}
    </div>

    <div className="finance-card">
      <p className="eyebrow">08 / FORECAST</p><h3>Cash-flow outlook</h3>
      <p className="finance-muted">Historical daily averages are projected forward; expected recurring payments are added separately. This is a planning estimate, not a guarantee.</p>
      <div className="finance-form"><label>Forecast horizon<select value={forecastDays} onChange={e => setForecastDays(e.target.value)}>{[7,14,30,60,90].map(n => <option key={n} value={n}>{n} days</option>)}</select></label><div className="finance-actions"><button className="finance-button" type="button" disabled={busy} onClick={() => void runForecast()}>Calculate forecast</button></div></div>
      {forecast.map(row => <article className="guard-finding" key={row.currency_code}><strong>{row.currency_code} forecast through {row.forecast_end}</strong><div className="evidence-row"><span>Average daily income / expenses</span><strong>{cash(row.average_daily_income,row.currency_code)} / {cash(row.average_daily_expenses,row.currency_code)}</strong></div><div className="evidence-row"><span>Baseline projected movement</span><strong>{cash(row.baseline_projected_net_movement,row.currency_code)}</strong></div><div className="evidence-row"><span>Scheduled income / expenses</span><strong>{cash(row.scheduled_income,row.currency_code)} / {cash(row.scheduled_expenses,row.currency_code)}</strong></div><div className="evidence-row"><span>Forecast net movement with schedules</span><strong>{cash(row.forecast_net_movement_with_schedules,row.currency_code)}</strong></div></article>)}
      {scheduledItems.length > 0 && <details><summary>Scheduled items ({scheduledItems.length})</summary>{scheduledItems.map((item,i)=><div className="evidence-row" key={item.date + item.description + i}><span>{item.date} · {item.description} · {item.direction}</span><strong>{cash(item.amount,item.currency_code)}</strong></div>)}</details>}
    </div>

    <div className="finance-card">
      <p className="eyebrow">09 / NOTIFICATIONS</p><h3>Financial alerts</h3>
      <p className="finance-muted">Alerts are based on saved budgets and upcoming expected payments. Acknowledging an alert does not confirm payment.</p>
      {alerts.length === 0 ? <p className="finance-empty">No active alerts.</p> : alerts.map(alert => <article className="guard-finding" key={alert.id}><span className={"finance-status finance-status--" + (alert.severity === "critical" ? "warning" : "posted")}>{alert.severity} · {alert.status}</span><strong>{alert.title}</strong><p>{alert.message}</p>{alert.status === "unread" && <div className="finance-actions"><button className="finance-button finance-button--quiet" type="button" onClick={() => void acknowledgeAlert(alert,"read")}>Mark read</button><button className="finance-button finance-button--quiet" type="button" onClick={() => void acknowledgeAlert(alert,"dismissed")}>Dismiss</button></div>}</article>)}
    </div>

    <div className="finance-card">
      <p className="eyebrow">10 / SHARE & RECONCILE</p><h3>Exports for your accountant</h3>
      <p className="finance-muted">Download posted transactions as CSV or review totals by currency/category. This is an export aid, not a tax filing or audited statement.</p>
      <div className="finance-form"><label>From<input type="date" value={reportStart} onChange={e => setReportStart(e.target.value)} /></label><label>To<input type="date" value={reportEnd} onChange={e => setReportEnd(e.target.value)} /></label></div>
      <div className="finance-actions"><button className="finance-button" type="button" disabled={busy} onClick={() => void downloadCsv()}>Download transaction CSV</button><button className="finance-button finance-button--quiet" type="button" disabled={busy} onClick={() => void loadAccountantReport()}>Build accountant summary</button></div>
      {accountantReport !== null && <><div className="finance-actions"><button className="finance-button finance-button--quiet" type="button" onClick={downloadAccountantReport}>Download accountant summary JSON</button></div><pre className="finance-report-json">{JSON.stringify(accountantReport,null,2)}</pre></>}
    </div>

    <div className="finance-card">
      <p className="eyebrow">11 / GET STARTED</p><h3>Workspace checklist</h3>
      {onboarding && <><p className="finance-muted">{onboarding.completed} of {onboarding.total} steps complete · {onboarding.percent}%</p><div className="finance-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={onboarding.percent}><span style={{width: onboarding.percent + "%"}} /></div>{onboarding.items.map(item => <div className="evidence-row" key={item.key}><span>{item.complete ? "✓" : "○"} {item.title}</span><strong>{item.complete ? "Complete" : "Suggested"}</strong></div>)}<p className="finance-muted">{onboarding.note}</p></>}
    </div>

    <div className="finance-card">
      <p className="eyebrow">12 / ASK EXPROFIT</p><h3>Financial copilot</h3>
      <p className="finance-muted">Ask a question about your last 30 days. The answer is grounded in posted transactions; optional AI receives only a bounded financial summary and your question.</p>
      <form onSubmit={askCopilot}><label className="finance-full">Your question<input maxLength={500} minLength={3} required value={question} onChange={e => setQuestion(e.target.value)} placeholder="What should I review in my expenses?" /></label><div className="finance-actions"><button className="finance-button finance-button--quiet" type="button" onClick={startVoiceInput} disabled={voiceListening} aria-label="Speak your financial question">{voiceListening ? "Listening…" : "🎙 Speak question"}</button></div>{voiceError && <p className="form-message form-message--error" role="status">{voiceError}</p>}<label className="finance-check"><input type="checkbox" checked={useAi} onChange={e => setUseAi(e.target.checked)} /> Use optional Hugging Face AI for an explanation</label><div className="finance-actions"><button className="finance-button" disabled={busy}>{busy ? "Thinking…" : "Ask financial copilot"}</button></div></form>
      {copilot && <article className="guard-finding"><p className="finance-muted">Provider: {copilot.provider} · AI status: {copilot.ai_status} · Evidence records: {copilot.evidence_count}</p><pre className="finance-report-json">{copilot.answer}</pre><p className="finance-muted">{copilot.disclaimer}</p></article>}
    </div>
    {error && <p className="form-message form-message--error" role="alert">{error}</p>}
    {notice && <p className="form-message" role="status">{notice}</p>}
  </div>;
}
