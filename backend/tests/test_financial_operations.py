from datetime import date

from app.api.routes.financial_operations import _advance_due, _due_dates_in_window, _safe_csv_cell


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



def test_recurring_dates_stop_at_schedule_end_date() -> None:
    assert _due_dates_in_window(
        date(2026, 10, 20), "weekly", date(2026, 10, 23), date(2026, 11, 20), date(2026, 11, 3)
    ) == [date(2026, 10, 27), date(2026, 11, 3)]


def test_expired_recurring_schedule_produces_no_future_dates() -> None:
    assert _due_dates_in_window(
        date(2026, 1, 1), "monthly", date(2026, 10, 23), date(2026, 11, 23), date(2026, 2, 1)
    ) == []


def test_recurring_date_window_includes_start_and_end_boundaries() -> None:
    assert _due_dates_in_window(
        date(2026, 10, 23), "weekly", date(2026, 10, 23), date(2026, 11, 6)
    ) == [date(2026, 10, 23), date(2026, 10, 30), date(2026, 11, 6)]
