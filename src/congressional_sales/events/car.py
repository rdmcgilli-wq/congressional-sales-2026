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
from ..sample.industry import ff12_industry


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


def estimate_four_factor_betas(
    ticker: str, event_date: date, prices: pl.DataFrame, factors: pl.DataFrame, sessions: list[date],
    estimation_start_offset: int = -250, estimation_end_offset: int = -30, min_obs: int = 30,
) -> dict | None:
    """OLS-fit alpha and factor loadings (mkt_rf, smb, hml, mom) on the
    security's daily excess returns over a pre-event estimation window,
    via numpy.linalg.lstsq. Returns None if fewer than min_obs valid days
    (with both a price and a factor row) exist in the window.
    """
    import numpy as np

    start = offset_within_days(sessions, event_date, estimation_start_offset)
    end = offset_within_days(sessions, event_date, estimation_end_offset)
    if start is None or end is None:
        return None
    window = [d for d in sessions if start <= d <= end]

    rows = []
    for d in window:
        r = daily_return(ticker, d, prices, sessions)
        f = factors.filter(pl.col("date") == d)
        if r is None or f.is_empty():
            continue
        rows.append((r - f["rf"][0], f["mkt_rf"][0], f["smb"][0], f["hml"][0], f["mom"][0]))
    if len(rows) < min_obs:
        return None

    y = np.array([r[0] for r in rows])
    X = np.array([[1.0, r[1], r[2], r[3], r[4]] for r in rows])
    coefs, *_ = np.linalg.lstsq(X, y, rcond=None)
    return {"alpha": float(coefs[0]), "beta_mkt": float(coefs[1]), "beta_smb": float(coefs[2]), "beta_hml": float(coefs[3]), "beta_mom": float(coefs[4])}


def _predicted_excess(betas: dict, f_row: pl.DataFrame) -> float:
    # Deliberately includes alpha in the predicted "normal" return: the
    # security's own average unexplained excess return over the
    # estimation window is treated as part of its expected performance
    # under the null, not as part of the abnormal signal being tested.
    # (Different from Model 3 / Task 19, where alpha itself is the test
    # statistic.)
    return (
        betas["alpha"] + betas["beta_mkt"] * f_row["mkt_rf"][0] + betas["beta_smb"] * f_row["smb"][0]
        + betas["beta_hml"] * f_row["hml"][0] + betas["beta_mom"] * f_row["mom"][0]
    )


def four_factor_car(ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, factors: pl.DataFrame, market_ticker: str = "SPY") -> float | None:
    sessions = sessions_from_prices(prices, market_ticker)
    betas = estimate_four_factor_betas(ticker, event_date, prices, factors, sessions)
    if betas is None:
        return None
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    total = 0.0
    for d in dates:
        r = daily_return(ticker, d, prices, sessions)
        f = factors.filter(pl.col("date") == d)
        if r is None or f.is_empty():
            return None
        actual_excess = r - f["rf"][0]
        total += actual_excess - _predicted_excess(betas, f)
    return total


def four_factor_bhar(ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, factors: pl.DataFrame, market_ticker: str = "SPY") -> float | None:
    sessions = sessions_from_prices(prices, market_ticker)
    betas = estimate_four_factor_betas(ticker, event_date, prices, factors, sessions)
    if betas is None:
        return None
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    actual_growth, predicted_growth = 1.0, 1.0
    for d in dates:
        r = daily_return(ticker, d, prices, sessions)
        f = factors.filter(pl.col("date") == d)
        if r is None or f.is_empty():
            return None
        actual_growth *= 1 + (r - f["rf"][0])
        predicted_growth *= 1 + _predicted_excess(betas, f)
    return (actual_growth - 1) - (predicted_growth - 1)


def size_proxy(ticker: str, as_of: date, prices: pl.DataFrame, sessions: list[date], lookback: int = 30) -> float | None:
    start = offset_within_days(sessions, as_of, -lookback)
    if start is None:
        return None
    window = [d for d in sessions if start <= d <= as_of]
    rows = prices.filter((pl.col("ticker") == ticker) & pl.col("date").is_in(window))
    if rows.is_empty():
        return None
    dollar_vol = (rows["close_adj"] * rows["volume"]).mean()
    return float(dollar_vol) if dollar_vol is not None else None


