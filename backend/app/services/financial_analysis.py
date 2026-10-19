"""Deterministic summaries and evidence-backed margin comparisons."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

ZERO = Decimal("0.00")
DIRECT_COST_CATEGORIES = {
    "cogs", "cost of goods sold", "cost of sales", "direct cost", "direct costs",
    "product cost", "inventory cost", "raw materials",
}


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def summarize_transactions(transactions: list[Any]) -> dict[str, Any]:
    """Summarize posted records without mixing currencies or calling cash movement profit."""
    currencies: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {"income": ZERO, "expenses": ZERO, "income_count": 0, "expense_count": 0}
    )
    categories: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"income": ZERO, "expense": ZERO}
    )
    for item in transactions:
        if item.status != "posted":
            continue
        bucket = currencies[item.currency_code]
        category = (item.category or "Uncategorised").strip() or "Uncategorised"
        amount = Decimal(item.amount)
        if item.direction == "income":
            bucket["income"] = Decimal(bucket["income"]) + amount
            bucket["income_count"] = int(bucket["income_count"]) + 1
            categories[category]["income"] += amount
        elif item.direction == "expense":
            bucket["expenses"] = Decimal(bucket["expenses"]) + amount
            bucket["expense_count"] = int(bucket["expense_count"]) + 1
            categories[category]["expense"] += amount
    result = []
    for currency, values in sorted(currencies.items()):
        income = _money(Decimal(values["income"]))
        expenses = _money(Decimal(values["expenses"]))
        result.append({
            "currency_code": currency,
            "income": str(income),
            "expenses": str(expenses),
            "net_cash_movement": str(_money(income - expenses)),
            "income_count": int(values["income_count"]),
            "expense_count": int(values["expense_count"]),
        })
    category_rows = [
        {"category": name, "income": str(_money(values["income"])),
         "expenses": str(_money(values["expense"]))}
        for name, values in sorted(categories.items(), key=lambda pair: pair[0].casefold())
    ]
    return {"currencies": result, "categories": category_rows, "posted_record_count": sum(
        int(row["income_count"]) + int(row["expense_count"]) for row in result
    )}


def profitability(transactions: list[Any]) -> dict[str, Any]:
    """Calculate revenue and explicitly categorised direct costs only.

    General operating expenses are not silently treated as cost of goods sold.
    """
    posted = [item for item in transactions if item.status == "posted"]
    currencies = sorted({item.currency_code for item in posted})
    result = []
    for currency in currencies:
        items = [item for item in posted if item.currency_code == currency]
        revenue = sum(
            (Decimal(item.amount) for item in items if item.direction == "income"), ZERO
        )
        direct_costs = sum(
            (
                Decimal(item.amount) for item in items
                if item.direction == "expense"
                and (item.category or "").strip().casefold() in DIRECT_COST_CATEGORIES
            ),
            ZERO,
        )
        has_direct_cost_records = any(
            item.direction == "expense"
            and (item.category or "").strip().casefold() in DIRECT_COST_CATEGORIES
            for item in items
        )
        gross_profit = revenue - direct_costs
        result.append({
            "currency_code": currency,
            "revenue": str(_money(revenue)),
            "direct_costs": str(_money(direct_costs)),
            "gross_profit": str(_money(gross_profit)) if has_direct_cost_records else None,
            "gross_margin_percent": (
                str((gross_profit / revenue * Decimal("100")).quantize(Decimal("0.01")))
                if has_direct_cost_records and revenue > 0 else None
            ),
            "direct_cost_data_available": has_direct_cost_records,
            "note": (
                "Gross profit includes only expenses explicitly categorised as direct costs."
                if has_direct_cost_records
                else (
                    "Gross profit is unavailable until direct costs are recorded "
                    "with a recognised direct-cost category."
                )
            ),
        })
    return {"currencies": result}


def compare_periods(
    current: list[Any], previous: list[Any], current_start: date, current_end: date,
    previous_start: date, previous_end: date,
) -> dict[str, Any]:
    """Compare revenue, expenses and supported gross margin; attach record evidence."""
    def metrics(items: list[Any]) -> dict[str, Any]:
        posted = [x for x in items if x.status == "posted"]
        currencies = sorted({x.currency_code for x in posted})
        rows = []
        for currency in currencies:
            selected = [x for x in posted if x.currency_code == currency]
            revenue = sum((Decimal(x.amount) for x in selected if x.direction == "income"), ZERO)
            expenses = sum((Decimal(x.amount) for x in selected if x.direction == "expense"), ZERO)
            direct = sum((Decimal(x.amount) for x in selected if x.direction == "expense" and
                          (x.category or "").strip().casefold() in DIRECT_COST_CATEGORIES), ZERO)
            has_direct = any(x.direction == "expense" and
                             (x.category or "").strip().casefold() in DIRECT_COST_CATEGORIES
                             for x in selected)
            rows.append({
                "currency_code": currency, "revenue": _money(revenue),
                "expenses": _money(expenses), "direct_costs": _money(direct),
                "gross_margin_percent": (
                    (revenue - direct) / revenue * Decimal("100")
                    if has_direct and revenue > 0 else None
                ),
                "records": [{
                    "id": str(x.id), "date": x.transaction_date.isoformat(),
                    "direction": x.direction, "amount": str(x.amount),
                    "category": x.category, "description": x.description,
                } for x in selected],
            })
        return {"currencies": rows}
    now = metrics(current)
    before = metrics(previous)
    before_by_currency = {x["currency_code"]: x for x in before["currencies"]}
    findings = []
    for row in now["currencies"]:
        old = before_by_currency.get(row["currency_code"])
        if old is None:
            findings.append({
                "kind": "new_currency_activity", "severity": "info",
                "currency_code": row["currency_code"],
                "summary": (
                    "This currency has current-period activity but no previous-period "
                    "activity."
                ),
                "current": {
                    key: str(value) if isinstance(value, Decimal) else value
                    for key, value in row.items()
                    if key != "records"
                },
                "previous": None, "evidence": row["records"],
                "uncertainty": "A comparison is not possible without records in both periods.",
            })
            continue
        revenue_delta = row["revenue"] - old["revenue"]
        expenses_delta = row["expenses"] - old["expenses"]
        if revenue_delta != 0:
            findings.append({
                "kind": "revenue_change", "severity": "warning" if revenue_delta < 0 else "info",
                "currency_code": row["currency_code"],
                "summary": (
                    f"Revenue {'decreased' if revenue_delta < 0 else 'increased'} by "
                    f"{abs(revenue_delta):.2f} {row['currency_code']}."
                ),
                "current": {"revenue": str(row["revenue"])},
                "previous": {"revenue": str(old["revenue"])},
                "change": str(_money(revenue_delta)), "evidence": row["records"],
                "previous_evidence": old["records"],
                "uncertainty": "The records show a change, but do not establish its cause.",
            })
        if expenses_delta != 0:
            findings.append({
                "kind": "expense_change", "severity": "warning" if expenses_delta > 0 else "info",
                "currency_code": row["currency_code"],
                "summary": (
                    f"Recorded expenses {'increased' if expenses_delta > 0 else 'decreased'} "
                    f"by {abs(expenses_delta):.2f} {row['currency_code']}."
                ),
                "current": {"expenses": str(row["expenses"])},
                "previous": {"expenses": str(old["expenses"])},
                "change": str(_money(expenses_delta)), "evidence": row["records"],
                "previous_evidence": old["records"],
                "uncertainty": (
                    "Only recorded entries are included; unrecorded costs are not visible."
                ),
            })
        if row["gross_margin_percent"] is not None and old["gross_margin_percent"] is not None:
            delta = row["gross_margin_percent"] - old["gross_margin_percent"]
            if abs(delta) >= Decimal("1.00"):
                findings.append({
                    "kind": "gross_margin_change",
                    "severity": "warning" if delta < 0 else "info",
                    "currency_code": row["currency_code"],
                    "summary": (
                        f"Gross margin {'fell' if delta < 0 else 'rose'} by "
                        f"{abs(delta):.2f} percentage points."
                    ),
                    "current": {
                        "gross_margin_percent": str(
                            row["gross_margin_percent"].quantize(Decimal("0.01"))
                        )
                    },
                    "previous": {
                        "gross_margin_percent": str(
                            old["gross_margin_percent"].quantize(Decimal("0.01"))
                        )
                    },
                    "change_percentage_points": str(delta.quantize(Decimal("0.01"))),
                    "evidence": row["records"], "previous_evidence": old["records"],
                    "uncertainty": (
                        "This calculation uses only explicitly categorised direct costs "
                        "and recorded revenue."
                    ),
                })
    return {
        "periods": {
            "current": {"start": current_start.isoformat(), "end": current_end.isoformat()},
            "previous": {"start": previous_start.isoformat(), "end": previous_end.isoformat()},
        },
        "findings": findings,
        "message": "Changes are signals to investigate, not proof of causation.",
    }
