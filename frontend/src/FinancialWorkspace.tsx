
import { useEffect, useState, type FormEvent } from "react";
import FinancialIntelligence from "./FinancialIntelligence";
import FinancialCatalogBudget from "./FinancialCatalogBudget";
import FinancialOperations from "./FinancialOperations";
import GuidedOnboarding from "./GuidedOnboarding";

type Workspace = { id: string; currency_code: string; workspace_type: "solo" | "business"; name: string; display_name: string | null };
type Tx = { id: string; direction: "income" | "expense"; status: "draft" | "posted" | "void"; amount: string; currency_code: string; transaction_date: string; description: string; category: string | null; product_id?: string | null; customer_id?: string | null };
type CatalogOption = { id: string; name: string };
type Summary = { currencies: Array<{ currency_code: string; income: string; expenses: string; net_cash_movement: string; income_count: number; expense_count: number }>; profitability: { currencies: Array<{ currency_code: string; revenue: string; direct_costs: string; gross_profit: string | null; gross_margin_percent: string | null; note: string }> } };
type Finding = { kind: string; severity: string; currency_code: string; summary: string; uncertainty: string; change?: string; current?: Record<string, string | number | boolean | null> | null; previous?: Record<string, string | number | boolean | null> | null; evidence?: Array<{ id: string; date: string; direction: string; amount: string; description: string }> };
type RecurringTemplate = { id: string; direction: "income" | "expense"; description: string; category: string | null; amount: string; currency_code: string; interval: "weekly" | "monthly" | "yearly"; next_due_date: string; is_active: boolean };
type Receipt = { id: string; original_filename: string; candidate_merchant: string | null; candidate_date: string | null; candidate_amount: string | null; extracted_text: string; review_status: string };
type MembershipAccess = { role: "owner" | "admin" | "worker"; permissions: Record<string, boolean> } | null;
const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const localDate = (date: Date) => date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, "0") + "-" + String(date.getDate()).padStart(2, "0");
const today = () => localDate(new Date());
const daysAgo = (n: number) => { const d = new Date(); d.setDate(d.getDate() - n); return localDate(d); };
const cash = (value: string, currency: string) => currency + " " + Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const errorText = (value: unknown) => {
  if (value && typeof value === "object" && "detail" in value) {
    const detail = value.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") return detail.message;
  }
  return "Request failed. Please try again.";
};

