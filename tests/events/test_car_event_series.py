from __future__ import annotations

from datetime import date, timedelta

import polars as pl
import pytest

from congressional_sales.events import car

PRICE_SCHEMA = {
    "ticker": pl.Utf8, "date": pl.Date, "open": pl.Float64, "high": pl.Float64,
    "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64, "close_adj": pl.Float64,
}


def test_event_time_series_baseline_is_zero_at_the_event_date():
    """Baseline is offset 0 (the event date), not offset -pre -- so
    series[+10] must equal market_adjusted_car's own [+1,+10] definition
    exactly (both sum the identical 10 post-event terms), and series[-k]
    is a SEPARATE backward accumulation from offset -1 down to -k, not a
    continuation of the forward walk. An earlier version of this test
    baselined at -pre and asserted series[10] == market_adjusted_car(...),
    which is wrong: baselining at -pre would make series[10] the sum of
    20 terms (offsets -9 through +10), not the 10 post-event terms
    market_adjusted_car computes -- caught by hand-tracing the two
    definitions against each other before this task was implemented."""
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(50)]
    rows = []
    aapl_price, spy_price = 100.0, 100.0
    for i, d in enumerate(sessions):
        if i > 0:
            aapl_price *= 1.01
            spy_price *= 1.001
        rows.append({"ticker": "AAPL", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": aapl_price, "volume": 1.0, "close_adj": aapl_price})
        rows.append({"ticker": "SPY", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": spy_price, "volume": 1.0, "close_adj": spy_price})
    prices = pl.DataFrame(rows, schema=PRICE_SCHEMA)

    series = car.event_time_series("AAPL", sessions[20], prices, pre=10, post=10)
    assert series[0] == 0.0
    assert series[10] == pytest.approx(car.market_adjusted_car("AAPL", sessions[20], 10, prices), abs=1e-9)


def test_event_time_series_none_after_a_gap():
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(15)]
    rows = [{"ticker": "AAPL", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1.0, "close_adj": 100.0} for d in sessions]
    rows += [{"ticker": "SPY", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1.0, "close_adj": 100.0} for d in sessions]
    prices = pl.DataFrame(rows, schema=PRICE_SCHEMA)

    series = car.event_time_series("AAPL", sessions[5], prices, pre=5, post=20)
    assert series[9] is not None   # within the 15-day fixture
    assert series[10] is None      # walks off the known calendar
    assert series[15] is None      # stays None after the gap
