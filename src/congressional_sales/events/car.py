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


def _price_on(ticker: str, d: date, prices: pl.DataFrame, _cache: dict[tuple[str, date], float] | None = None) -> float | None:
    """`_cache`, when given, must be price_lookup_cache(prices)'s own
    output -- a plain dict lookup instead of a `.filter()` scan. See
    price_lookup_cache's docstring for why this exists; semantics are
    identical either way (a (ticker, d) pair with no row is None)."""
    if _cache is not None:
        return _cache.get((ticker, d))
    rows = prices.filter((pl.col("ticker") == ticker) & (pl.col("date") == d))
    if rows.is_empty():
        return None
    return rows["close_adj"][0]


def price_lookup_cache(prices: pl.DataFrame) -> dict[tuple[str, date], float]:
    """Vectorized equivalent of repeated _price_on(ticker, d, prices)
    calls -- one dict built from the whole frame in a single pass, instead
    of a `.filter()` scan per (ticker, date) lookup. Confirmed live to
    matter: size_industry_matched_car/bhar's own _control_group_return
    calls daily_return (2 _price_on lookups) once per control ticker, per
    day in the event window -- up to 180 days x ~487 same-sector peers x 2
    lookups for a single "Money"-sector 180-day CAR, an entirely separate
    and far larger cost than the peer SIZE computation size_proxies_asof
    already fixes (that one scales with peer COUNT; this one scales with
    peer count x horizon LENGTH). Semantics are identical either way: a
    (ticker, date) pair with no row is simply absent from the dict,
    matching _price_on's own None for that case.
    """
    return dict(zip(zip(prices["ticker"].to_list(), prices["date"].to_list()), prices["close_adj"].to_list()))


def daily_return(
    ticker: str, d: date, prices: pl.DataFrame, sessions: list[date],
    _cache: dict[tuple[str, date], float] | None = None,
) -> float | None:
    prior = offset_within_days(sessions, d, -1)
    if prior is None:
        return None
    p0, p1 = _price_on(ticker, prior, prices, _cache=_cache), _price_on(ticker, d, prices, _cache=_cache)
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


def market_adjusted_car(
    ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, market_ticker: str = "SPY",
    price_cache: dict[tuple[str, date], float] | None = None,
) -> float | None:
    sessions = sessions_from_prices(prices, market_ticker)
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    total = 0.0
    for d in dates:
        r_t = daily_return(ticker, d, prices, sessions, _cache=price_cache)
        r_m = daily_return(market_ticker, d, prices, sessions, _cache=price_cache)
        if r_t is None or r_m is None:
            return None
        total += r_t - r_m
    return total


def market_adjusted_bhar(
    ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, market_ticker: str = "SPY",
    price_cache: dict[tuple[str, date], float] | None = None,
) -> float | None:
    sessions = sessions_from_prices(prices, market_ticker)
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    ticker_growth, market_growth = 1.0, 1.0
    for d in dates:
        r_t = daily_return(ticker, d, prices, sessions, _cache=price_cache)
        r_m = daily_return(market_ticker, d, prices, sessions, _cache=price_cache)
        if r_t is None or r_m is None:
            return None
        ticker_growth *= 1 + r_t
        market_growth *= 1 + r_m
    return (ticker_growth - 1) - (market_growth - 1)


