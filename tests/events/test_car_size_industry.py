from __future__ import annotations

from datetime import date, timedelta

import polars as pl
import pytest

from congressional_sales.events import car

PRICE_SCHEMA = {
    "ticker": pl.Utf8, "date": pl.Date, "open": pl.Float64, "high": pl.Float64,
    "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64, "close_adj": pl.Float64,
}
SIC_SCHEMA = {"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8}


def _flat_price_series(ticker: str, sessions: list, start_price: float, daily_return: float, volume: float) -> pl.DataFrame:
    rows = []
    price = start_price
    for i, d in enumerate(sessions):
        if i > 0:
            price *= 1 + daily_return
        rows.append({"ticker": ticker, "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": price, "volume": volume, "close_adj": price})
    return pl.DataFrame(rows, schema=PRICE_SCHEMA)


def test_size_proxy_is_trailing_average_dollar_volume():
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(5)]
    prices = _flat_price_series("AAPL", sessions, 100.0, 0.0, volume=1000.0)
    # Every session: close_adj=100, volume=1000 -> dollar volume=100,000 exactly.
    got = car.size_proxy("AAPL", sessions[-1], prices, sessions, lookback=4)
    assert got == pytest.approx(100_000.0)


def test_matched_control_tickers_excludes_self_and_matches_sector_and_size():
    """4 same-sector peers (including the event ticker) split cleanly into
    2 deciles of 2 -- BIG1/BIG2 both ~10M in dollar volume, SMALL1/SMALL2
    both ~10K, a >100x gap with no ambiguous middle value, so bucket
    boundaries land on a whole-number split (4 names / 2 deciles = groups
    of exactly 2) rather than the fractional-boundary case a 3-peer/
    2-decile split would produce.

    Uses 40 sessions (not 10): matched_control_tickers calls size_proxy
    with its default lookback=30, and offset_within_days returns None
    (out of calendar) whenever fewer than lookback+1 sessions precede
    as_of. With only 10 sessions every size_proxy call would silently
    return None, tripping the "too few peers" fallback and masking the
    decile-bucketing path entirely (verified by hand: matched_control_tickers
    returned the full same-sector fallback set ['BIG2', 'SMALL1', 'SMALL2']
    instead of the intended ['BIG2'] against the original 10-session
    fixture). Values are flat/constant across sessions by construction, so
    lengthening the calendar does not change any ticker's dollar-volume
    figure or the >100x BIG/SMALL gap."""
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(40)]
    prices = pl.concat(
        [
            _flat_price_series("BIG1", sessions, 100.0, 0.0, volume=100_000.0),
            _flat_price_series("BIG2", sessions, 100.0, 0.0, volume=100_000.0),
            _flat_price_series("SMALL1", sessions, 100.0, 0.0, volume=100.0),
            _flat_price_series("SMALL2", sessions, 100.0, 0.0, volume=100.0),
            _flat_price_series("OTHERSECTOR", sessions, 100.0, 0.0, volume=100_000.0),
        ]
    )
    sic = pl.DataFrame(
        {
            "ticker": ["BIG1", "BIG2", "SMALL1", "SMALL2", "OTHERSECTOR"],
            "cik": [1, 2, 3, 4, 5],
            "sic_code": ["7372", "7372", "7372", "7372", "2911"],  # first 4 Business Equipment, last one Energy
            "sic_description": ["x"] * 5,
        },
        schema=SIC_SCHEMA,
    )
    controls = car.matched_control_tickers("BIG1", sessions[-1], prices, sic, sessions, n_deciles=2)
    assert "BIG1" not in controls  # never includes self
    assert "OTHERSECTOR" not in controls  # different sector, never a candidate
    assert "SMALL1" not in controls  # different size decile
    assert "SMALL2" not in controls  # different size decile
    assert controls == ["BIG2"]  # the one genuine same-sector, same-decile peer


