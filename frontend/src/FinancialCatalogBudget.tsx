import { useEffect, useState, type FormEvent } from "react";

type Product = { id: string; name: string; sku: string | null; unit_price: string | null; unit_cost: string | null; currency_code: string; };
type Customer = { id: string; name: string; email: string | null; phone: string | null; };
type ProfitItem = { id: string; name: string; currency_code: string; revenue: string; direct_costs: string; gross_profit: string | null; gross_margin_percent: string | null; transaction_count: number; note: string; };
type BudgetActual = { id: string; category: string; currency_code: string; period_start: string; period_end: string; budget_amount: string; actual_spend: string; remaining: string; used_percent: string; warning_threshold_percent: number; status: "on_track" | "warning" | "over_budget"; };
type Budget = { id: string; category: string; period_start: string; period_end: string; amount: string; currency_code: string; warning_threshold_percent: number; };
type Props = { workspaceId: string; accessToken: string; currencyCode: string; canReadSales: boolean; canWriteSales: boolean; canReadExpenses: boolean; canWriteExpenses: boolean; };
const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const today = () => { const d = new Date(); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); };
const monthStart = () => today().slice(0, 8) + "01";
const cash = (value: string | null, currency: string) => value === null ? "Not available" : currency + " " + Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
function errorMessage(data: unknown): string {
  if (data && typeof data === "object" && "detail" in data && typeof data.detail === "string") return data.detail;
  return "Request failed. Please check the fields and try again.";
}

