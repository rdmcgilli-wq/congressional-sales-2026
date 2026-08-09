"""CAR/BHAR event-study engine, PRE_ANALYSIS_PLAN.md Section 6.

Horizon h means trading sessions [+1, +h] from the event date, using
calendar.offset_trading_day exclusively -- never raw date arithmetic. This
IS the t+1 discipline Section 11 calls the most common silent failure.

Deliberately does NOT call calendar.offset_trading_day (the global,
storage-backed variant): this module derives its own session list from
whatever `prices` DataFrame the caller passes in (via
sessions_from_prices), and offsets against that local list using the pure
calendar.offset_within_days core. Reaching for the global warehouse-backed
calendar here would create a hidden coupling bug -- a caller's local test
fixture (or, in production, a specific pre-filtered prices frame) would no
longer agree with whatever happens to be in the global warehouse at call
time. Every function below is therefore a pure function of its arguments.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from ..calendar import offset_within_days


def sessions_from_prices(prices: pl.DataFrame, market_ticker: str = "SPY") -> list[date]:
    return prices.filter(pl.col("ticker") == market_ticker)["date"].unique().sort().to_list()


def _price_on(ticker: str, d: date, prices: pl.DataFrame) -> float | None:
    rows = prices.filter((pl.col("ticker") == ticker) & (pl.col("date") == d))
    if rows.is_empty():
        return None
    return rows["close_adj"][0]


def daily_return(ticker: str, d: date, prices: pl.DataFrame, sessions: list[date]) -> float | None:
    prior = offset_within_days(sessions, d, -1)
    if prior is None:
        return None
    p0, p1 = _price_on(ticker, prior, prices), _price_on(ticker, d, prices)
    if p0 is None or p1 is None or p0 == 0:
        return None
    return (p1 - p0) / p0


def _window_dates(event_date: date, horizon: int, sessions: list[date]) -> list[date] | None:
    dates = []
    for k in range(1, horizon + 1):
        d = offset_within_days(sessions, event_date, k)
        if d is None:
            return None
        dates.append(d)
    return dates


def market_adjusted_car(ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, market_ticker: str = "SPY") -> float | None:
    sessions = sessions_from_prices(prices, market_ticker)
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    total = 0.0
    for d in dates:
        r_t = daily_return(ticker, d, prices, sessions)
        r_m = daily_return(market_ticker, d, prices, sessions)
        if r_t is None or r_m is None:
            return None
        total += r_t - r_m
    return total


def market_adjusted_bhar(ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, market_ticker: str = "SPY") -> float | None:
    sessions = sessions_from_prices(prices, market_ticker)
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    ticker_growth, market_growth = 1.0, 1.0
    for d in dates:
        r_t = daily_return(ticker, d, prices, sessions)
        r_m = daily_return(market_ticker, d, prices, sessions)
        if r_t is None or r_m is None:
            return None
        ticker_growth *= 1 + r_t
        market_growth *= 1 + r_m
    return (ticker_growth - 1) - (market_growth - 1)
