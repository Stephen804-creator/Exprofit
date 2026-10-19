
import { useEffect, useState, type FormEvent } from "react";

type Workspace = { id: string; currency_code: string; workspace_type: "solo" | "business"; name: string; display_name: string | null };
type Tx = { id: string; direction: "income" | "expense"; status: "draft" | "posted" | "void"; amount: string; currency_code: string; transaction_date: string; description: string; category: string | null };
type Summary = { currencies: Array<{ currency_code: string; income: string; expenses: string; net_cash_movement: string; income_count: number; expense_count: number }>; profitability: { currencies: Array<{ currency_code: string; revenue: string; direct_costs: string; gross_profit: string | null; gross_margin_percent: string | null; note: string }> } };
type Finding = { kind: string; severity: string; currency_code: string; summary: string; uncertainty: string; evidence?: Array<{ id: string; date: string; direction: string; amount: string; description: string }> };
type Receipt = { id: string; original_filename: string; candidate_merchant: string | null; candidate_date: string | null; candidate_amount: string | null; extracted_text: string; review_status: string };
type MembershipAccess = { role: "owner" | "admin" | "worker"; permissions: Record<string, boolean> } | null;
const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const localDate = (date: Date) => date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, "0") + "-" + String(date.getDate()).padStart(2, "0");
const today = () => localDate(new Date());
const daysAgo = (n: number) => { const d = new Date(); d.setDate(d.getDate() - n); return localDate(d); };
const cash = (value: string, currency: string) => currency + " " + Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const errorText = (value: unknown) => value && typeof value === "object" && "detail" in value && typeof value.detail === "string" ? value.detail : "Request failed. Please try again.";

