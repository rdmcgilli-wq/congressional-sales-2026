"""Attaches every CAR/BHAR variant (3 horizons x 3 methods, both metrics)
to each sample row, plus two Model 2 (Task 19) control columns that have
no other producer in this codebase: industry (FF12, via SIC) and
prior_12mo_return (trailing ~252-session return). event_date_col defaults
to "transaction_date" -- see PRE_ANALYSIS_PLAN.md Section 6's primary
specification and the Global Constraints note on why this differs from
every point-in-time-gated filter elsewhere in this codebase.

Every events.car function is a pure function of whatever `prices` frame
it is handed, and does its own internal `.filter()` per price lookup
(see car.py's own module docstring on why -- deliberately no coupling to
a global warehouse). This module's own caller therefore controls the
single biggest cost in the whole pipeline: confirmed live against the
real full-universe warehouse (12M+ equity_eod rows), passing that frame
through unsliced turned the size/industry-matched method's own peer-group
scan (up to 487 same-sector tickers in this study's real "Money" sector,
recomputed independently for every horizon and every CAR/BHAR call on
every transaction) into a genuinely multi-day computation, not the
"slow but not vectorized" cost the rest of this codebase's comments
already flag. `_sector_price_slicer` below fixes this at the one call
site that matters, without touching car.py at all: every price lookup
this function makes for a given transaction is against a slice
containing only that transaction's own ticker, the market ticker, and
its full FF12 sector's peer set -- built once per sector, cached, and
reused across every transaction that shares it, since every function in
car.py accepts `prices: pl.DataFrame` and does not care how large or
small the frame handed to it is.

Sector-slicing alone was confirmed live to be INSUFFICIENT: a 200-row
benchmark against the real warehouse still took 35s/row (~8.8 days
extrapolated to the full 21,717-row screened sample), because
size_industry_matched_car/bhar's control group -- unaffected by horizon --
was being recomputed independently 6 times per transaction (3 horizons x
CAR/BHAR), and each of those calls re-scanned every same-sector peer's
price history one ticker at a time (car.size_proxy's own `.filter()` per
call). attach_car_bhar now computes the control group and the size
proxies it depends on exactly ONCE per transaction -- car.size_proxies_asof
for the vectorized batch computation, passed into car.matched_control_tickers
as `size_cache`, and the resulting `controls` list passed into both
size_industry_matched_car and size_industry_matched_bhar for all 3
horizons -- rather than letting either recompute per call.

A THIRD, larger fix was needed on top of both of the above, confirmed
live the same way: even with the control group computed once and its
peer SIZES vectorized, a fresh 200-row benchmark ran for well over an
hour without finishing. The remaining, and far larger, cost was
car._control_group_return -- called once per DAY in the event window,
and for every call, looping over every control ticker with an uncached
`.filter()` scan (via daily_return/_price_on) for each one. For a large
sector (up to ~487 peers) and a 180-day horizon that is up to
180 x 487 x 2 scans per size/industry CAR call, PER TRANSACTION -- a cost
that scales with horizon LENGTH x peer COUNT, categorically larger than
the peer-size cost size_cache already fixed (which only scales with peer
count). `_price_cache_for` below builds one ticker -> close_adj lookup
dict per sector (car.price_lookup_cache, memoized the same way
`slice_for`'s own slices are), and every car.* call this function makes
is now passed that dict as `price_cache` -- turning every one of those
`.filter()` scans, throughout car.py (not just the size/industry path),
into a plain dict lookup."""

from __future__ import annotations

from bisect import bisect_right
from datetime import date

import polars as pl

from ..calendar import offset_within_days
from ..sample.industry import ff12_industry
from . import car

HORIZONS = (30, 90, 180)


def _sector_price_slicer(prices: pl.DataFrame, sic: pl.DataFrame, market_ticker: str = "SPY"):
    """Returns ticker -> a much smaller prices slice containing that
    ticker, `market_ticker`, and every ticker sharing its FF12 sector (the
    full candidate peer set matched_control_tickers draws from) -- built
    and cached once per SECTOR (at most 12, per industry.py's own FF12
    scheme), not once per ticker or once per call, since every ticker in
    the same sector needs the identical peer slice and this function is
    invoked once per transaction per horizon per metric.

    A ticker with no SIC classification at all (or one whose own rows
    were not already captured by its sector's precomputed peer set) still
    needs ITS OWN price rows for the market/four-factor methods even
    though it will never itself appear as a size/industry peer -- the
    slice is extended with that ticker's own rows on demand rather than
    assumed present, so no method silently loses data for an
    unclassified ticker.
    """
    sic_lookup = dict(zip(sic["ticker"].to_list(), sic["sic_code"].to_list()))
    tickers_by_sector: dict[str, set[str]] = {}
    for ticker, sic_code in sic_lookup.items():
        tickers_by_sector.setdefault(ff12_industry(sic_code), set()).add(ticker)

    sector_slice_cache: dict[str, pl.DataFrame] = {}
    sector_ticker_set_cache: dict[str, set[str]] = {}
    full_slice_cache: dict[str, pl.DataFrame] = {}

    def slice_for(ticker: str) -> pl.DataFrame:
        sector = ff12_industry(sic_lookup.get(ticker))
        if sector not in sector_slice_cache:
            peers = tickers_by_sector.get(sector, set()) | {market_ticker}
            sector_slice_cache[sector] = prices.filter(pl.col("ticker").is_in(list(peers)))
            sector_ticker_set_cache[sector] = peers
        if ticker in sector_ticker_set_cache[sector]:
            return sector_slice_cache[sector]
        cache_key = f"{sector}:{ticker}"
        if cache_key not in full_slice_cache:
            extra = prices.filter(pl.col("ticker") == ticker)
            full_slice_cache[cache_key] = (
                pl.concat([sector_slice_cache[sector], extra], how="vertical_relaxed")
                if not extra.is_empty()
                else sector_slice_cache[sector]
            )
        return full_slice_cache[cache_key]

    return slice_for