export default function FinancialWorkspace({ workspace, accessToken, membership, membershipResolved }: { workspace: Workspace; accessToken: string; membership: MembershipAccess; membershipResolved: boolean }) {
  const [activePanel, setActivePanel] = useState<"overview" | "transactions" | "receipts" | "insights" | "catalog" | "operations">("overview");
  const [rows, setRows] = useState<Tx[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [products, setProducts] = useState<CatalogOption[]>([]);
  const [recurringTemplates, setRecurringTemplates] = useState<RecurringTemplate[]>([]);
  const [selectedRecurringId, setSelectedRecurringId] = useState("");
  const [transactionStatus, setTransactionStatus] = useState<"draft" | "posted">("posted");
  const [selectedReceiptFile, setSelectedReceiptFile] = useState<File | null>(null);
  const [receiptDragActive, setReceiptDragActive] = useState(false);
  const [customers, setCustomers] = useState<CatalogOption[]>([]);
  const [selectedProductId, setSelectedProductId] = useState("");
  const [selectedCustomerId, setSelectedCustomerId] = useState("");
  const [from, setFrom] = useState(daysAgo(29)); const [to, setTo] = useState(today());
  const [transactionSearch, setTransactionSearch] = useState("");
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

  const overviewProfit = summary?.profitability.currencies.find((item) => item.currency_code === workspace.currency_code);
  const postedRows = rows.filter((tx) => tx.status === "posted" && tx.currency_code === workspace.currency_code);
  const normalizedTransactionSearch = transactionSearch.trim().toLocaleLowerCase();
  const visibleTransactions = rows.filter((tx) => !normalizedTransactionSearch || [tx.description, tx.category ?? "", tx.direction, tx.status, tx.transaction_date, tx.amount, tx.currency_code].some((value) => value.toLocaleLowerCase().includes(normalizedTransactionSearch)));
  const expenseCategories = Object.entries(postedRows.filter((tx) => tx.direction === "expense").reduce<Record<string, number>>((totals, tx) => {
    const key = tx.category?.trim() || "Uncategorised";
    totals[key] = (totals[key] ?? 0) + Number(tx.amount);
    return totals;
  }, {})).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const maxCategoryExpense = Math.max(1, ...expenseCategories.map(([, amount]) => amount));
  const trendDays = Array.from({ length: 7 }, (_, index) => {
    const day = new Date(to + "T12:00:00");
    day.setDate(day.getDate() - (6 - index));
    return localDate(day);
  }).filter((day) => day >= from);
  const cashTrend = trendDays.map((day) => ({
    day,
    label: new Date(day + "T12:00:00").toLocaleDateString(undefined, { weekday: "short" }),
    income: postedRows.filter((tx) => tx.direction === "income" && tx.transaction_date === day).reduce((sum, tx) => sum + Number(tx.amount), 0),
    expenses: postedRows.filter((tx) => tx.direction === "expense" && tx.transaction_date === day).reduce((sum, tx) => sum + Number(tx.amount), 0),
  }));
  const maxDailyAmount = Math.max(1, ...cashTrend.flatMap((day) => [day.income, day.expenses]));

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
      const recurringPromise = canViewCombined
        ? request<RecurringTemplate[]>("/businesses/" + workspace.id + "/recurring-transactions")
        : Promise.resolve([] as RecurringTemplate[]);
      const [tx, totals, guard, receiptRows, recurringRows] = await Promise.all([
        txPromise, totalsPromise, guardPromise, receiptsPromise, recurringPromise
      ]);
      setRows(tx); setSummary(totals); setFindings(guard.findings); setReceipts(receiptRows); setRecurringTemplates(recurringRows);
      if (canRead("sales")) {
        const [productRows, customerRows] = await Promise.all([
          request<CatalogOption[]>("/businesses/" + workspace.id + "/products"),
          request<CatalogOption[]>("/businesses/" + workspace.id + "/customers"),
        ]);
        setProducts(productRows); setCustomers(customerRows);
      } else { setProducts([]); setCustomers([]); }
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
        description, category: category || null, product_id: selectedProductId || null, customer_id: selectedCustomerId || null, status: transactionStatus
      }) });
      setAmount(""); setDescription(""); setSelectedProductId(""); setSelectedCustomerId(""); setSelectedRecurringId(""); setTransactionStatus("posted"); setNotice(transactionStatus === "draft" ? "Transaction saved as a draft. It is excluded from financial totals until posted." : "Transaction posted."); await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save transaction."); }
    finally { setBusy(false); }
  }
  function duplicateTransaction(tx: Tx) {
    setDirection(tx.direction); setAmount(tx.amount); setDate(today()); setDescription(tx.description); setCategory(tx.category ?? "Uncategorised");
    setSelectedProductId(tx.product_id ?? ""); setSelectedCustomerId(tx.customer_id ?? ""); setSelectedRecurringId(""); setTransactionStatus("draft"); setActivePanel("transactions");
    setNotice("Transaction copied into the form as a draft. Check the date and amount before saving.");
    window.setTimeout(() => document.getElementById("transaction-entry-title")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  }
  function applyRecurringTemplate(id: string) {
    setSelectedRecurringId(id);
    const template = recurringTemplates.find(item => item.id === id);
    if (!template) return;
    setDirection(template.direction); setAmount(template.amount); setDescription(template.description); setCategory(template.category ?? "Uncategorised"); setDate(today()); setTransactionStatus("draft");
    setNotice("Recurring payment details copied as a draft. This does not mark the expected payment as paid.");
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
  async function postDraft(tx: Tx) {
    if (tx.status !== "draft") return;
    setBusy(true); setError(""); setNotice("");
    try {
      await request("/businesses/" + workspace.id + "/transactions/" + tx.id + "/post", { method: "POST" });
      setNotice("Draft reviewed and posted. It is now included in financial totals.");
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not post this draft."); }
    finally { setBusy(false); }
  }
  async function voidTx(tx: Tx) {
    if (!window.confirm("Void this transaction? It remains in history and is excluded from totals.")) return;
    setBusy(true); setError("");
    try { await request("/businesses/" + workspace.id + "/transactions/" + tx.id + "/void", { method: "POST" }); setNotice("Transaction voided."); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not void transaction."); }
    finally { setBusy(false); }
  }
  async function importTransactionsCsv(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const file = (form.elements.namedItem("transaction-csv") as HTMLInputElement).files?.[0];
    if (!file) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const body = new FormData(); body.append("file", file);
      const result = await request<{ created_count: number }>("/businesses/" + workspace.id + "/transactions/import", { method: "POST", body });
      form.reset(); setNotice(`${result.created_count} transactions imported as drafts. Review them before posting.`); await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "CSV import failed."); }
    finally { setBusy(false); }
  }

  function chooseReceiptFile(file: File | null) {
    if (!file) { setSelectedReceiptFile(null); return; }
    const allowed = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
    if (!allowed.includes(file.type)) { setError("Choose a JPEG, PNG, WebP image, or PDF receipt."); return; }
    if (file.size > 5 * 1024 * 1024) { setError("Receipt files must be 5 MB or smaller."); return; }
    setError(""); setSelectedReceiptFile(file);
  }
  async function uploadReceipt(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const form = e.currentTarget; const inputFile = (form.elements.namedItem("receipt-file") as HTMLInputElement).files?.[0]; const file = selectedReceiptFile ?? inputFile; if (!file) { setError("Choose or drop a receipt file first."); return; }
    if (file.size > 5 * 1024 * 1024) { setError("Receipt files must be 5 MB or smaller."); return; }
    setBusy(true); setError("");
    try { const body = new FormData(); body.append("file", file); await request("/businesses/" + workspace.id + "/receipts", { method: "POST", body }); form.reset(); setSelectedReceiptFile(null); setNotice("Receipt uploaded. Review all extracted fields before saving."); await refresh(); }
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
    <div className="finance-heading"><div><p className="eyebrow">FINANCIAL WORKSPACE</p><h2>{activePanel === "overview" ? "Your money at a glance" : activePanel === "transactions" ? "Transactions" : activePanel === "receipts" ? "Receipt inbox" : activePanel === "catalog" ? "Products, customers & budgets" : activePanel === "operations" ? "Plan, forecast & export" : "Profit and financial intelligence"}</h2><p className="finance-muted">Only posted records contribute to totals. Workspace records stay separate.</p></div><span className="finance-currency">{workspace.currency_code}</span></div>
    <nav className="finance-nav" aria-label="Financial tools">
      <button type="button" className={activePanel === "overview" ? "finance-nav-item finance-nav-item--active" : "finance-nav-item"} onClick={() => setActivePanel("overview")}>Overview</button>
      <button type="button" className={activePanel === "transactions" ? "finance-nav-item finance-nav-item--active" : "finance-nav-item"} onClick={() => setActivePanel("transactions")}>Transactions <span>＋</span></button>
      <button type="button" className={activePanel === "receipts" ? "finance-nav-item finance-nav-item--active" : "finance-nav-item"} onClick={() => setActivePanel("receipts")}>Receipts</button>
      <button type="button" className={activePanel === "insights" ? "finance-nav-item finance-nav-item--active" : "finance-nav-item"} onClick={() => setActivePanel("insights")}>MarginGuard & AI</button>
      <button type="button" className={activePanel === "catalog" ? "finance-nav-item finance-nav-item--active" : "finance-nav-item"} onClick={() => setActivePanel("catalog")}>Products & budgets</button>
      <button type="button" className={activePanel === "operations" ? "finance-nav-item finance-nav-item--active" : "finance-nav-item"} onClick={() => setActivePanel("operations")}>Plan & export</button>
    </nav>
    {activePanel === "overview" && <GuidedOnboarding workspaceId={workspace.id} accessToken={accessToken} onNavigate={setActivePanel} />}
     {activePanel === "overview" && <div className="overview-quick-actions"><button type="button" className="finance-button" onClick={() => setActivePanel("transactions")}>＋ Add transaction</button><button type="button" className="finance-button finance-button--quiet" onClick={() => setActivePanel("receipts")}>Upload receipt</button><button type="button" className="finance-button finance-button--quiet" onClick={() => setActivePanel("insights")}>Review margin insights</button></div>}
     <div className="finance-filters"><label>From<input type="date" value={from} max={to} onChange={e => setFrom(e.target.value)} /></label><label>To<input type="date" value={to} min={from} max={today()} onChange={e => setTo(e.target.value)} /></label><button className="finance-button finance-button--quiet" type="button" onClick={() => { setFrom(daysAgo(29)); setTo(today()); }}>Last 30 days</button></div>
    {error && <p className="form-message form-message--error" role="alert">{error}</p>}{notice && <p className="form-message" role="status">{notice}</p>}{loading && <p className="form-hint">Loading financial records…</p>}
    {activePanel === "overview" && <div className="finance-metrics">{(summary?.currencies ?? []).map(s => <div className="finance-metric-grid" key={s.currency_code}>
      <article className="finance-metric"><span>Recorded income</span><strong>{cash(s.income, s.currency_code)}</strong><small>{s.income_count} entries</small></article>
      <article className="finance-metric"><span>Recorded expenses</span><strong>{cash(s.expenses, s.currency_code)}</strong><small>{s.expense_count} entries</small></article>
      <article className="finance-metric"><span>Net cash movement</span><strong>{cash(s.net_cash_movement, s.currency_code)}</strong><small>Not the same as profit</small></article>
    </div>)}{!loading && canViewCombined && !summary?.currencies.length && <p className="finance-empty">No posted transactions in this period. Add one below.</p>}
     {!canViewCombined && <p className="finance-footnote">Combined summaries and MarginGuard require read access to both sales and expenses.</p>}</div>}
    
     {activePanel === "overview" && overviewProfit && <section className="overview-profit-card">
      <div><p className="eyebrow">PROFITABILITY SNAPSHOT</p><h3>Know what the sales are really earning</h3><p className="finance-muted">Gross profit is revenue minus recognised direct costs. It is not the same as cash movement or final net profit.</p></div>
      <div className="overview-profit-values"><div><span>Gross profit</span><strong>{overviewProfit.gross_profit === null ? "Not available" : cash(overviewProfit.gross_profit, overviewProfit.currency_code)}</strong></div><div><span>Gross margin</span><strong>{overviewProfit.gross_margin_percent === null ? "Not available" : overviewProfit.gross_margin_percent + "%"}</strong></div></div>
      <p className="finance-footnote">{overviewProfit.note}</p>
    </section>}
    {activePanel === "overview" && <div className="overview-charts">
      <section className="finance-card overview-chart-card">
        <div className="finance-card-heading"><div><p className="eyebrow">CASH FLOW</p><h3>Income vs expenses</h3><p className="finance-muted">Daily recorded activity over the last seven days of this date range.</p></div></div>
        {cashTrend.some((day) => day.income > 0 || day.expenses > 0) ? <div className="cash-trend-chart" role="img" aria-label="Daily income and expenses bar chart">
          <div className="cash-trend-legend"><span><i className="trend-dot trend-dot--income" />Income</span><span><i className="trend-dot trend-dot--expense" />Expenses</span></div>
          <div className="cash-trend-bars">{cashTrend.map((day) => <div className="cash-trend-day" key={day.day}>
            <div className="cash-trend-bar-pair" title={day.day + ": income " + day.income.toFixed(2) + ", expenses " + day.expenses.toFixed(2)}>
              <span className="cash-trend-bar cash-trend-bar--income" style={{ height: Math.max(day.income ? 4 : 0, day.income / maxDailyAmount * 100) + "%" }} />
              <span className="cash-trend-bar cash-trend-bar--expense" style={{ height: Math.max(day.expenses ? 4 : 0, day.expenses / maxDailyAmount * 100) + "%" }} />
            </div><small>{day.label}</small>
          </div>)}</div>
        </div> : <p className="finance-empty">There is not enough recorded activity in this seven-day window to draw a chart. Add transactions and the chart will update.</p>}
        <p className="finance-footnote">This visual uses the transactions currently loaded (up to 100 records); the summary figures above come from the financial-summary endpoint.</p>
      </section>
      <section className="finance-card overview-chart-card">
        <div className="finance-card-heading"><div><p className="eyebrow">SPENDING PATTERN</p><h3>Where expenses go</h3><p className="finance-muted">Top categories among loaded posted expenses.</p></div></div>
        {expenseCategories.length ? <div className="expense-category-chart">{expenseCategories.map(([name, total]) => <div className="expense-category-row" key={name}>
          <div><span>{name}</span><strong>{cash(String(total), workspace.currency_code)}</strong></div>
          <div className="expense-category-track"><span style={{ width: (total / maxCategoryExpense * 100) + "%" }} /></div>
        </div>)}</div> : <p className="finance-empty">No posted expenses are available to break down yet. Once you record expenses, this chart will show which categories account for the most spending.</p>}
        <p className="finance-footnote">Category breakdown is based on the transactions currently loaded for this period, up to 100 records.</p>
      </section>
    </div>}
    {activePanel === "overview" && <section className="finance-card overview-recent-card">
       <div className="finance-card-heading"><div><p className="eyebrow">RECENT ACTIVITY</p><h3>Latest transactions</h3><p className="finance-muted">Recent records in the selected date range. Drafts and voided entries are labelled.</p></div><button className="finance-button finance-button--quiet" type="button" onClick={() => setActivePanel("transactions")}>View all</button></div>
       {rows.length === 0 ? <p className="finance-empty">Your activity will appear here after you add a transaction. <button type="button" className="finance-link" onClick={() => setActivePanel("transactions")}>Add your first transaction</button></p> : <div className="overview-recent-list">{[...rows].sort((a,b) => b.transaction_date.localeCompare(a.transaction_date)).slice(0,5).map(tx => <div className="overview-recent-row" key={tx.id}><div><strong>{tx.description}</strong><small>{tx.transaction_date} · {tx.category || "Uncategorised"} · <span className={"finance-status finance-status--" + tx.status}>{tx.status}</span></small></div><strong className={tx.direction === "expense" ? "recent-amount recent-amount--expense" : "recent-amount recent-amount--income"}>{tx.direction === "expense" ? "−" : "+"}{cash(tx.amount, tx.currency_code)}</strong></div>)}</div>}
     </section>}
     <div className="finance-columns">
      {activePanel === "transactions" && writeDirections.length > 0 && <section className="finance-card"><p className="eyebrow">01 / TRACK</p><h3 id="transaction-entry-title">Quick-add a transaction</h3><p className="finance-muted">Save a completed entry or keep it as a draft to review later. Drafts do not affect totals.</p>
        <form className="finance-form" onSubmit={addTransaction}>
          <label>Type<select value={direction} onChange={e => setDirection(e.target.value as "income" | "expense")}>{canWrite("expenses") && <option value="expense">Expense</option>}{canWrite("sales") && <option value="income">Income / sale</option>}</select></label>
           {recurringTemplates.some(item => item.is_active) && <label className="finance-full">Fill from recurring expectation (optional)<select value={selectedRecurringId} onChange={e => applyRecurringTemplate(e.target.value)}><option value="">Start from a blank transaction</option>{recurringTemplates.filter(item => item.is_active).map(item => <option key={item.id} value={item.id}>{item.description} · {item.interval} · due {item.next_due_date}</option>)}</select><small>Copies the expected payment details only; it does not confirm payment.</small></label>}
          <label>Amount ({workspace.currency_code})<input type="number" min="0.01" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} required /></label>
          <label>Date<input type="date" value={date} max={today()} onChange={e => setDate(e.target.value)} required /></label>
          <label>Category<select value={category} onChange={e => setCategory(e.target.value)}>{["Uncategorised","Sales","COGS","Cost of goods sold","Cost of sales","Direct costs","Inventory cost","Rent","Transport","Utilities","Marketing","Equipment","Other"].map(c => <option key={c}>{c}</option>)}</select></label>
          {canRead("sales") && <label>Product/service (optional)<select value={selectedProductId} onChange={e => setSelectedProductId(e.target.value)}><option value="">Not attributed</option>{products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>}
          {canRead("sales") && <label>Customer (optional)<select value={selectedCustomerId} onChange={e => setSelectedCustomerId(e.target.value)}><option value="">Not attributed</option>{customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>}
          <label className="finance-full">Description / note<input value={description} onChange={e => setDescription(e.target.value)} maxLength={500} required placeholder="What was this payment for?" /></label>
           <label>Save as<select value={transactionStatus} onChange={e => setTransactionStatus(e.target.value as "draft" | "posted")}><option value="posted">Posted transaction</option><option value="draft">Draft for review</option></select></label>
          <button className="finance-button" disabled={busy}>{busy ? "Saving…" : transactionStatus === "draft" ? "Save draft" : "Post transaction"}</button>
        </form><p className="finance-footnote">Voiding preserves history. Amounts use decimal storage.</p>
      </section>}
      {activePanel === "transactions" && canWriteAny && <section className="finance-card"><p className="eyebrow">02 / IMPORT</p><h3>Import transactions from CSV</h3><p className="finance-muted">Required columns: direction, amount, transaction_date, description. Optional: currency_code, category, status. Amounts must use this workspace currency; rows import as drafts by default.</p><form className="finance-upload" onSubmit={importTransactionsCsv}><input name="transaction-csv" type="file" accept=".csv,text/csv" required /><button className="finance-button" disabled={busy}>{busy ? "Importing…" : "Validate and import CSV"}</button></form><p className="finance-footnote">Up to 500 rows and 2 MB. If any row is invalid or you lack permission for a row, nothing is imported. Review imported drafts before posting.</p></section>}
      {activePanel === "receipts" && canReadExpenses && <section className="finance-card"><p className="eyebrow">02 / CAPTURE</p><h3>Scan a receipt</h3><p className="finance-muted">JPEG, PNG, WebP or PDF up to 5 MB. Confirm every field before saving.</p>
        {canWriteExpenses && <form className={"finance-upload finance-upload--drop" + (receiptDragActive ? " finance-upload--drag-active" : "")} onSubmit={uploadReceipt} onDragOver={event => { event.preventDefault(); setReceiptDragActive(true); }} onDragLeave={() => setReceiptDragActive(false)} onDrop={event => { event.preventDefault(); setReceiptDragActive(false); chooseReceiptFile(event.dataTransfer.files?.[0] ?? null); }}><div className="receipt-drop-copy"><strong>Drop a receipt here</strong><span>or choose a file · JPEG, PNG, WebP or PDF · max 5 MB</span></div><input name="receipt-file" type="file" accept="image/jpeg,image/png,image/webp,application/pdf" onChange={event => chooseReceiptFile(event.target.files?.[0] ?? null)} /><button className="finance-button" disabled={busy || !(selectedReceiptFile || undefined)}>Upload and extract</button></form>{selectedReceiptFile && <p className="receipt-file-selected" role="status">Selected: {selectedReceiptFile.name} · {(selectedReceiptFile.size / 1024).toFixed(0)} KB <button type="button" className="finance-link" onClick={() => setSelectedReceiptFile(null)}>Remove</button></p>}}
        <p className="finance-footnote">Files are private to this workspace. OCR is best-effort; enter details manually if text extraction is unavailable.</p>
        {receipts.filter(r => r.review_status === "pending").map(r => {
          const f = receiptFields[r.id] ?? { amount: r.candidate_amount ?? "", date: r.candidate_date ?? today(), description: r.candidate_merchant ?? r.original_filename, category: "Uncategorised", direction: "expense" as const };
          const change = (patch: Partial<typeof f>) => setReceiptFields(old => ({ ...old, [r.id]: { ...f, ...patch } }));
          return <article className="receipt-review" key={r.id}><strong>{r.original_filename} — needs review</strong>
            <p className="receipt-review-warning"><strong>Review required:</strong> extracted values are suggestions, not verified facts. Compare them with the original receipt before confirming.</p>{r.extracted_text ? <details><summary>View extracted text</summary><pre>{r.extracted_text}</pre></details> : <p className="finance-muted">No text extracted; complete fields manually.</p>}
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
    {activePanel === "transactions" && <section className="finance-card finance-records"><div className="finance-card-heading"><div><p className="eyebrow">03 / LEDGER</p><h3>Transactions</h3></div><span className="finance-muted">{visibleTransactions.length} of {rows.length} records</span></div>
      <label className="finance-search">Search transactions<input type="search" value={transactionSearch} onChange={e => setTransactionSearch(e.target.value)} placeholder="Description, category, date, amount or status" aria-label="Search loaded transactions" /></label>
      {!rows.length && (canRead("sales") || canRead("expenses")) && <p className="finance-empty">No transactions in this date range.</p>}
      {rows.length > 0 && visibleTransactions.length === 0 && <p className="finance-empty">No transactions match “{transactionSearch}”. Try a different search.</p>}
      {!rows.length && !canRead("sales") && !canRead("expenses") && <p className="finance-empty">You do not have read access to sales or expenses in this workspace.</p>}
      <div className="finance-table-wrap"><table className="finance-table"><thead><tr><th>Date</th><th>Details</th><th>Category</th><th>Amount</th><th>Status</th><th>Actions</th></tr></thead><tbody>
        {visibleTransactions.map(tx => <tr key={tx.id} className={tx.status === "void" ? "finance-row--void" : ""}><td>{tx.transaction_date}</td><td><strong>{tx.description}</strong><small>{tx.direction}</small></td><td>{tx.category ?? "Uncategorised"}</td><td>{tx.direction === "expense" ? "−" : "+"}{cash(tx.amount, tx.currency_code)}</td><td><span className={"finance-status finance-status--" + tx.status}>{tx.status}</span></td>
          <td>{tx.status !== "void" && canWrite(tx.direction === "income" ? "sales" : "expenses") && <div className="finance-actions"><button className="finance-link" type="button" onClick={() => startEdit(tx)}>Edit</button>{tx.status === "draft" && <button className="finance-link" type="button" onClick={() => void postDraft(tx)} disabled={busy}>Review & post</button>}<button className="finance-link" type="button" onClick={() => duplicateTransaction(tx)}>Duplicate</button><button className="finance-link finance-link--danger" type="button" onClick={() => void voidTx(tx)} disabled={busy}>Void</button></div>}</td></tr>)}
      </tbody></table></div>
      {editing && <form className="finance-edit" onSubmit={saveEdit}><h3>Edit transaction</h3><label>Amount<input type="number" min="0.01" step="0.01" value={editAmount} onChange={e => setEditAmount(e.target.value)} required /></label><label>Date<input type="date" value={editDate} onChange={e => setEditDate(e.target.value)} required /></label><label>Description<input value={editDescription} onChange={e => setEditDescription(e.target.value)} required /></label><label>Category<input value={editCategory} onChange={e => setEditCategory(e.target.value)} /></label><div className="finance-actions"><button className="finance-button" disabled={busy}>Save changes</button><button className="finance-button finance-button--quiet" type="button" onClick={() => setEditing(null)}>Cancel</button></div></form>}
    </section>}
    {activePanel === "insights" && canViewCombined && <div className="finance-columns finance-bottom"><section className="finance-card"><p className="eyebrow">04 / CALCULATE</p><h3>Profitability — where supported</h3>
      {(summary?.profitability.currencies ?? []).map(p => <div className="profitability-row" key={p.currency_code}><div><span>Revenue</span><strong>{cash(p.revenue, p.currency_code)}</strong></div><div><span>Recognised direct costs</span><strong>{cash(p.direct_costs, p.currency_code)}</strong></div><div><span>Gross profit</span><strong>{p.gross_profit === null ? "Not available" : cash(p.gross_profit, p.currency_code)}</strong></div><div><span>Gross margin</span><strong>{p.gross_margin_percent === null ? "Not available" : p.gross_margin_percent + "%"}</strong></div><p className="finance-footnote">{p.note} General expenses are not automatically treated as direct costs.</p></div>)}
      {!summary?.profitability.currencies.length && <p className="finance-empty">Add posted income and direct costs to calculate gross profit.</p>}
    </section><section className="finance-card"><p className="eyebrow">05 / INVESTIGATE</p><h3>MarginGuard</h3><p className="finance-muted">Latest 30 days compared with the preceding 30 days. Changes are not proof of cause.</p>
      {!findings.length && <p className="finance-empty">No comparable changes detected, or not enough history yet.</p>}
      {findings.map((f, i) => <article className="guard-finding" key={f.kind + f.currency_code + i}><span className={"finance-status finance-status--" + (f.severity === "warning" ? "warning" : "posted")}>{f.severity}</span><strong>{f.summary}</strong><p className="margin-explanation">{f.kind === "revenue_change" ? "Revenue is different from the previous comparison period. Review sales volume, prices, refunds, and missing entries before deciding what changed." : f.kind === "expense_change" ? "Recorded expenses changed between periods. Review category mix, one-off purchases, and missing or duplicate entries." : f.kind === "new_currency_activity" ? "This currency has activity now but no comparable prior-period records, so a like-for-like change cannot be calculated." : "This signal highlights a recorded financial change; use the evidence below to investigate it."}</p>{f.current && f.previous && <details><summary>Compare current and previous period</summary><div className="evidence-row"><span>Current value</span><strong>{Object.values(f.current).filter(v => v !== null).join(" · ") || "Not available"}</strong></div><div className="evidence-row"><span>Previous value</span><strong>{Object.values(f.previous).filter(v => v !== null).join(" · ") || "Not available"}</strong></div></details>}<p>{f.uncertainty}</p><details><summary>Evidence ({f.evidence?.length ?? 0} records)</summary>{(f.evidence ?? []).map(ev => <div className="evidence-row" key={ev.id}><span>{ev.date} · {ev.description}</span><strong>{ev.direction} {cash(ev.amount, f.currency_code)}</strong></div>)}</details></article>)}
    </section></div>}
    {activePanel === "insights" && canViewCombined && <FinancialIntelligence workspaceId={workspace.id} accessToken={accessToken} />}
    {activePanel === "catalog" && <FinancialCatalogBudget workspaceId={workspace.id} accessToken={accessToken} currencyCode={workspace.currency_code} startDate={from} endDate={to} canReadSales={canRead("sales")} canWriteSales={canWrite("sales")} canReadExpenses={canRead("expenses")} canWriteExpenses={canWrite("expenses")} />}
    {activePanel === "operations" && canViewCombined && <FinancialOperations workspaceId={workspace.id} accessToken={accessToken} currencyCode={workspace.currency_code} />}
    {activePanel === "operations" && !canViewCombined && <p className="finance-empty">Planning, alerts, and combined exports require read access to both sales and expenses in this workspace.</p>}
    {activePanel === "insights" && !canViewCombined && <p className="finance-empty">MarginGuard and combined financial intelligence require read access to both sales and expenses in this workspace.</p>}
    <p className="finance-disclaimer">Exprofit reports recorded information only. Cash movement is not profit. Check source records before making a business decision.</p>
  </section>;
}