def test_size_industry_matched_car_nets_out_the_control_groups_move():
    """size_industry_matched_car derives its own trading calendar via
    sessions_from_prices(prices, market_ticker="SPY") -- same convention as
    market_adjusted_car / four_factor_car (see
    tests/events/test_car_market_adjusted.py) -- so the price fixture must
    include a SPY row purely to anchor that calendar; SPY itself never
    enters the size/industry-matched calculation. Confirmed by hand: without
    it, sessions_from_prices returns [] and the function short-circuits to
    None regardless of EVENT/PEER1/PEER2 data."""
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(10)]
    prices = pl.concat(
        [
            _flat_price_series("EVENT", sessions, 100.0, 0.05, volume=100_000.0),   # +5%/day
            _flat_price_series("PEER1", sessions, 100.0, 0.01, volume=100_000.0),   # +1%/day
            _flat_price_series("PEER2", sessions, 100.0, 0.01, volume=100_000.0),   # +1%/day
            _flat_price_series("SPY", sessions, 300.0, 0.0, volume=1.0),            # calendar anchor only
        ]
    )
    sic = pl.DataFrame(
        {"ticker": ["EVENT", "PEER1", "PEER2"], "cik": [1, 2, 3], "sic_code": ["7372", "7372", "7372"], "sic_description": ["x"] * 3},
        schema=SIC_SCHEMA,
    )
    got = car.size_industry_matched_car("EVENT", sessions[4], horizon=3, prices=prices, sic=sic)
    # EVENT daily return over [+1,+3] is exactly 0.05 each session (flat compounding
    # rate by construction), control group average is exactly 0.01 each session ->
    # CAR = sum(0.05-0.01) * 3 = 0.12.
    assert got == pytest.approx(0.12, abs=1e-6)


def _dollar_vol_series(ticker: str, sessions: list, dollar_vol: float) -> pl.DataFrame:
    """price fixed at 1.0 so dollar volume == volume exactly, for clean
    hand-checkable arithmetic in the adversarial decile test below."""
    rows = [{"ticker": ticker, "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": dollar_vol, "close_adj": 1.0} for d in sessions]
    return pl.DataFrame(rows, schema=PRICE_SCHEMA)


def test_matched_control_tickers_handles_a_size_tie_straddling_a_fractional_bucket_boundary():
    """Adversarial case beyond the brief's clean 4-peer/2-decile fixture:
    5 entries (TARGET + 4 peers) into 3 deciles gives a genuinely
    fractional bucket_size = 5/3 = 1.6667, and two of the five share an
    IDENTICAL size that straddles the bucket 0/1 boundary -- exactly the
    ambiguity the original list.index(size)-based version got wrong.

    Sorted by (size, name) ascending, position -> bucket (floor(position /
    1.6667)):
      AAA0  dv=1_000  -> position 0 -> bucket 0
      MID_A dv=5_000  -> position 1 -> bucket 0   \\_ tied size, straddles
      MID_B dv=5_000  -> position 2 -> bucket 1   /   the 0/1 boundary
      ZZZ3  dv=9_000  -> position 3 -> bucket 1
      ZZZ4  dv=20_000 -> position 4 -> bucket 2

    TARGET = MID_B, the alphabetically-SECOND of the tied pair, which
    position-based ranking correctly places in bucket 1 (its only true
    peer there is ZZZ3). A value-based list.index(size) lookup would
    instead resolve BOTH MID_A and MID_B to index 1 (MID_A's position,
    since list.index returns the first match for a shared value),
    collapsing MID_B into bucket 0 and wrongly returning ["AAA0", "MID_A"]
    while missing its real bucket-1 peer ZZZ3 entirely -- verified by hand
    against the buggy formulation before this test was written.
    """
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(40)]
    sizes = {"AAA0": 1_000.0, "MID_A": 5_000.0, "MID_B": 5_000.0, "ZZZ3": 9_000.0, "ZZZ4": 20_000.0}
    prices = pl.concat([_dollar_vol_series(t, sessions, dv) for t, dv in sizes.items()])
    sic = pl.DataFrame(
        {"ticker": list(sizes), "cik": list(range(1, 6)), "sic_code": ["7372"] * 5, "sic_description": ["x"] * 5},
        schema=SIC_SCHEMA,
    )
    controls = car.matched_control_tickers("MID_B", sessions[-1], prices, sic, sessions, n_deciles=3)
    assert controls == ["ZZZ3"]


