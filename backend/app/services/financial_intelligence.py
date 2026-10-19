"""Evidence-grounded financial explanations and non-persistent what-if calculations."""

from decimal import Decimal
from typing import Any

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def _money(value: Decimal) -> str:
    return str(value.quantize(CENT))


def build_verified_facts(summary: dict[str, Any], comparison: dict[str, Any]) -> dict[str, Any]:
    """Build a small, structured context from server-calculated results only.

    Transaction descriptions and identifiers are deliberately omitted from AI context.
    """
    findings = []
    for item in comparison.get("findings", [])[:8]:
        findings.append({
            key: item.get(key)
            for key in (
                "kind", "severity", "currency_code", "summary", "current",
                "previous", "change", "change_percentage_points", "uncertainty",
            )
            if item.get(key) is not None
        })
    return {
        "periods": comparison.get("periods", {}),
        "currency_summaries": summary.get("currencies", []),
        "profitability": summary.get("profitability", {}).get("currencies", []),
        "findings": findings,
        "limitations": [
            "Only posted transactions recorded in Exprofit are included.",
            "Currencies are separate and are never converted or added together.",
            "Gross profit is unavailable when recognised direct-cost data is missing.",
            "Period changes are evidence for investigation, not proof of cause.",
        ],
    }


def explain_verified_facts(facts: dict[str, Any]) -> str:
    """Produce a deterministic explanation without relying on an AI provider."""
    findings = facts.get("findings", [])
    if not findings:
        return (
            "No material change was identified by the current comparison rules. "
            "This does not prove that performance was unchanged: records may be missing "
            "or there may not be enough comparable activity."
        )
    lines = ["What the recorded data shows:"]
    for finding in findings[:6]:
        currency = finding.get("currency_code", "")
        summary = str(finding.get("summary", "A financial change was detected."))
        rendered = f"- {summary}"
        if currency and currency not in summary:
            rendered += f" ({currency})"
        lines.append(rendered)
        uncertainty = finding.get("uncertainty")
        if uncertainty:
            lines.append(f"  Limitation: {uncertainty}")
    lines.append(
        "Suggested next step: open the corresponding MarginGuard evidence, check the "
        "underlying entries and compare like-for-like periods before deciding what caused "
        "the change."
    )
    return "\n".join(lines)


def simulate_scenario(
    profitability: dict[str, Any],
    price_change_percent: Decimal,
    volume_change_percent: Decimal,
    unit_cost_change_percent: Decimal,
) -> dict[str, Any]:
    """Apply explicit hypothetical percentage assumptions without changing stored records."""
    price_factor = Decimal("1") + price_change_percent / Decimal("100")
    volume_factor = Decimal("1") + volume_change_percent / Decimal("100")
    cost_factor = Decimal("1") + unit_cost_change_percent / Decimal("100")
    results = []
    for base in profitability.get("currencies", []):
        revenue = Decimal(base["revenue"])
        direct_costs = Decimal(base["direct_costs"])
        estimated_revenue = (revenue * price_factor * volume_factor).quantize(CENT)
        estimated_costs = (direct_costs * cost_factor * volume_factor).quantize(CENT)
        has_cost_data = base.get("direct_cost_data_available") is True
        gross_profit = estimated_revenue - estimated_costs if has_cost_data else None
        margin = (
            (gross_profit / estimated_revenue * Decimal("100")).quantize(CENT)
            if gross_profit is not None and estimated_revenue > 0
            else None
        )
        results.append({
            "currency_code": base["currency_code"],
            "baseline_revenue": _money(revenue),
            "baseline_direct_costs": _money(direct_costs),
            "baseline_gross_profit": base.get("gross_profit"),
            "estimated_revenue": _money(estimated_revenue),
            "estimated_direct_costs": _money(estimated_costs),
            "estimated_gross_profit": _money(gross_profit) if gross_profit is not None else None,
            "estimated_gross_margin_percent": _money(margin) if margin is not None else None,
            "direct_cost_data_available": has_cost_data,
        })
    return {
        "results": results,
        "assumptions": [
            "Recorded period revenue is the baseline; this is a scenario, not a forecast.",
            "Price and volume changes are assumed to apply uniformly to all revenue.",
            "Direct costs are assumed to change with both unit cost and volume.",
            "Other operating costs, taxes, stock limits, demand response, and "
            "seasonality are not modelled.",
            "No transaction or financial record is created or modified.",
        ],
    }