def matched_control_tickers(
    ticker: str, event_date: date, prices: pl.DataFrame, sic: pl.DataFrame, sessions: list[date], n_deciles: int = 10
) -> list[str]:
    my_sic = sic.filter(pl.col("ticker") == ticker)
    if my_sic.is_empty():
        return []
    my_sector = ff12_industry(my_sic["sic_code"][0])

    peers = sic.filter(pl.col("ticker") != ticker)
    peer_sectors = peers.with_columns(pl.col("sic_code").map_elements(ff12_industry, return_dtype=pl.Utf8).alias("_sector"))
    same_sector = peer_sectors.filter(pl.col("_sector") == my_sector)["ticker"].to_list()
    if not same_sector:
        return []

    my_size = size_proxy(ticker, event_date, prices, sessions)
    sized_peers = [(t, size_proxy(t, event_date, prices, sessions)) for t in same_sector]
    sized_peers = [(t, s) for t, s in sized_peers if s is not None]
    if my_size is None or len(sized_peers) < n_deciles:
        # Too few same-sector peers to form meaningful deciles -- fall back
        # to the full same-sector set rather than raising. This is the
        # "coarser buckets in sparsely-covered sectors" limitation
        # documented in the plan's Global Constraints.
        return same_sector

    # Rank every (ticker, size) pair -- including the event ticker itself
    # -- by size ascending, tie-breaking by ticker name for a deterministic
    # order. Bucket index = floor(position / bucket_size), bucket_size =
    # n / n_deciles. Ranking by POSITION rather than by looking up size
    # values matters here: two tickers can share an identical size (a
    # real possibility with a coarse dollar-volume proxy), and a
    # value-based lookup (e.g. list.index(size)) would silently collapse
    # every tied ticker onto whichever one happens to appear first in the
    # sorted list -- verified during planning to misclassify a same-sized
    # peer into the wrong bucket. Position-based ranking has no such
    # ambiguity because every entry, including ties, gets its own index.
    all_pairs = sorted(sized_peers + [(ticker, my_size)], key=lambda p: (p[1], p[0]))
    n = len(all_pairs)
    bucket_size = n / n_deciles
    my_position = next(i for i, (t, _) in enumerate(all_pairs) if t == ticker)
    my_bucket = int(my_position / bucket_size)
    return [
        t for i, (t, _) in enumerate(all_pairs)
        if t != ticker and int(i / bucket_size) == my_bucket
    ]


def _control_group_return(controls: list[str], d: date, prices: pl.DataFrame, sessions: list[date]) -> float | None:
    if not controls:
        return None
    returns = [daily_return(t, d, prices, sessions) for t in controls]
    returns = [r for r in returns if r is not None]
    if not returns:
        return None
    return sum(returns) / len(returns)


def size_industry_matched_car(ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, sic: pl.DataFrame, market_ticker: str = "SPY") -> float | None:
    sessions = sessions_from_prices(prices, market_ticker)
    controls = matched_control_tickers(ticker, event_date, prices, sic, sessions)
    if not controls:
        return None
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    total = 0.0
    for d in dates:
        r_t = daily_return(ticker, d, prices, sessions)
        r_c = _control_group_return(controls, d, prices, sessions)
        if r_t is None or r_c is None:
            return None
        total += r_t - r_c
    return total


def size_industry_matched_bhar(ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, sic: pl.DataFrame, market_ticker: str = "SPY") -> float | None:
    sessions = sessions_from_prices(prices, market_ticker)
    controls = matched_control_tickers(ticker, event_date, prices, sic, sessions)
    if not controls:
        return None
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    ticker_growth, control_growth = 1.0, 1.0
    for d in dates:
        r_t = daily_return(ticker, d, prices, sessions)
        r_c = _control_group_return(controls, d, prices, sessions)
        if r_t is None or r_c is None:
            return None
        ticker_growth *= 1 + r_t
        control_growth *= 1 + r_c
    return (ticker_growth - 1) - (control_growth - 1)