def _price_cache_for(slice_for):
    """Wraps `slice_for` (above) with a SECOND cache -- ticker -> the
    car.price_lookup_cache(...) dict for that ticker's own slice --
    keyed by the Python object id of whatever DataFrame slice_for
    returns rather than by re-deriving its own sector/cache-key logic.
    This is safe because slice_for already returns the IDENTICAL object
    reference for every ticker sharing a sector (its own internal
    caching), so id() naturally coincides exactly where sector-sharing
    should make it coincide, and differs exactly where it shouldn't --
    with no need to duplicate slice_for's cache-key bookkeeping here.

    This exists because sector-slicing alone (slice_for) and size_cache
    alone (see attach_car_bhar) were BOTH confirmed live to be
    insufficient: size_industry_matched_car/bhar's own day-loop calls
    daily_return -- an uncached `.filter()` scan -- once per control
    ticker per day in the event window. For a large sector (up to ~487
    peers) and a 180-day horizon, that is up to 180 x 487 x 2 scans
    PER TRANSACTION even with the slice already reduced to just that
    sector -- confirmed live to still make a 200-row benchmark run for
    well over an hour. See car.py's price_lookup_cache and
    _control_group_return docstrings for the full accounting.
    """
    cache_by_slice_id: dict[int, dict] = {}

    def cache_for(ticker: str) -> dict:
        ticker_prices = slice_for(ticker)
        key = id(ticker_prices)
        if key not in cache_by_slice_id:
            cache_by_slice_id[key] = car.price_lookup_cache(ticker_prices)
        return cache_by_slice_id[key]

    return cache_for


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


def _prior_12mo_return(
    ticker: str, event_date: date, prices: pl.DataFrame, sessions: list[date], lookback: int = 252,
    price_cache: dict[tuple[str, date], float] | None = None,
) -> float | None:
    anchor = _anchor_session(sessions, event_date)
    if anchor is None:
        return None
    start = offset_within_days(sessions, anchor, -lookback)
    if start is None:
        return None
    p0 = car._price_on(ticker, start, prices, _cache=price_cache)
    p1 = car._price_on(ticker, anchor, prices, _cache=price_cache)
    if p0 is None or p1 is None or p0 == 0:
        return None
    return (p1 - p0) / p0


def attach_car_bhar(
    sample: pl.DataFrame, prices: pl.DataFrame, factors: pl.DataFrame, sic: pl.DataFrame,
    event_date_col: str = "transaction_date",
) -> pl.DataFrame:
    sic_lookup = dict(zip(sic["ticker"].to_list(), sic["sic_code"].to_list()))
    sessions = car.sessions_from_prices(prices)
    slice_for = _sector_price_slicer(prices, sic)
    cache_for = _price_cache_for(slice_for)
    out_rows = []
    for row in sample.iter_rows(named=True):
        ticker, event_date = row["ticker"], row[event_date_col]
        ticker_prices = slice_for(ticker)
        price_cache = cache_for(ticker)
        # Computed once per transaction, not once per horizon x metric: the
        # control group and the size proxies it's built from don't depend on
        # horizon at all. size_cache is the vectorized equivalent of every
        # size_proxy() call matched_control_tickers would otherwise make one
        # peer at a time -- confirmed live to be a real, though not the
        # dominant, remaining cost after sector-slicing alone. See car.py's
        # size_proxies_asof/matched_control_tickers docstrings.
        size_cache = car.size_proxies_asof(ticker_prices["ticker"].unique().to_list(), event_date, ticker_prices, sessions)
        controls = car.matched_control_tickers(ticker, event_date, ticker_prices, sic, sessions, size_cache=size_cache)
        result = dict(row)
        for h in HORIZONS:
            result[f"car_market_{h}"] = car.market_adjusted_car(ticker, event_date, h, ticker_prices, price_cache=price_cache)
            result[f"bhar_market_{h}"] = car.market_adjusted_bhar(ticker, event_date, h, ticker_prices, price_cache=price_cache)
            result[f"car_four_factor_{h}"] = car.four_factor_car(ticker, event_date, h, ticker_prices, factors, price_cache=price_cache)
            result[f"bhar_four_factor_{h}"] = car.four_factor_bhar(ticker, event_date, h, ticker_prices, factors, price_cache=price_cache)
            result[f"car_size_industry_{h}"] = car.size_industry_matched_car(
                ticker, event_date, h, ticker_prices, sic, controls=controls, price_cache=price_cache
            )
            result[f"bhar_size_industry_{h}"] = car.size_industry_matched_bhar(
                ticker, event_date, h, ticker_prices, sic, controls=controls, price_cache=price_cache
            )
        result["industry"] = ff12_industry(sic_lookup.get(ticker))
        result["prior_12mo_return"] = _prior_12mo_return(ticker, event_date, ticker_prices, sessions, price_cache=price_cache)
        out_rows.append(result)
    return pl.DataFrame(out_rows)