def test_matched_control_tickers_falls_back_to_full_sector_when_too_few_peers_for_deciles():
    """With only 2 same-sector peers and n_deciles=10, there aren't enough
    names to form meaningful deciles; the function must fall back to the
    full same-sector set rather than raising or returning an empty list."""
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(5)]
    prices = pl.concat(
        [
            _flat_price_series("X", sessions, 100.0, 0.0, volume=100.0),
            _flat_price_series("Y", sessions, 100.0, 0.0, volume=200.0),
        ]
    )
    sic = pl.DataFrame(
        {"ticker": ["X", "Y"], "cik": [1, 2], "sic_code": ["7372", "7372"], "sic_description": ["x", "x"]},
        schema=SIC_SCHEMA,
    )
    controls = car.matched_control_tickers("X", sessions[-1], prices, sic, sessions, n_deciles=10)
    assert controls == ["Y"]


def test_size_proxies_asof_matches_size_proxy_called_individually_per_ticker():
    """size_proxies_asof is a single vectorized aggregation meant to
    replace matched_control_tickers' original per-peer Python loop over
    size_proxy -- confirmed live to be the dominant remaining cost after
    sector-level price slicing (35s/row on a 200-transaction real-warehouse
    benchmark). It must produce EXACTLY the same values as calling
    size_proxy once per ticker, including correctly omitting a ticker with
    no rows in the lookback window rather than returning 0.0 for it."""
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(40)]
    prices = pl.concat(
        [
            _flat_price_series("BIG1", sessions, 100.0, 0.02, volume=100_000.0),
            _flat_price_series("BIG2", sessions, 50.0, -0.01, volume=250_000.0),
            _flat_price_series("SMALL1", sessions, 10.0, 0.0, volume=1_000.0),
        ]
    )
    # NOSUCHTICKER has no rows anywhere -- must be silently absent from the
    # result, matching size_proxy's own None return for a ticker with no data.
    as_of = sessions[-1]
    tickers = ["BIG1", "BIG2", "SMALL1", "NOSUCHTICKER"]
    got = car.size_proxies_asof(tickers, as_of, prices, sessions)
    expected = {
        t: car.size_proxy(t, as_of, prices, sessions)
        for t in tickers
        if car.size_proxy(t, as_of, prices, sessions) is not None
    }
    assert got.keys() == expected.keys()
    for t in expected:
        assert got[t] == pytest.approx(expected[t])


def test_matched_control_tickers_with_precomputed_size_cache_matches_uncached_result():
    """size_cache is a pure performance escape hatch (see car.py's own
    docstrings on size_proxy/matched_control_tickers) -- passing a
    precomputed cache must produce IDENTICAL output to the original
    per-peer .filter() computation, using the same adversarial fixture as
    the fractional-bucket-boundary test above so the equivalence claim
    covers the tie-straddling decile-assignment path too, not just a
    trivial case."""
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(40)]
    sizes = {"AAA0": 1_000.0, "MID_A": 5_000.0, "MID_B": 5_000.0, "ZZZ3": 9_000.0, "ZZZ4": 20_000.0}
    prices = pl.concat([_dollar_vol_series(t, sessions, dv) for t, dv in sizes.items()])
    sic = pl.DataFrame(
        {"ticker": list(sizes), "cik": list(range(1, 6)), "sic_code": ["7372"] * 5, "sic_description": ["x"] * 5},
        schema=SIC_SCHEMA,
    )
    uncached = car.matched_control_tickers("MID_B", sessions[-1], prices, sic, sessions, n_deciles=3)
    size_cache = car.size_proxies_asof(list(sizes), sessions[-1], prices, sessions)
    cached = car.matched_control_tickers("MID_B", sessions[-1], prices, sic, sessions, n_deciles=3, size_cache=size_cache)
    assert cached == uncached == ["ZZZ3"]


