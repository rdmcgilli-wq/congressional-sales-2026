from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from congressional_sales import calendar, storage


def _seed_spy(dates: list[date]) -> None:
    n = len(dates)
    df = pl.DataFrame(
        {
            "ticker": ["SPY"] * n, "date": dates, "open": [1.0] * n, "high": [1.0] * n,
            "low": [1.0] * n, "close": [1.0] * n, "volume": [1.0] * n, "close_adj": [1.0] * n,
        }
    )
    storage.write("equity_eod", df, key_cols=["ticker", "date"])


def test_trading_days_are_sorted_and_deduped():
    _seed_spy([date(2024, 1, 3), date(2024, 1, 2), date(2024, 1, 2)])
    assert calendar.trading_days() == [date(2024, 1, 2), date(2024, 1, 3)]


def test_offset_trading_day_skips_the_weekend_gap():
    """Regression: a naive calendar-day t+1 would land on Saturday. The real
    next SESSION after Friday 2024-01-05 is Monday 2024-01-08."""
    _seed_spy([date(2024, 1, 4), date(2024, 1, 5), date(2024, 1, 8), date(2024, 1, 9)])
    assert calendar.offset_trading_day(date(2024, 1, 5), 1) == date(2024, 1, 8)


def test_offset_trading_day_negative_looks_backward():
    _seed_spy([date(2024, 1, 4), date(2024, 1, 5), date(2024, 1, 8)])
    assert calendar.offset_trading_day(date(2024, 1, 8), -1) == date(2024, 1, 5)


def test_offset_trading_day_zero_requires_d_itself_be_a_session():
    _seed_spy([date(2024, 1, 4), date(2024, 1, 5)])
    assert calendar.offset_trading_day(date(2024, 1, 4), 0) == date(2024, 1, 4)


def test_offset_trading_day_past_the_known_calendar_returns_none():
    _seed_spy([date(2024, 1, 4), date(2024, 1, 5)])
    assert calendar.offset_trading_day(date(2024, 1, 5), 5) is None


def test_offset_trading_day_from_a_non_session_date_anchors_forward():
    """d itself need not be a session (e.g. a Saturday disclosure date) --
    offsetting from it walks forward to the first known session on/after d,
    then applies n-1 additional sessions for n>=1."""
    _seed_spy([date(2024, 1, 4), date(2024, 1, 5), date(2024, 1, 8)])
    # Saturday 2024-01-06 -> first session on/after it is Monday 01-08 (n=1 effectively free);
    # +1 more session from there would be off the known calendar -> None for n=2,
    # but n=1 lands exactly on 01-08.
    assert calendar.offset_trading_day(date(2024, 1, 6), 1) == date(2024, 1, 8)


def test_is_trading_day():
    _seed_spy([date(2024, 1, 4), date(2024, 1, 5)])
    assert calendar.is_trading_day(date(2024, 1, 4)) is True
    assert calendar.is_trading_day(date(2024, 1, 6)) is False
