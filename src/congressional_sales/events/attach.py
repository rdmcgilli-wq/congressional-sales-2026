"""Attaches every CAR/BHAR variant (3 horizons x 3 methods, both metrics)
to each sample row, plus two Model 2 (Task 19) control columns that have
no other producer in this codebase: industry (FF12, via SIC) and
prior_12mo_return (trailing ~252-session return). event_date_col defaults
to "transaction_date" -- see PRE_ANALYSIS_PLAN.md Section 6's primary
specification and the Global Constraints note on why this differs from
every point-in-time-gated filter elsewhere in this codebase."""

from __future__ import annotations

from bisect import bisect_right
from datetime import date

import polars as pl

from ..calendar import offset_within_days
from ..sample.industry import ff12_industry
from . import car

HORIZONS = (30, 90, 180)


def _anchor_session(sessions: list[date], d: date) -> date | None:
    """Most recent known session at or before d -- deliberately NOT
    offset_within_days(sessions, d, 0), whose n=0 behavior from a
    non-session date is a documented edge case (anchors to the session
    immediately BEFORE the first known session on/after d, not to the
    session at-or-before d itself). This is a plain as-of lookup."""
    i = bisect_right(sessions, d)
    if i == 0:
        return None
    return sessions[i - 1]


def _prior_12mo_return(ticker: str, event_date: date, prices: pl.DataFrame, sessions: list[date], lookback: int = 252) -> float | None:
    anchor = _anchor_session(sessions, event_date)
    if anchor is None:
        return None
    start = offset_within_days(sessions, anchor, -lookback)
    if start is None:
        return None
    p0 = car._price_on(ticker, start, prices)
    p1 = car._price_on(ticker, anchor, prices)
    if p0 is None or p1 is None or p0 == 0:
        return None
    return (p1 - p0) / p0


def attach_car_bhar(
    sample: pl.DataFrame, prices: pl.DataFrame, factors: pl.DataFrame, sic: pl.DataFrame,
    event_date_col: str = "transaction_date",
) -> pl.DataFrame:
    sic_lookup = dict(zip(sic["ticker"].to_list(), sic["sic_code"].to_list()))
    sessions = car.sessions_from_prices(prices)
    out_rows = []
    for row in sample.iter_rows(named=True):
        ticker, event_date = row["ticker"], row[event_date_col]
        result = dict(row)
        for h in HORIZONS:
            result[f"car_market_{h}"] = car.market_adjusted_car(ticker, event_date, h, prices)
            result[f"bhar_market_{h}"] = car.market_adjusted_bhar(ticker, event_date, h, prices)
            result[f"car_four_factor_{h}"] = car.four_factor_car(ticker, event_date, h, prices, factors)
            result[f"bhar_four_factor_{h}"] = car.four_factor_bhar(ticker, event_date, h, prices, factors)
            result[f"car_size_industry_{h}"] = car.size_industry_matched_car(ticker, event_date, h, prices, sic)
            result[f"bhar_size_industry_{h}"] = car.size_industry_matched_bhar(ticker, event_date, h, prices, sic)
        result["industry"] = ff12_industry(sic_lookup.get(ticker))
        result["prior_12mo_return"] = _prior_12mo_return(ticker, event_date, prices, sessions)
        out_rows.append(result)
    return pl.DataFrame(out_rows)