export default function FinancialCatalogBudget({ workspaceId, accessToken, currencyCode, canReadSales, canWriteSales, canReadExpenses, canWriteExpenses }: Props) {
  const [products, setProducts] = useState<Product[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [productProfit, setProductProfit] = useState<ProfitItem[]>([]);
  const [customerProfit, setCustomerProfit] = useState<ProfitItem[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [budgetActual, setBudgetActual] = useState<BudgetActual[]>([]);
  const [productName, setProductName] = useState("");
  const [productSku, setProductSku] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [customerName, setCustomerName] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [budgetCategory, setBudgetCategory] = useState("Rent");
  const [budgetAmount, setBudgetAmount] = useState("");
  const [periodStart, setPeriodStart] = useState(monthStart());
  const [periodEnd, setPeriodEnd] = useState(today());
  const [threshold, setThreshold] = useState("80");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Authorization", "Bearer " + accessToken);
    if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBase + path, { ...init, headers });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(errorMessage(data));
    return data as T;
  }

  async function refresh() {
    setError("");
    try {
      const tasks: Promise<unknown>[] = [];
      if (canReadSales) {
        tasks.push(request<Product[]>("/businesses/" + workspaceId + "/products").then(setProducts));
        tasks.push(request<Customer[]>("/businesses/" + workspaceId + "/customers").then(setCustomers));
      } else {
        setProducts([]); setCustomers([]);
      }
      if (canReadSales && canReadExpenses) {
        tasks.push(request<{ items: ProfitItem[] }>("/businesses/" + workspaceId + "/product-profitability").then(x => setProductProfit(x.items)));
        tasks.push(request<{ items: ProfitItem[] }>("/businesses/" + workspaceId + "/customer-profitability").then(x => setCustomerProfit(x.items)));
      } else {
        setProductProfit([]); setCustomerProfit([]);
      }
      if (canReadExpenses) {
        tasks.push(request<Budget[]>("/businesses/" + workspaceId + "/budgets").then(setBudgets));
        tasks.push(request<{ items: BudgetActual[] }>("/businesses/" + workspaceId + "/budget-vs-actual").then(x => setBudgetActual(x.items)));
      } else {
        setBudgets([]); setBudgetActual([]);
      }
      await Promise.all(tasks);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load catalog and budget information.");
    }
  }
  useEffect(() => { void refresh(); }, [workspaceId, accessToken, canReadSales, canReadExpenses]);

  async function addProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      await request<Product>("/businesses/" + workspaceId + "/products", { method: "POST", body: JSON.stringify({
        name: productName, sku: productSku || null, unit_price: unitPrice || null, unit_cost: unitCost || null,
      }) });
      setProductName(""); setProductSku(""); setUnitPrice(""); setUnitCost(""); setNotice("Product saved. You can now attribute sales and direct-cost transactions to it."); await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save product."); }
    finally { setBusy(false); }
  }

  async function addCustomer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      await request<Customer>("/businesses/" + workspaceId + "/customers", { method: "POST", body: JSON.stringify({
        name: customerName, email: customerEmail || null,
      }) });
      setCustomerName(""); setCustomerEmail(""); setNotice("Customer saved. You can now attribute transactions to this customer."); await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save customer."); }
    finally { setBusy(false); }
  }

  async function addBudget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      await request<Budget>("/businesses/" + workspaceId + "/budgets", { method: "POST", body: JSON.stringify({
        category: budgetCategory, amount: budgetAmount, period_start: periodStart, period_end: periodEnd,
        warning_threshold_percent: Number(threshold),
      }) });
      setBudgetAmount(""); setNotice("Budget saved. Actuals are calculated from posted expenses with an exact category match."); await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save budget."); }
    finally { setBusy(false); }
  }

  return <section className="catalog-budget">
    <div className="finance-card-heading"><div><p className="eyebrow">UNIT 15–17</p><h3>Products, customers & budgets</h3><p className="finance-muted">Attribute posted transactions to products/customers and compare category spending with a budget.</p></div><button type="button" className="finance-button finance-button--quiet" onClick={() => void refresh()}>Refresh</button></div>
    {error && <p className="form-message form-message--error" role="alert">{error}</p>}
    {notice && <p className="form-message" role="status">{notice}</p>}
    {canWriteSales && <div className="finance-columns">
      <section className="finance-card"><h3>Add product or service</h3><form className="finance-form" onSubmit={addProduct}>
        <label>Product/service name<input value={productName} onChange={e => setProductName(e.target.value)} maxLength={160} required /></label>
        <label>SKU (optional)<input value={productSku} onChange={e => setProductSku(e.target.value)} maxLength={80} /></label>
        <label>Unit price ({currencyCode}, optional)<input type="number" min="0" step="0.01" value={unitPrice} onChange={e => setUnitPrice(e.target.value)} /></label>
        <label>Reference unit cost ({currencyCode}, optional)<input type="number" min="0" step="0.01" value={unitCost} onChange={e => setUnitCost(e.target.value)} /></label>
        <button className="finance-button" disabled={busy}>Save product</button>
      </form><p className="finance-footnote">Reference unit cost is descriptive only. Profitability uses recorded direct-cost transactions, not guessed cost multiplications.</p></section>
      <section className="finance-card"><h3>Add customer</h3><form className="finance-form" onSubmit={addCustomer}>
        <label>Customer name<input value={customerName} onChange={e => setCustomerName(e.target.value)} maxLength={160} required /></label>
        <label>Email (optional)<input type="email" value={customerEmail} onChange={e => setCustomerEmail(e.target.value)} maxLength={254} /></label>
        <button className="finance-button" disabled={busy}>Save customer</button>
      </form><p className="finance-footnote">Only save contact details needed for your business. Customer access follows the workspace's sales permissions.</p></section>
    </div>}
    {canReadSales && <section className="finance-card"><h3>Catalog</h3><div className="finance-columns">
      <div><strong>Products/services ({products.length})</strong>{products.map(p => <div className="evidence-row" key={p.id}><span>{p.name}{p.sku ? " · " + p.sku : ""}</span><strong>{p.unit_price ? cash(p.unit_price, p.currency_code) : "Price not set"}</strong></div>)}{!products.length && <p className="finance-empty">No products yet.</p>}</div>
      <div><strong>Customers ({customers.length})</strong>{customers.map(c => <div className="evidence-row" key={c.id}><span>{c.name}</span><strong>{c.email ?? c.phone ?? "No contact saved"}</strong></div>)}{!customers.length && <p className="finance-empty">No customers yet.</p>}</div>
    </div></section>}
    {canWriteExpenses && <section className="finance-card"><h3>Create a category budget</h3><form className="finance-form" onSubmit={addBudget}>
      <label>Expense category<input value={budgetCategory} onChange={e => setBudgetCategory(e.target.value)} maxLength={80} required /></label>
      <label>Budget amount ({currencyCode})<input type="number" min="0.01" step="0.01" value={budgetAmount} onChange={e => setBudgetAmount(e.target.value)} required /></label>
      <label>Period starts<input type="date" value={periodStart} onChange={e => setPeriodStart(e.target.value)} required /></label>
      <label>Period ends<input type="date" min={periodStart} value={periodEnd} onChange={e => setPeriodEnd(e.target.value)} required /></label>
      <label>Warning threshold (%)<input type="number" min="1" max="200" value={threshold} onChange={e => setThreshold(e.target.value)} required /></label>
      <button className="finance-button" disabled={busy}>Save budget</button>
    </form><p className="finance-footnote">A warning appears at the chosen threshold. An over-budget status appears at 100%. Duplicate category/date budgets are rejected.</p></section>}
    {canReadExpenses && <section className="finance-card"><h3>Budget versus actual</h3><p className="finance-muted">{budgets.length} saved budget(s)</p>
      {!budgetActual.length && <p className="finance-empty">No budgets have been created yet.</p>}
      <div className="finance-table-wrap"><table className="finance-table"><thead><tr><th>Category / period</th><th>Budget</th><th>Actual spend</th><th>Remaining</th><th>Used</th><th>Status</th></tr></thead><tbody>
        {budgetActual.map(b => <tr key={b.id}><td><strong>{b.category}</strong><small>{b.period_start} – {b.period_end}</small></td><td>{cash(b.budget_amount, b.currency_code)}</td><td>{cash(b.actual_spend, b.currency_code)}</td><td>{cash(b.remaining, b.currency_code)}</td><td>{b.used_percent}%</td><td><span className={"finance-status " + (b.status === "over_budget" ? "finance-status--warning" : b.status === "warning" ? "finance-status--warning" : "finance-status--posted")}>{b.status.replace("_", " ")}</span></td></tr>)}
      </tbody></table></div>
    </section>}
    {canReadSales && canReadExpenses && <div className="finance-columns">
      <section className="finance-card"><h3>Profitability by product/service</h3>{!productProfit.length && <p className="finance-empty">Add a product and attribute posted sales/direct costs to it.</p>}
        {productProfit.map(p => <article className="guard-finding" key={p.id}><strong>{p.name}</strong><p>Revenue: {cash(p.revenue, p.currency_code)} · Direct costs: {cash(p.direct_costs, p.currency_code)}</p><p>Gross profit: {cash(p.gross_profit, p.currency_code)} · Margin: {p.gross_margin_percent === null ? "Not available" : p.gross_margin_percent + "%"}</p><p className="finance-footnote">{p.transaction_count} linked records. {p.note}</p></article>)}
      </section>
      <section className="finance-card"><h3>Profitability by customer</h3>{!customerProfit.length && <p className="finance-empty">Add a customer and attribute posted transactions to them.</p>}
        {customerProfit.map(p => <article className="guard-finding" key={p.id}><strong>{p.name}</strong><p>Revenue: {cash(p.revenue, p.currency_code)} · Direct costs: {cash(p.direct_costs, p.currency_code)}</p><p>Gross profit: {cash(p.gross_profit, p.currency_code)} · Margin: {p.gross_margin_percent === null ? "Not available" : p.gross_margin_percent + "%"}</p><p className="finance-footnote">{p.transaction_count} linked records. {p.note}</p></article>)}
      </section>
    </div>}
    <p className="finance-disclaimer">These are deterministic summaries of posted, explicitly attributed records. Missing direct-cost transactions mean gross profit is not available; an estimate is never silently substituted.</p>
  </section>;
}
