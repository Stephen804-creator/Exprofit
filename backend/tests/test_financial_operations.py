from datetime import date

from app.api.routes.financial_operations import _advance_due, _safe_csv_cell


def test_monthly_schedule_clamps_to_month_end() -> None:
    assert _advance_due(date(2026, 1, 31), "monthly") == date(2026, 2, 28)
    assert _advance_due(date(2028, 1, 31), "monthly") == date(2028, 2, 29)


def test_monthly_schedule_keeps_day_when_possible() -> None:
    assert _advance_due(date(2026, 3, 15), "monthly") == date(2026, 4, 15)


def test_yearly_schedule_handles_leap_day() -> None:
    assert _advance_due(date(2028, 2, 29), "yearly") == date(2029, 2, 28)


def test_weekly_schedule_advances_seven_days() -> None:
    assert _advance_due(date(2026, 10, 22), "weekly") == date(2026, 10, 29)



def test_csv_export_escapes_spreadsheet_formula_prefixes() -> None:
    assert _safe_csv_cell("=1+1") == "'=1+1"
    assert _safe_csv_cell("  @SUM(A1:A2)") == "'  @SUM(A1:A2)"
    assert _safe_csv_cell("+cmd") == "'+cmd"
    assert _safe_csv_cell("-cmd") == "'-cmd"


def test_csv_export_preserves_normal_text_and_empty_values() -> None:
    assert _safe_csv_cell("Market sales") == "Market sales"
    assert _safe_csv_cell(None) == ""