def estimate_four_factor_betas(
    ticker: str, event_date: date, prices: pl.DataFrame, factors: pl.DataFrame, sessions: list[date],
    estimation_start_offset: int = -250, estimation_end_offset: int = -30, min_obs: int = 30,
    price_cache: dict[tuple[str, date], float] | None = None,
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
        r = daily_return(ticker, d, prices, sessions, _cache=price_cache)
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


def four_factor_car(
    ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, factors: pl.DataFrame, market_ticker: str = "SPY",
    price_cache: dict[tuple[str, date], float] | None = None,
) -> float | None:
    sessions = sessions_from_prices(prices, market_ticker)
    betas = estimate_four_factor_betas(ticker, event_date, prices, factors, sessions, price_cache=price_cache)
    if betas is None:
        return None
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    total = 0.0
    for d in dates:
        r = daily_return(ticker, d, prices, sessions, _cache=price_cache)
        f = factors.filter(pl.col("date") == d)
        if r is None or f.is_empty():
            return None
        actual_excess = r - f["rf"][0]
        total += actual_excess - _predicted_excess(betas, f)
    return total


def four_factor_bhar(
    ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, factors: pl.DataFrame, market_ticker: str = "SPY",
    price_cache: dict[tuple[str, date], float] | None = None,
) -> float | None:
    sessions = sessions_from_prices(prices, market_ticker)
    betas = estimate_four_factor_betas(ticker, event_date, prices, factors, sessions, price_cache=price_cache)
    if betas is None:
        return None
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    actual_growth, predicted_growth = 1.0, 1.0
    for d in dates:
        r = daily_return(ticker, d, prices, sessions, _cache=price_cache)
        f = factors.filter(pl.col("date") == d)
        if r is None or f.is_empty():
            return None
        actual_growth *= 1 + (r - f["rf"][0])
        predicted_growth *= 1 + _predicted_excess(betas, f)
    return (actual_growth - 1) - (predicted_growth - 1)


def size_proxy(
    ticker: str, as_of: date, prices: pl.DataFrame, sessions: list[date], lookback: int = 30,
    _cache: dict[str, float] | None = None,
) -> float | None:
    """`_cache`, when given, must be `size_proxies_asof(tickers, as_of, prices,
    sessions, lookback)`'s output for the SAME `as_of`/`lookback` this call
    would otherwise use -- a plain lookup then, no filtering at all. This
    exists purely as a performance escape hatch for a caller (see
    matched_control_tickers below) that needs this value for many tickers
    at the same `as_of`: computing it that way, once, is a single
    vectorized aggregation instead of one `.filter()` per ticker --
    confirmed live to matter at real full-universe scale, where a single
    FF12 sector can hold hundreds of peers (487 in this study's own
    "Money" sector) and this function was being called individually for
    every one of them, per horizon, per CAR/BHAR call, with no caching at
    all. Semantics are identical either way: a ticker with no rows in the
    window is None, whether that comes from an empty `.filter()` result or
    a cache miss.
    """
    if _cache is not None:
        return _cache.get(ticker)
    start = offset_within_days(sessions, as_of, -lookback)
    if start is None:
        return None
    window = [d for d in sessions if start <= d <= as_of]
    rows = prices.filter((pl.col("ticker") == ticker) & pl.col("date").is_in(window))
    if rows.is_empty():
        return None
    dollar_vol = (rows["close_adj"] * rows["volume"]).mean()
    return float(dollar_vol) if dollar_vol is not None else None


def size_proxies_asof(
    tickers: list[str], as_of: date, prices: pl.DataFrame, sessions: list[date], lookback: int = 30,
) -> dict[str, float]:
    """Vectorized equivalent of calling size_proxy(t, as_of, prices,
    sessions, lookback) for every t in `tickers` -- one filter + one
    group_by aggregation for the whole set, instead of one filter per
    ticker. Mathematically identical to the per-ticker version (same
    window, same mean of close_adj*volume per ticker); a ticker with no
    rows in the window is simply absent from the returned dict, matching
    size_proxy's own None for that case rather than a KeyError.
    """
    start = offset_within_days(sessions, as_of, -lookback)
    if start is None:
        return {}
    window = [d for d in sessions if start <= d <= as_of]
    subset = prices.filter(pl.col("ticker").is_in(tickers) & pl.col("date").is_in(window))
    if subset.is_empty():
        return {}
    agg = (
        subset.with_columns((pl.col("close_adj") * pl.col("volume")).alias("_dollar_vol"))
        .group_by("ticker")
        .agg(pl.col("_dollar_vol").mean().alias("_size_proxy"))
    )
    return dict(zip(agg["ticker"].to_list(), agg["_size_proxy"].to_list()))


def matched_control_tickers(
    ticker: str, event_date: date, prices: pl.DataFrame, sic: pl.DataFrame, sessions: list[date], n_deciles: int = 10,
    size_cache: dict[str, float] | None = None,
) -> list[str]:
    """`size_cache`, when given, must be size_proxies_asof(..., event_date,
    ...)'s output covering at least `ticker` and every same-sector peer --
    passed straight through to size_proxy's own `_cache` parameter for
    every internal call this function makes, turning what would otherwise
    be one `.filter()` per peer into a plain dict lookup. See size_proxy's
    docstring for why this exists; semantics are unchanged either way.
    """
    my_sic = sic.filter(pl.col("ticker") == ticker)
    if my_sic.is_empty():
        return []
    my_sector = ff12_industry(my_sic["sic_code"][0])

    peers = sic.filter(pl.col("ticker") != ticker)
    peer_sectors = peers.with_columns(pl.col("sic_code").map_elements(ff12_industry, return_dtype=pl.Utf8).alias("_sector"))
    same_sector = peer_sectors.filter(pl.col("_sector") == my_sector)["ticker"].to_list()
    if not same_sector:
        return []

    my_size = size_proxy(ticker, event_date, prices, sessions, _cache=size_cache)
    sized_peers = [(t, size_proxy(t, event_date, prices, sessions, _cache=size_cache)) for t in same_sector]
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


def _control_group_return(
    controls: list[str], d: date, prices: pl.DataFrame, sessions: list[date],
    price_cache: dict[tuple[str, date], float] | None = None,
) -> float | None:
    """The dominant real-scale cost this whole module was found to have,
    even after size_proxies_asof/size_cache fixed the peer SIZE
    computation: this function is called once per day in the event
    window, and (unfixed) called daily_return -- 2 uncached `.filter()`
    lookups -- once per control ticker on every single call. For a large
    same-sector control group (up to ~487 peers in this study's "Money"
    sector) and a 180-day horizon, that is up to 180 x 487 x 2 uncached
    filter scans for ONE transaction's ONE size/industry CAR -- confirmed
    live to still dominate wall time even with size_cache already wired
    in. `price_cache`, when given, must be price_lookup_cache(prices)'s
    own output, covering at minimum every ticker in `controls`.
    """
    if not controls:
        return None
    returns = [daily_return(t, d, prices, sessions, _cache=price_cache) for t in controls]
    returns = [r for r in returns if r is not None]
    if not returns:
        return None
    return sum(returns) / len(returns)


def size_industry_matched_car(
    ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, sic: pl.DataFrame, market_ticker: str = "SPY",
    controls: list[str] | None = None, price_cache: dict[tuple[str, date], float] | None = None,
) -> float | None:
    """`controls`, when given, must be matched_control_tickers(ticker,
    event_date, ...)'s own output for this exact ticker/event_date --
    passed straight through instead of recomputed. horizon does not
    affect the control group at all, so a caller computing both this and
    size_industry_matched_bhar across multiple horizons for the same
    transaction can (and, at real full-universe scale, must) compute the
    control group once and reuse it here 6 times over, rather than paying
    matched_control_tickers' own peer-scan cost redundantly on every call.

    `price_cache`, when given, must be price_lookup_cache(prices)'s own
    output -- see _control_group_return's docstring for why this matters
    far more here than in market_adjusted_car/four_factor_car: this
    function's day-loop calls daily_return once per CONTROL TICKER per
    day, not once total, so an uncached run pays O(horizon x len(controls))
    `.filter()` scans instead of O(horizon).
    """
    sessions = sessions_from_prices(prices, market_ticker)
    if controls is None:
        controls = matched_control_tickers(ticker, event_date, prices, sic, sessions)
    if not controls:
        return None
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    total = 0.0
    for d in dates:
        r_t = daily_return(ticker, d, prices, sessions, _cache=price_cache)
        r_c = _control_group_return(controls, d, prices, sessions, price_cache=price_cache)
        if r_t is None or r_c is None:
            return None
        total += r_t - r_c
    return total


def size_industry_matched_bhar(
    ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, sic: pl.DataFrame, market_ticker: str = "SPY",
    controls: list[str] | None = None, price_cache: dict[tuple[str, date], float] | None = None,
) -> float | None:
    """See size_industry_matched_car's docstring -- `controls` and
    `price_cache` are the same precomputed-reuse escape hatches, for the
    same reasons."""
    sessions = sessions_from_prices(prices, market_ticker)
    if controls is None:
        controls = matched_control_tickers(ticker, event_date, prices, sic, sessions)
    if not controls:
        return None
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    ticker_growth, control_growth = 1.0, 1.0
    for d in dates:
        r_t = daily_return(ticker, d, prices, sessions, _cache=price_cache)
        r_c = _control_group_return(controls, d, prices, sessions, price_cache=price_cache)
        if r_t is None or r_c is None:
            return None
        ticker_growth *= 1 + r_t
        control_growth *= 1 + r_c
    return (ticker_growth - 1) - (control_growth - 1)


def event_time_series(ticker: str, event_date: date, prices: pl.DataFrame, market_ticker: str = "SPY", pre: int = 30, post: int = 180) -> dict:
    """Baseline is offset 0 (the event date itself), not offset -pre --
    this makes series[+h] exactly equal market_adjusted_car(..., horizon=h),
    both being the sum of the same [+1, +h] daily abnormal returns. The
    pre-event side is a SEPARATE backward accumulation from offset -1 down
    to -pre, not a continuation of the forward walk -- the two directions
    share only the offset-0 baseline of 0.0, matching the standard
    event-study convention of centering the plot on the event date rather
    than on the start of the pre-event window.
    """
    sessions = sessions_from_prices(prices, market_ticker)
    result: dict[int, float | None] = {0: 0.0}

    cumulative, broken = 0.0, False
    for offset in range(1, post + 1):
        if broken:
            result[offset] = None
            continue
        d = offset_within_days(sessions, event_date, offset)
        if d is None:
            broken = True
            result[offset] = None
            continue
        r_t = daily_return(ticker, d, prices, sessions)
        r_m = daily_return(market_ticker, d, prices, sessions)
        if r_t is None or r_m is None:
            broken = True
            result[offset] = None
            continue
        cumulative += r_t - r_m
        result[offset] = cumulative

    cumulative, broken = 0.0, False
    for offset in range(-1, -pre - 1, -1):
        if broken:
            result[offset] = None
            continue
        d = offset_within_days(sessions, event_date, offset)
        if d is None:
            broken = True
            result[offset] = None
            continue
        r_t = daily_return(ticker, d, prices, sessions)
        r_m = daily_return(market_ticker, d, prices, sessions)
        if r_t is None or r_m is None:
            broken = True
            result[offset] = None
            continue
        cumulative += r_t - r_m
        result[offset] = cumulative

    return result