def test_size_industry_matched_car_and_bhar_with_precomputed_controls_match_uncached_result():
    """The `controls` parameter exists so attach_car_bhar can compute the
    control group once per transaction and reuse it across all 3 horizons
    x CAR/BHAR (6 calls total) instead of recomputing matched_control_tickers
    redundantly on every call -- confirmed live as a real, non-hypothetical
    cost. Passing a precomputed list must produce identical CAR and BHAR
    values to letting the function derive it internally."""
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(10)]
    prices = pl.concat(
        [
            _flat_price_series("EVENT", sessions, 100.0, 0.05, volume=100_000.0),
            _flat_price_series("PEER1", sessions, 100.0, 0.01, volume=100_000.0),
            _flat_price_series("PEER2", sessions, 100.0, 0.01, volume=100_000.0),
            _flat_price_series("SPY", sessions, 300.0, 0.0, volume=1.0),
        ]
    )
    sic = pl.DataFrame(
        {"ticker": ["EVENT", "PEER1", "PEER2"], "cik": [1, 2, 3], "sic_code": ["7372", "7372", "7372"], "sic_description": ["x"] * 3},
        schema=SIC_SCHEMA,
    )
    event_date = sessions[4]
    controls = car.matched_control_tickers("EVENT", event_date, prices, sic, car.sessions_from_prices(prices))

    car_uncached = car.size_industry_matched_car("EVENT", event_date, horizon=3, prices=prices, sic=sic)
    car_cached = car.size_industry_matched_car("EVENT", event_date, horizon=3, prices=prices, sic=sic, controls=controls)
    assert car_cached == pytest.approx(car_uncached)

    bhar_uncached = car.size_industry_matched_bhar("EVENT", event_date, horizon=3, prices=prices, sic=sic)
    bhar_cached = car.size_industry_matched_bhar("EVENT", event_date, horizon=3, prices=prices, sic=sic, controls=controls)
    assert bhar_cached == pytest.approx(bhar_uncached)


def test_size_industry_matched_car_and_bhar_with_price_cache_match_uncached_result():
    """price_cache (car.price_lookup_cache) is the fix for the cost that
    turned out to actually dominate: _control_group_return calls
    daily_return once per control ticker PER DAY in the event window, so
    an uncached run pays a `.filter()` scan for every (control, day) pair
    -- confirmed live to still take over an hour for 200 real transactions
    even with `controls` already precomputed once per transaction (this
    file's test above). Passing price_cache must produce identical
    output to the fully uncached computation."""
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(10)]
    prices = pl.concat(
        [
            _flat_price_series("EVENT", sessions, 100.0, 0.05, volume=100_000.0),
            _flat_price_series("PEER1", sessions, 100.0, 0.01, volume=100_000.0),
            _flat_price_series("PEER2", sessions, 100.0, 0.01, volume=100_000.0),
            _flat_price_series("SPY", sessions, 300.0, 0.0, volume=1.0),
        ]
    )
    sic = pl.DataFrame(
        {"ticker": ["EVENT", "PEER1", "PEER2"], "cik": [1, 2, 3], "sic_code": ["7372", "7372", "7372"], "sic_description": ["x"] * 3},
        schema=SIC_SCHEMA,
    )
    event_date = sessions[4]
    price_cache = car.price_lookup_cache(prices)

    car_uncached = car.size_industry_matched_car("EVENT", event_date, horizon=3, prices=prices, sic=sic)
    car_cached = car.size_industry_matched_car("EVENT", event_date, horizon=3, prices=prices, sic=sic, price_cache=price_cache)
    assert car_cached == pytest.approx(car_uncached)

    bhar_uncached = car.size_industry_matched_bhar("EVENT", event_date, horizon=3, prices=prices, sic=sic)
    bhar_cached = car.size_industry_matched_bhar("EVENT", event_date, horizon=3, prices=prices, sic=sic, price_cache=price_cache)
    assert bhar_cached == pytest.approx(bhar_uncached)
