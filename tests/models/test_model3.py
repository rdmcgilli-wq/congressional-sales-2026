from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from congressional_sales.models import model3

PRICE_SCHEMA = {
    "ticker": pl.Utf8, "date": pl.Date, "open": pl.Float64, "high": pl.Float64,
    "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64, "close_adj": pl.Float64,
}
FACTOR_SCHEMA = {"date": pl.Date, "mkt_rf": pl.Float64, "smb": pl.Float64, "hml": pl.Float64, "mom": pl.Float64, "rf": pl.Float64}


def test_monthly_factor_returns_compounds_daily_to_monthly():
    factors = pl.DataFrame(
        [
            {"date": date(2020, 1, 2), "mkt_rf": 0.01, "smb": 0.0, "hml": 0.0, "mom": 0.0, "rf": 0.0001},
            {"date": date(2020, 1, 3), "mkt_rf": 0.01, "smb": 0.0, "hml": 0.0, "mom": 0.0, "rf": 0.0001},
        ],
        schema=FACTOR_SCHEMA,
    )
    got = model3.monthly_factor_returns(factors)
    assert got.height == 1
    assert got["mkt_rf"][0] == pytest.approx(1.01 * 1.01 - 1, abs=1e-9)


def test_monthly_stock_return_compounds_within_month():
    prices = pl.DataFrame(
        [
            {"ticker": "T", "date": date(2020, 1, 2), "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1.0, "close_adj": 100.0},
            {"ticker": "T", "date": date(2020, 1, 31), "open": 1.0, "high": 1.0, "low": 1.0, "close": 110.0, "volume": 1.0, "close_adj": 110.0},
        ],
        schema=PRICE_SCHEMA,
    )
    got = model3.monthly_stock_return("T", date(2020, 1, 1), prices)
    assert got == pytest.approx(0.10)


def test_calendar_time_portfolio_is_short_so_a_rising_stock_gives_a_negative_return():
    prices = pl.DataFrame(
        [
            {"ticker": "T", "date": date(2020, 3, 1), "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1.0, "close_adj": 100.0},
            {"ticker": "T", "date": date(2020, 3, 31), "open": 1.0, "high": 1.0, "low": 1.0, "close": 120.0, "volume": 1.0, "close_adj": 120.0},
        ],
        schema=PRICE_SCHEMA,
    )
    got = model3.calendar_time_portfolio_returns([("T", date(2020, 2, 15))], prices, holding_months=3)
    # T's disclosure is Feb 15 -> it's short-held for March/April/May.
    march = got.filter(pl.col("month") == date(2020, 3, 1))
    assert march["portfolio_return"][0] == pytest.approx(-0.20, abs=1e-6)
    assert march["n_names"][0] == 1


def test_calendar_time_portfolio_excludes_months_outside_the_holding_window():
    prices = pl.DataFrame(
        [{"ticker": "T", "date": date(2020, 1, 1), "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1.0, "close_adj": 100.0}],
        schema=PRICE_SCHEMA,
    )
    got = model3.calendar_time_portfolio_returns([("T", date(2020, 2, 15))], prices, holding_months=3)
    assert got.filter(pl.col("month") == date(2020, 1, 1)).is_empty()  # before the disclosure
    assert got.filter(pl.col("month") == date(2020, 6, 1)).is_empty()  # after the 3-month window
