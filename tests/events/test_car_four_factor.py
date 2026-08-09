from __future__ import annotations

from datetime import date, timedelta

import polars as pl
import pytest

from congressional_sales.events import car

PRICE_SCHEMA = {
    "ticker": pl.Utf8, "date": pl.Date, "open": pl.Float64, "high": pl.Float64,
    "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64, "close_adj": pl.Float64,
}
FACTOR_SCHEMA = {"date": pl.Date, "mkt_rf": pl.Float64, "smb": pl.Float64, "hml": pl.Float64, "mom": pl.Float64, "rf": pl.Float64}


def _synthetic(n: int, true_alpha: float, true_beta_mkt: float):
    """n consecutive daily sessions where excess_return is EXACTLY
    true_alpha + true_beta_mkt*mkt_rf (true betas on smb/hml/mom are 0),
    built from genuinely non-collinear factor columns (different modular
    periods) so the regression design matrix has full rank and OLS on
    this noiseless data recovers the true coefficients exactly."""
    base = date(2020, 1, 1)
    sessions = [base + timedelta(days=i) for i in range(n)]
    price = 100.0
    price_rows = [{"ticker": "T", "date": sessions[0], "open": 1.0, "high": 1.0, "low": 1.0, "close": price, "volume": 1.0, "close_adj": price}]
    factor_rows = []
    for i in range(1, n):
        mkt_rf, smb, hml, mom, rf = 0.001 * (i % 7), 0.001 * (i % 5), 0.001 * (i % 3), 0.001 * (i % 11), 0.0001
        excess = true_alpha + true_beta_mkt * mkt_rf
        daily_r = excess + rf
        price = price * (1 + daily_r)
        price_rows.append({"ticker": "T", "date": sessions[i], "open": 1.0, "high": 1.0, "low": 1.0, "close": price, "volume": 1.0, "close_adj": price})
        factor_rows.append({"date": sessions[i], "mkt_rf": mkt_rf, "smb": smb, "hml": hml, "mom": mom, "rf": rf})
    prices = pl.DataFrame(price_rows, schema=PRICE_SCHEMA)
    factors = pl.DataFrame(factor_rows, schema=FACTOR_SCHEMA)
    return sessions, prices, factors


def test_estimate_four_factor_betas_recovers_known_coefficients_on_noiseless_data():
    sessions, prices, factors = _synthetic(n=40, true_alpha=0.02, true_beta_mkt=1.5)
    betas = car.estimate_four_factor_betas(
        "T", sessions[-1], prices, factors, sessions,
        estimation_start_offset=-(len(sessions) - 1), estimation_end_offset=-1, min_obs=30,
    )
    assert betas is not None
    assert betas["alpha"] == pytest.approx(0.02, abs=1e-6)
    assert betas["beta_mkt"] == pytest.approx(1.5, abs=1e-6)
    assert betas["beta_smb"] == pytest.approx(0.0, abs=1e-6)
    assert betas["beta_hml"] == pytest.approx(0.0, abs=1e-6)
    assert betas["beta_mom"] == pytest.approx(0.0, abs=1e-6)


def test_estimate_four_factor_betas_insufficient_data_is_none():
    sessions, prices, factors = _synthetic(n=15, true_alpha=0.02, true_beta_mkt=1.5)
    betas = car.estimate_four_factor_betas(
        "T", sessions[-1], prices, factors, sessions,
        estimation_start_offset=-(len(sessions) - 1), estimation_end_offset=-1, min_obs=30,
    )
    assert betas is None


def test_four_factor_car_is_zero_when_event_window_matches_the_fitted_model_exactly():
    """If the event window's actual returns follow the SAME true model the
    betas were estimated from, abnormal return must be ~0 at every session
    -- this is the sanity check that predicted_t actually uses alpha, not
    just the factor loadings.

    four_factor_car uses estimate_four_factor_betas' DEFAULT estimation
    offsets (-250, -30 sessions), so event_date must sit far enough into
    the session list for that full 250-session lookback to resolve
    against offset_within_days rather than returning None. With n=300 and
    event_date = sessions[280]: the estimation window resolves to
    sessions[30..250] (221 observations, comfortably above min_obs=30)
    and the event window (horizon=3) resolves to sessions[281..283].
    Both ranges sit entirely inside the synthetic data's noiseless region
    (every session index 1..299 follows excess = true_alpha +
    true_beta_mkt*mkt_rf exactly, by construction of _synthetic) and do
    not overlap each other.

    _synthetic only ever builds price rows for ticker "T" -- there is no
    separate "SPY" row in this single-ticker fixture. four_factor_car's
    default market_ticker="SPY" (inherited from market_adjusted_car in
    Task 14) would make sessions_from_prices filter for a ticker that
    doesn't exist here, yielding an empty session list and an
    unconditional None -- independent of any window-offset math. Passing
    market_ticker="T" makes the synthetic ticker double as its own
    calendar anchor, which is correct for this single-ticker fixture.
    """
    sessions, prices, factors = _synthetic(n=300, true_alpha=0.02, true_beta_mkt=1.5)
    event_date = sessions[280]
    got = car.four_factor_car("T", event_date, horizon=3, prices=prices, factors=factors, market_ticker="T")
    assert got == pytest.approx(0.0, abs=1e-6)
