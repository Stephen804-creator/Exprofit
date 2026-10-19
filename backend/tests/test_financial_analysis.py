from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.services.financial_analysis import compare_periods, profitability, summarize_transactions


def record(
    direction, amount, category=None, currency="NGN", status="posted", day=date(2026, 10, 1)
):
    return SimpleNamespace(
        id="record-1", direction=direction, amount=Decimal(amount), category=category,
        currency_code=currency, status=status, transaction_date=day,
        description="Test record",
    )


def test_summary_keeps_currency_buckets_separate_and_excludes_drafts():
    result = summarize_transactions([
        record("income", "100.00"),
        record("expense", "20.00", "Transport"),
        record("income", "5.00", currency="USD"),
        record("income", "900.00", status="draft"),
    ])
    assert len(result["currencies"]) == 2
    ngn = next(row for row in result["currencies"] if row["currency_code"] == "NGN")
    assert ngn["income"] == "100.00"
    assert ngn["expenses"] == "20.00"
    assert ngn["net_cash_movement"] == "80.00"
    assert result["posted_record_count"] == 3


def test_profitability_does_not_assume_all_expenses_are_direct_costs():
    result = profitability([
        record("income", "200.00"),
        record("expense", "40.00", "COGS"),
        record("expense", "20.00", "Transport"),
    ])["currencies"][0]
    assert result["revenue"] == "200.00"
    assert result["direct_costs"] == "40.00"
    assert result["gross_profit"] == "160.00"
    assert result["gross_margin_percent"] == "80.00"


def test_profitability_is_unknown_without_direct_cost_data():
    result = profitability(
        [record("income", "200.00"), record("expense", "40.00", "Rent")]
    )["currencies"][0]
    assert result["gross_profit"] is None
    assert result["gross_margin_percent"] is None
    assert result["direct_cost_data_available"] is False


def test_margin_guard_reports_revenue_change_with_evidence_and_uncertainty():
    current = [record("income", "150.00", day=date(2026, 10, 10))]
    previous = [record("income", "100.00", day=date(2026, 9, 10))]
    result = compare_periods(
        current, previous, date(2026, 10, 1), date(2026, 10, 10),
        date(2026, 9, 1), date(2026, 9, 30),
    )
    finding = next(item for item in result["findings"] if item["kind"] == "revenue_change")
    assert finding["change"] == "50.00"
    assert finding["evidence"][0]["description"] == "Test record"
    assert "do not establish its cause" in finding["uncertainty"]


def test_category_totals_are_separated_by_currency():
    result = summarize_transactions([
        record("expense", "100.00", "Transport", currency="NGN"),
        record("expense", "10.00", "Transport", currency="USD"),
    ])
    rows = [row for row in result["categories"] if row["category"] == "Transport"]
    assert {(row["currency_code"], row["expenses"]) for row in rows} == {
        ("NGN", "100.00"),
        ("USD", "10.00"),
    }


def test_margin_guard_reports_activity_that_disappears_in_current_period():
    previous = [record("income", "100.00", currency="USD", day=date(2026, 9, 10))]
    result = compare_periods(
        [], previous, date(2026, 10, 1), date(2026, 10, 10),
        date(2026, 9, 1), date(2026, 9, 30),
    )
    finding = next(
        item for item in result["findings"]
        if item["kind"] == "previous_currency_activity"
    )
    assert finding["currency_code"] == "USD"
    assert finding["current"] is None
    assert finding["previous_evidence"][0]["amount"] == "100.00"
