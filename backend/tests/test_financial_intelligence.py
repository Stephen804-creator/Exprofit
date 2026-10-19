from decimal import Decimal

from app.services.financial_intelligence import (
    build_verified_facts,
    explain_verified_facts,
    simulate_scenario,
)


def test_verified_ai_facts_omit_transaction_descriptions_and_identifiers():
    summary = {
        "currencies": [{"currency_code": "NGN", "income": "100.00"}],
        "profitability": {"currencies": []},
    }
    comparison = {
        "periods": {"current": {"start": "2026-10-01", "end": "2026-10-30"}},
        "findings": [{
            "kind": "revenue_change", "severity": "warning", "currency_code": "NGN",
            "summary": "Revenue fell.", "uncertainty": "Cause is not proven.",
            "evidence": [{"id": "private-id", "description": "Customer phone number 08000000000"}],
        }],
    }
    facts = build_verified_facts(summary, comparison)
    serialized = str(facts)
    assert "private-id" not in serialized
    assert "08000000000" not in serialized
    assert facts["findings"][0]["summary"] == "Revenue fell."


def test_rule_explanation_states_uncertainty():
    result = explain_verified_facts({"findings": [{
        "summary": "Recorded revenue decreased.", "currency_code": "NGN",
        "uncertainty": "Records do not prove the cause.",
    }]})
    assert "Recorded revenue decreased." in result
    assert "do not prove the cause" in result
    assert "Suggested next step" in result


def test_simulator_applies_explicit_assumptions_without_mutating_input():
    base = {"currencies": [{
        "currency_code": "NGN", "revenue": "100000.00", "direct_costs": "40000.00",
        "gross_profit": "60000.00", "direct_cost_data_available": True,
    }]}
    result = simulate_scenario(base, Decimal("10"), Decimal("20"), Decimal("5"))
    row = result["results"][0]
    assert row["estimated_revenue"] == "132000.00"
    assert row["estimated_direct_costs"] == "50400.00"
    assert row["estimated_gross_profit"] == "81600.00"
    assert row["estimated_gross_margin_percent"] == "61.82"
    assert base["currencies"][0]["revenue"] == "100000.00"
    assert any("No transaction" in item for item in result["assumptions"])


def test_simulator_does_not_invent_profit_without_direct_cost_records():
    result = simulate_scenario(
        {"currencies": [{
            "currency_code": "NGN", "revenue": "1000.00", "direct_costs": "0.00",
            "gross_profit": None, "direct_cost_data_available": False,
        }]},
        Decimal("0"), Decimal("0"), Decimal("0"),
    )
    assert result["results"][0]["estimated_gross_profit"] is None
    assert result["results"][0]["estimated_gross_margin_percent"] is None
