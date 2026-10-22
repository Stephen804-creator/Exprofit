from datetime import date

from app.api.routes.financial_operations import _advance_due


def test_monthly_schedule_clamps_to_month_end() -> None:
    assert _advance_due(date(2026, 1, 31), "monthly") == date(2026, 2, 28)
    assert _advance_due(date(2028, 1, 31), "monthly") == date(2028, 2, 29)


def test_monthly_schedule_keeps_day_when_possible() -> None:
    assert _advance_due(date(2026, 3, 15), "monthly") == date(2026, 4, 15)


def test_yearly_schedule_handles_leap_day() -> None:
    assert _advance_due(date(2028, 2, 29), "yearly") == date(2029, 2, 28)


def test_weekly_schedule_advances_seven_days() -> None:
    assert _advance_due(date(2026, 10, 22), "weekly") == date(2026, 10, 29)
