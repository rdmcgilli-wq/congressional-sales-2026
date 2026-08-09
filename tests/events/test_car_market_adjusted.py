from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from congressional_sales.events import car


def _prices(rows: dict[str, list[tuple]]) -> pl.DataFrame:
    frames = []
    for ticker, pairs in rows.items():
        n = len(pairs)
        frames.append(
            pl.DataFrame(
                {
                    "ticker": [ticker] * n, "date": [p[0] for p in pairs], "open": [1.0] * n,
                    "high": [1.0] * n, "low": [1.0] * n, "close": [p[1] for p in pairs],
                    "volume": [1.0] * n, "close_adj": [p[1] for p in pairs],
                }
            )
        )
    return pl.concat(frames)


def test_daily_return_computes_simple_return_from_prior_session():
    prices = _prices({"AAPL": [(date(2020, 1, 2), 100.0), (date(2020, 1, 3), 110.0)]})
    sessions = [date(2020, 1, 2), date(2020, 1, 3)]
    r = car.daily_return("AAPL", date(2020, 1, 3), prices, sessions)
    assert r == pytest.approx(0.10)


def test_daily_return_missing_prior_session_is_none():
    prices = _prices({"AAPL": [(date(2020, 1, 3), 110.0)]})
    sessions = [date(2020, 1, 3)]  # no prior session in the known calendar
    assert car.daily_return("AAPL", date(2020, 1, 3), prices, sessions) is None


def test_sessions_from_prices_reads_the_market_tickers_dates():
    prices = _prices({"AAPL": [(date(2020, 1, 2), 100.0)], "SPY": [(date(2020, 1, 2), 300.0), (date(2020, 1, 3), 303.0)]})
    assert car.sessions_from_prices(prices) == [date(2020, 1, 2), date(2020, 1, 3)]


def test_market_adjusted_car_nets_out_market_move():
    prices = _prices(
        {
            "AAPL": [(date(2020, 1, 2), 100.0), (date(2020, 1, 3), 110.0), (date(2020, 1, 6), 121.0)],
            "SPY": [(date(2020, 1, 2), 300.0), (date(2020, 1, 3), 303.0), (date(2020, 1, 6), 306.03)],
        }
    )
    # AAPL: +10% then +10% (cumulative sum of daily simple returns = 0.20).
    # SPY: +1% then +1% (cumulative sum = 0.02).
    got = car.market_adjusted_car("AAPL", date(2020, 1, 2), horizon=2, prices=prices)
    assert got == pytest.approx(0.20 - 0.02, abs=1e-6)


def test_market_adjusted_car_missing_window_data_is_none():
    prices = _prices({"AAPL": [(date(2020, 1, 2), 100.0)], "SPY": [(date(2020, 1, 2), 300.0)]})
    assert car.market_adjusted_car("AAPL", date(2020, 1, 2), horizon=5, prices=prices) is None


def test_market_adjusted_bhar_compounds_rather_than_sums():
    prices = _prices(
        {
            "AAPL": [(date(2020, 1, 2), 100.0), (date(2020, 1, 3), 110.0), (date(2020, 1, 6), 121.0)],
            "SPY": [(date(2020, 1, 2), 300.0), (date(2020, 1, 3), 303.0), (date(2020, 1, 6), 306.03)],
        }
    )
    got = car.market_adjusted_bhar("AAPL", date(2020, 1, 2), horizon=2, prices=prices)
    # AAPL compounds to 1.10*1.10 - 1 = 0.21; SPY compounds to 1.01*1.01 - 1 = 0.0201.
    assert got == pytest.approx(0.21 - 0.0201, abs=1e-6)