export default function FinancialWorkspace({ workspace, accessToken, membership, membershipResolved }: { workspace: Workspace; accessToken: string; membership: MembershipAccess; membershipResolved: boolean }) {
  const [rows, setRows] = useState<Tx[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [from, setFrom] = useState(daysAgo(29)); const [to, setTo] = useState(today());
  const [direction, setDirection] = useState<"income" | "expense">("expense");
  const [amount, setAmount] = useState(""); const [date, setDate] = useState(today());
  const [description, setDescription] = useState(""); const [category, setCategory] = useState("Uncategorised");
  const [editing, setEditing] = useState<Tx | null>(null);
  const [editAmount, setEditAmount] = useState(""); const [editDate, setEditDate] = useState("");
  const [editDescription, setEditDescription] = useState(""); const [editCategory, setEditCategory] = useState("");
  const [receiptFields, setReceiptFields] = useState<Record<string, { amount: string; date: string; description: string; category: string; direction: "income" | "expense" }>>({});
  const [busy, setBusy] = useState(false); const [loading, setLoading] = useState(true);
  const [error, setError] = useState(""); const [notice, setNotice] = useState("");

  function canRead(domain: "sales" | "expenses"): boolean {
    return workspace.workspace_type === "solo" || membership?.role === "owner" || membership?.permissions[`${domain}:read`] === true;
  }
  function canWrite(domain: "sales" | "expenses"): boolean {
    return workspace.workspace_type === "solo" || membership?.role === "owner" || membership?.permissions[`${domain}:write`] === true;
  }
  const canViewCombined = canRead("sales") && canRead("expenses");
  const canReadExpenses = canRead("expenses");
  const canWriteExpenses = canWrite("expenses");
  const canWriteAny = canWrite("sales") || canWrite("expenses");
  const writeDirections = (["expense", "income"] as const).filter((value) => canWrite(value === "income" ? "sales" : "expenses"));

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Authorization", "Bearer " + accessToken);
    if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBase + path, { ...init, headers });
    const body = response.status === 204 ? undefined : await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(errorText(body));
    return body as T;
  }
  async function refresh() {
    if (workspace.workspace_type === "business" && !membershipResolved) {
      setLoading(true);
      return;
    }
    if (workspace.workspace_type === "business" && !membership) {
      setRows([]); setSummary(null); setFindings([]); setReceipts([]);
      setError("Workspace access could not be verified. Reload the workspace and try again.");
      setLoading(false);
      return;
    }
    setLoading(true); setError("");
    const query = new URLSearchParams({ start_date: from, end_date: to }).toString();
    try {
      const txPromise = canRead("sales") || canRead("expenses")
        ? request<Tx[]>("/businesses/" + workspace.id + "/transactions?start_date=" + from + "&end_date=" + to + "&limit=100")
        : Promise.resolve([] as Tx[]);
      const totalsPromise = canViewCombined
        ? request<Summary>("/businesses/" + workspace.id + "/financial-summary?" + query)
        : Promise.resolve(null);
      const guardPromise = canViewCombined
        ? request<{ findings: Finding[] }>("/businesses/" + workspace.id + "/margin-guard?end_date=" + to + "&period_days=30")
        : Promise.resolve({ findings: [] as Finding[] });
      const receiptsPromise = canReadExpenses
        ? request<Receipt[]>("/businesses/" + workspace.id + "/receipts")
        : Promise.resolve([] as Receipt[]);
      const [tx, totals, guard, receiptRows] = await Promise.all([
        txPromise, totalsPromise, guardPromise, receiptsPromise
      ]);
      setRows(tx); setSummary(totals); setFindings(guard.findings); setReceipts(receiptRows);
      setReceiptFields(old => {
        const next = { ...old };
        receiptRows.forEach(r => { if (!next[r.id]) next[r.id] = { amount: r.candidate_amount ?? "", date: r.candidate_date ?? today(), description: r.candidate_merchant ?? r.original_filename, category: "Uncategorised", direction: "expense" }; });
        return next;
      });
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load financial records."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void refresh(); }, [workspace.id, accessToken, from, to, membershipResolved, membership]);
  useEffect(() => {
    if (writeDirections.length > 0 && !writeDirections.includes(direction)) setDirection(writeDirections[0]);
  }, [workspace.id, membership, membershipResolved, direction]);

  async function addTransaction(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      await request("/businesses/" + workspace.id + "/transactions", { method: "POST", body: JSON.stringify({
        business_id: workspace.id, direction, amount, currency_code: workspace.currency_code, transaction_date: date,
        description, category: category || null, status: "posted"
      }) });
      setAmount(""); setDescription(""); setNotice("Transaction saved."); await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save transaction."); }
    finally { setBusy(false); }
  }
  function startEdit(tx: Tx) { setEditing(tx); setEditAmount(tx.amount); setEditDate(tx.transaction_date); setEditDescription(tx.description); setEditCategory(tx.category ?? ""); }
  async function saveEdit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (!editing) return; setBusy(true); setError("");
    try {
      await request("/businesses/" + workspace.id + "/transactions/" + editing.id, { method: "PATCH", body: JSON.stringify({ amount: editAmount, transaction_date: editDate, description: editDescription, category: editCategory || null }) });
      setEditing(null); setNotice("Transaction updated."); await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not update transaction."); }
    finally { setBusy(false); }
  }
  async function voidTx(tx: Tx) {
    if (!window.confirm("Void this transaction? It remains in history and is excluded from totals.")) return;
    setBusy(true); setError("");
    try { await request("/businesses/" + workspace.id + "/transactions/" + tx.id + "/void", { method: "POST" }); setNotice("Transaction voided."); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not void transaction."); }
    finally { setBusy(false); }
  }
  async function uploadReceipt(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const form = e.currentTarget; const file = (form.elements.namedItem("receipt-file") as HTMLInputElement).files?.[0]; if (!file) return;
    setBusy(true); setError("");
    try { const body = new FormData(); body.append("file", file); await request("/businesses/" + workspace.id + "/receipts", { method: "POST", body }); form.reset(); setNotice("Receipt uploaded. Review all extracted fields before saving."); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Receipt upload failed."); }
    finally { setBusy(false); }
  }
  async function confirmReceipt(r: Receipt) {
    const fields = receiptFields[r.id]; if (!fields || !fields.amount || !fields.date || !fields.description.trim()) { setError("Review amount, date and description first."); return; }
    setBusy(true); setError("");
    try {
      await request("/businesses/" + workspace.id + "/receipts/" + r.id + "/confirm", { method: "POST", body: JSON.stringify({ ...fields, transaction_date: fields.date, description: fields.description.trim(), category: fields.category || null }) });
      setNotice("Reviewed receipt and created transaction."); await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not confirm receipt."); }
    finally { setBusy(false); }
  }
  async function rejectReceipt(r: Receipt) {
    if (!window.confirm("Reject this receipt and delete its stored file?")) return;
    setBusy(true);
    try { await request("/businesses/" + workspace.id + "/receipts/" + r.id + "/reject", { method: "POST" }); setNotice("Receipt rejected and file deleted."); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not reject receipt."); }
    finally { setBusy(false); }
  }

  if (workspace.workspace_type === "business" && !membershipResolved) {
    return <section className="finance-workspace"><p className="form-hint">Checking workspace permissions…</p></section>;
  }
  if (workspace.workspace_type === "business" && !membership) {
    return <section className="finance-workspace"><p className="form-message form-message--error" role="alert">Workspace access could not be verified. Reload and try again.</p></section>;
  }

  return <section className="finance-workspace">
    <div className="finance-heading"><div><p className="eyebrow">FINANCIAL WORKSPACE</p><h2>Records and margin signals</h2><p className="finance-muted">Only posted records contribute to totals. Workspace records stay separate.</p></div><span className="finance-currency">{workspace.currency_code}</span></div>
    <div className="finance-filters"><label>From<input type="date" value={from} max={to} onChange={e => setFrom(e.target.value)} /></label><label>To<input type="date" value={to} min={from} max={today()} onChange={e => setTo(e.target.value)} /></label><button className="finance-button finance-button--quiet" type="button" onClick={() => { setFrom(daysAgo(29)); setTo(today()); }}>Last 30 days</button></div>
    {error && <p className="form-message form-message--error" role="alert">{error}</p>}{notice && <p className="form-message" role="status">{notice}</p>}{loading && <p className="form-hint">Loading financial records…</p>}
    <div className="finance-metrics">{(summary?.currencies ?? []).map(s => <div className="finance-metric-grid" key={s.currency_code}>
      <article className="finance-metric"><span>Recorded income</span><strong>{cash(s.income, s.currency_code)}</strong><small>{s.income_count} entries</small></article>
      <article className="finance-metric"><span>Recorded expenses</span><strong>{cash(s.expenses, s.currency_code)}</strong><small>{s.expense_count} entries</small></article>
      <article className="finance-metric"><span>Net cash movement</span><strong>{cash(s.net_cash_movement, s.currency_code)}</strong><small>Not the same as profit</small></article>
    </div>)}{!loading && canViewCombined && !summary?.currencies.length && <p className="finance-empty">No posted transactions in this period. Add one below.</p>}
     {!canViewCombined && <p className="finance-footnote">Combined summaries and MarginGuard require read access to both sales and expenses.</p>}</div>
    <div className="finance-columns">
      {writeDirections.length > 0 && <section className="finance-card"><p className="eyebrow">01 / TRACK</p><h3>Add a transaction</h3>
        <form className="finance-form" onSubmit={addTransaction}>
          <label>Type<select value={direction} onChange={e => setDirection(e.target.value as "income" | "expense")}>{canWrite("expenses") && <option value="expense">Expense</option>}{canWrite("sales") && <option value="income">Income / sale</option>}</select></label>
          <label>Amount ({workspace.currency_code})<input type="number" min="0.01" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} required /></label>
          <label>Date<input type="date" value={date} max={today()} onChange={e => setDate(e.target.value)} required /></label>
          <label>Category<select value={category} onChange={e => setCategory(e.target.value)}>{["Uncategorised","Sales","COGS","Cost of goods sold","Cost of sales","Direct costs","Inventory cost","Rent","Transport","Utilities","Marketing","Equipment","Other"].map(c => <option key={c}>{c}</option>)}</select></label>
          <label className="finance-full">Description<input value={description} onChange={e => setDescription(e.target.value)} maxLength={500} required /></label>
          <button className="finance-button" disabled={busy}>{busy ? "Saving…" : "Save transaction"}</button>
        </form><p className="finance-footnote">Voiding preserves history. Amounts use decimal storage.</p>
      </section>}
      {canReadExpenses && <section className="finance-card"><p className="eyebrow">02 / CAPTURE</p><h3>Scan a receipt</h3><p className="finance-muted">JPEG, PNG, WebP or PDF up to 5 MB. Confirm every field before saving.</p>
        {canWriteExpenses && <form className="finance-upload" onSubmit={uploadReceipt}><input name="receipt-file" type="file" accept="image/jpeg,image/png,image/webp,application/pdf" required /><button className="finance-button" disabled={busy}>Upload and extract</button></form>}
        <p className="finance-footnote">Files are private to this workspace. OCR is best-effort; enter details manually if text extraction is unavailable.</p>
        {receipts.filter(r => r.review_status === "pending").map(r => {
          const f = receiptFields[r.id] ?? { amount: r.candidate_amount ?? "", date: r.candidate_date ?? today(), description: r.candidate_merchant ?? r.original_filename, category: "Uncategorised", direction: "expense" as const };
          const change = (patch: Partial<typeof f>) => setReceiptFields(old => ({ ...old, [r.id]: { ...f, ...patch } }));
          return <article className="receipt-review" key={r.id}><strong>{r.original_filename} — needs review</strong>
            {r.extracted_text ? <details><summary>View extracted text</summary><pre>{r.extracted_text}</pre></details> : <p className="finance-muted">No text extracted; complete fields manually.</p>}
            <div className="finance-form"><label>Type<select disabled={!canWriteAny} value={f.direction} onChange={e => change({ direction: e.target.value as "income" | "expense" })}>{canWrite("expenses") && <option value="expense">Expense</option>}{canWrite("sales") && <option value="income">Income</option>}</select></label>
              <label>Amount<input disabled={!canWriteAny} type="number" min="0.01" step="0.01" value={f.amount} onChange={e => change({ amount: e.target.value })} required /></label>
              <label>Date<input disabled={!canWriteAny} type="date" value={f.date} onChange={e => change({ date: e.target.value })} required /></label>
              <label>Category<input disabled={!canWriteAny} value={f.category} onChange={e => change({ category: e.target.value })} /></label>
              <label className="finance-full">Merchant / description<input disabled={!canWriteAny} value={f.description} onChange={e => change({ description: e.target.value })} required /></label></div>
            <div className="finance-actions">{canWrite(f.direction === "income" ? "sales" : "expenses") && <button className="finance-button" type="button" disabled={busy} onClick={() => void confirmReceipt(r)}>Confirm and save</button>}{canWriteExpenses && <button className="finance-button finance-button--quiet" type="button" disabled={busy} onClick={() => void rejectReceipt(r)}>Reject and delete file</button>}</div>
          </article>;
        })}
      </section>}
    </div>
    <section className="finance-card finance-records"><div className="finance-card-heading"><div><p className="eyebrow">03 / LEDGER</p><h3>Transactions</h3></div><span className="finance-muted">{rows.length} records</span></div>
      {!rows.length && (canRead("sales") || canRead("expenses")) && <p className="finance-empty">No transactions in this date range.</p>}
      {!rows.length && !canRead("sales") && !canRead("expenses") && <p className="finance-empty">You do not have read access to sales or expenses in this workspace.</p>}
      <div className="finance-table-wrap"><table className="finance-table"><thead><tr><th>Date</th><th>Details</th><th>Category</th><th>Amount</th><th>Status</th><th>Actions</th></tr></thead><tbody>
        {rows.map(tx => <tr key={tx.id} className={tx.status === "void" ? "finance-row--void" : ""}><td>{tx.transaction_date}</td><td><strong>{tx.description}</strong><small>{tx.direction}</small></td><td>{tx.category ?? "Uncategorised"}</td><td>{tx.direction === "expense" ? "−" : "+"}{cash(tx.amount, tx.currency_code)}</td><td><span className={"finance-status finance-status--" + tx.status}>{tx.status}</span></td>
          <td>{tx.status !== "void" && canWrite(tx.direction === "income" ? "sales" : "expenses") && <div className="finance-actions"><button className="finance-link" type="button" onClick={() => startEdit(tx)}>Edit</button><button className="finance-link finance-link--danger" type="button" onClick={() => void voidTx(tx)} disabled={busy}>Void</button></div>}</td></tr>)}
      </tbody></table></div>
      {editing && <form className="finance-edit" onSubmit={saveEdit}><h3>Edit transaction</h3><label>Amount<input type="number" min="0.01" step="0.01" value={editAmount} onChange={e => setEditAmount(e.target.value)} required /></label><label>Date<input type="date" value={editDate} onChange={e => setEditDate(e.target.value)} required /></label><label>Description<input value={editDescription} onChange={e => setEditDescription(e.target.value)} required /></label><label>Category<input value={editCategory} onChange={e => setEditCategory(e.target.value)} /></label><div className="finance-actions"><button className="finance-button" disabled={busy}>Save changes</button><button className="finance-button finance-button--quiet" type="button" onClick={() => setEditing(null)}>Cancel</button></div></form>}
    </section>
    {canViewCombined && <div className="finance-columns finance-bottom"><section className="finance-card"><p className="eyebrow">04 / CALCULATE</p><h3>Profitability — where supported</h3>
      {(summary?.profitability.currencies ?? []).map(p => <div className="profitability-row" key={p.currency_code}><div><span>Revenue</span><strong>{cash(p.revenue, p.currency_code)}</strong></div><div><span>Recognised direct costs</span><strong>{cash(p.direct_costs, p.currency_code)}</strong></div><div><span>Gross profit</span><strong>{p.gross_profit === null ? "Not available" : cash(p.gross_profit, p.currency_code)}</strong></div><div><span>Gross margin</span><strong>{p.gross_margin_percent === null ? "Not available" : p.gross_margin_percent + "%"}</strong></div><p className="finance-footnote">{p.note} General expenses are not automatically treated as direct costs.</p></div>)}
      {!summary?.profitability.currencies.length && <p className="finance-empty">Add posted income and direct costs to calculate gross profit.</p>}
    </section><section className="finance-card"><p className="eyebrow">05 / INVESTIGATE</p><h3>MarginGuard</h3><p className="finance-muted">Latest 30 days compared with the preceding 30 days. Changes are not proof of cause.</p>
      {!findings.length && <p className="finance-empty">No comparable changes detected, or not enough history yet.</p>}
      {findings.map((f, i) => <article className="guard-finding" key={f.kind + f.currency_code + i}><span className={"finance-status finance-status--" + (f.severity === "warning" ? "warning" : "posted")}>{f.severity}</span><strong>{f.summary}</strong><p>{f.uncertainty}</p><details><summary>Evidence ({f.evidence?.length ?? 0} records)</summary>{(f.evidence ?? []).map(ev => <div className="evidence-row" key={ev.id}><span>{ev.date} · {ev.description}</span><strong>{ev.direction} {cash(ev.amount, f.currency_code)}</strong></div>)}</details></article>)}
    </section></div>}
    <p className="finance-disclaimer">Exprofit reports recorded information only. Cash movement is not profit. Check source records before making a business decision.</p>
  </section>;
}
