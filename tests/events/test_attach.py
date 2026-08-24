from __future__ import annotations

from datetime import date, timedelta

import polars as pl
import pytest

from congressional_sales.events import attach, car

PRICE_SCHEMA = {
    "ticker": pl.Utf8, "date": pl.Date, "open": pl.Float64, "high": pl.Float64,
    "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64, "close_adj": pl.Float64,
}
FACTOR_SCHEMA = {"date": pl.Date, "mkt_rf": pl.Float64, "smb": pl.Float64, "hml": pl.Float64, "mom": pl.Float64, "rf": pl.Float64}
SIC_SCHEMA = {"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8}
SAMPLE_SCHEMA = {
    "ticker": pl.Utf8, "bioguide_id": pl.Utf8, "transaction": pl.Utf8,
    "transaction_date": pl.Date, "report_date": pl.Date,
}


def test_attach_car_bhar_adds_all_18_columns_and_uses_transaction_date_by_default():
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(250)]
    price_rows, factor_rows = [], []
    price = 100.0
    for i, d in enumerate(sessions):
        if i > 0:
            price *= 1.001
        price_rows.append({"ticker": "AAPL", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": price, "volume": 1000.0, "close_adj": price})
        price_rows.append({"ticker": "SPY", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1000.0, "close_adj": 100.0})
        factor_rows.append({"date": d, "mkt_rf": 0.0002 * (i % 5), "smb": 0.0001, "hml": 0.0001, "mom": 0.0001, "rf": 0.0001})
    prices = pl.DataFrame(price_rows, schema=PRICE_SCHEMA)
    factors = pl.DataFrame(factor_rows, schema=FACTOR_SCHEMA)
    sic = pl.DataFrame({"ticker": ["AAPL"], "cik": [320193], "sic_code": ["3571"], "sic_description": ["x"]}, schema=SIC_SCHEMA)
    sample = pl.DataFrame(
        {
            "ticker": ["AAPL"], "bioguide_id": ["A1"], "transaction": ["Sale"],
            "transaction_date": [sessions[200]], "report_date": [sessions[210]],
        },
        schema=SAMPLE_SCHEMA,
    )

    out = attach.attach_car_bhar(sample, prices, factors, sic)
    expected_cols = {
        f"{metric}_{method}_{h}"
        for metric in ("car", "bhar")
        for method in ("market", "four_factor", "size_industry")
        for h in (30, 90, 180)
    }
    assert expected_cols.issubset(set(out.columns))
    # AAPL rises every session, so the market-adjusted CAR (which nets out
    # SPY's exactly-flat price) must be positive.
    assert out["car_market_30"][0] > 0
    # SIC 3571 (Electronic Computers) is Business Equipment in FF12.
    assert out["industry"][0] == "Business Equipment"
    # AAPL grows 0.1%/session; ~252 sessions before day 200 is day -52 (out
    # of the fixture's range), so this specific case has no valid trailing
    # 12-month window and prior_12mo_return must be None, not a wrong value
    # computed from a truncated window -- the fixture is deliberately too
    # short to have real 12mo history, exercising the "not enough data"
    # path, not the happy path (a second test below covers the happy path).
    assert out["prior_12mo_return"][0] is None


def test_attach_car_bhar_computes_prior_12mo_return_when_enough_history_exists():
    sessions = [date(2019, 1, 1) + timedelta(days=i) for i in range(500)]
    price_rows = []
    price = 100.0
    for i, d in enumerate(sessions):
        if i > 0:
            price *= 1.001
        price_rows.append({"ticker": "AAPL", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": price, "volume": 1000.0, "close_adj": price})
        price_rows.append({"ticker": "SPY", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1000.0, "close_adj": 100.0})
    prices = pl.DataFrame(price_rows, schema=PRICE_SCHEMA)
    factors = pl.DataFrame(schema=FACTOR_SCHEMA)
    sic = pl.DataFrame({"ticker": ["AAPL"], "cik": [320193], "sic_code": ["3571"], "sic_description": ["x"]}, schema=SIC_SCHEMA)
    # event at session index 400 -- 252 sessions of real prior history exist (indices 148..400).
    sample = pl.DataFrame(
        {
            "ticker": ["AAPL"], "bioguide_id": ["A1"], "transaction": ["Sale"],
            "transaction_date": [sessions[400]], "report_date": [sessions[410]],
        },
        schema=SAMPLE_SCHEMA,
    )
    out = attach.attach_car_bhar(sample, prices, factors, sic)
    assert out["prior_12mo_return"][0] is not None
    # 0.1%/session compounded over exactly 252 sessions: (1.001**252 - 1).
    assert out["prior_12mo_return"][0] == pytest.approx(1.001 ** 252 - 1, abs=1e-6)


def test_attach_car_bhar_prior_12mo_return_anchors_backward_from_a_non_session_event_date():
    # Review finding: none of the other tests pass an event_date that is
    # NOT itself a known trading session -- a realistic case in production
    # (STOCK Act disclosures can be dated/reported on a weekend), and
    # exactly the scenario _anchor_session's bisect_right (vs. a plain
    # offset_within_days(..., d, 0) call) exists to handle correctly.
    # Sessions here are weekdays only; the event date is a real Saturday
    # with no price row at all, so attach_car_bhar must anchor backward to
    # the prior Friday before computing prior_12mo_return, not treat the
    # Saturday as a session (which would silently misalign the whole
    # 252-session lookback window) or crash.
    start = date(2019, 1, 1)  # a Tuesday
    calendar_days = [start + timedelta(days=i) for i in range(700)]
    sessions = [d for d in calendar_days if d.weekday() < 5]
    assert len(sessions) > 450  # comfortably enough weekday sessions for a 252-session lookback

    friday_idx = next(i for i, d in enumerate(sessions) if i >= 260 and d.weekday() == 4)
    friday = sessions[friday_idx]
    saturday = friday + timedelta(days=1)
    assert saturday.weekday() == 5
    assert saturday not in sessions  # no price row exists for this date at all
    monday_idx = friday_idx + 1  # the session bisect_right would land on if it (wrongly) anchored forward

    # A constant per-session growth rate would make every 252-session
    # window return the identical ratio regardless of which day anchors
    # it -- unable to distinguish "anchored to Friday" from "anchored to
    # (wrongly) the following Monday". Break that degeneracy with a
    # one-off price jump on the Monday session only: this changes the
    # ratio if and only if the anchor is (incorrectly) resolved forward
    # to Monday instead of backward to Friday.
    price_rows = []
    price = 100.0
    for i, d in enumerate(sessions):
        if i > 0:
            price *= 1.001
        row_price = price * 3.0 if i == monday_idx else price
        price_rows.append({"ticker": "AAPL", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": row_price, "volume": 1000.0, "close_adj": row_price})
        price_rows.append({"ticker": "SPY", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1000.0, "close_adj": 100.0})
    prices = pl.DataFrame(price_rows, schema=PRICE_SCHEMA)
    factors = pl.DataFrame(schema=FACTOR_SCHEMA)
    sic = pl.DataFrame({"ticker": ["AAPL"], "cik": [320193], "sic_code": ["3571"], "sic_description": ["x"]}, schema=SIC_SCHEMA)

    sample = pl.DataFrame(
        {
            "ticker": ["AAPL"], "bioguide_id": ["A1"], "transaction": ["Sale"],
            "transaction_date": [saturday], "report_date": [saturday],
        },
        schema=SAMPLE_SCHEMA,
    )
    out = attach.attach_car_bhar(sample, prices, factors, sic)
    # Correctly anchored to Friday, prior_12mo_return is untouched by the
    # Monday-only price jump (neither the Friday nor Friday-252 endpoint
    # is Monday) -- the plain 252-session compounded return.
    assert out["prior_12mo_return"][0] == pytest.approx(1.001 ** 252 - 1, abs=1e-6)
    # If _anchor_session instead (wrongly) anchored forward to Monday, p1
    # would pick up the 3x jump and the ratio would come out roughly
    # 3x too high -- confirm the correct value is not confoundable with
    # that wrong-anchor value.
    wrong_anchor_return = (price * 3.0 - price_rows[2 * (monday_idx - 252)]["close"]) / price_rows[2 * (monday_idx - 252)]["close"]
    assert out["prior_12mo_return"][0] != pytest.approx(wrong_anchor_return, abs=1e-6)


def test_attach_car_bhar_industry_is_other_for_unknown_sic():
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(10)]
    price_rows = [
        {"ticker": "ZZZ", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0, "close_adj": 1.0}
        for d in sessions
    ] + [
        {"ticker": "SPY", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0, "close_adj": 1.0}
        for d in sessions
    ]
    prices = pl.DataFrame(price_rows, schema=PRICE_SCHEMA)
    factors = pl.DataFrame(schema=FACTOR_SCHEMA)
    sic = pl.DataFrame(schema=SIC_SCHEMA)  # ZZZ has no SIC entry at all
    sample = pl.DataFrame(
        {
            "ticker": ["ZZZ"], "bioguide_id": ["A1"], "transaction": ["Sale"],
            "transaction_date": [sessions[5]], "report_date": [sessions[5]],
        },
        schema=SAMPLE_SCHEMA,
    )
    out = attach.attach_car_bhar(sample, prices, factors, sic)
    assert out["industry"][0] == "Other"


def test_attach_car_bhar_report_date_variant_uses_report_date_as_event_date():
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(250)]
    price_rows = []
    for i, d in enumerate(sessions):
        price_rows.append({"ticker": "AAPL", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0 + i, "volume": 1000.0, "close_adj": 100.0 + i})
        price_rows.append({"ticker": "SPY", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1000.0, "close_adj": 100.0})
    prices = pl.DataFrame(price_rows, schema=PRICE_SCHEMA)
    factors = pl.DataFrame(schema=FACTOR_SCHEMA)
    sic = pl.DataFrame({"ticker": ["AAPL"], "cik": [320193], "sic_code": ["3571"], "sic_description": ["x"]}, schema=SIC_SCHEMA)
    # transaction_date is early (little forward runway before the fixture ends);
    # report_date is later still with room for a 30-day window. Only the
    # report_date variant should have a non-null car_market_30.
    sample = pl.DataFrame(
        {
            "ticker": ["AAPL"], "bioguide_id": ["A1"], "transaction": ["Sale"],
            "transaction_date": [sessions[245]], "report_date": [sessions[200]],
        },
        schema=SAMPLE_SCHEMA,
    )
    by_transaction_date = attach.attach_car_bhar(sample, prices, factors, sic, event_date_col="transaction_date")
    by_report_date = attach.attach_car_bhar(sample, prices, factors, sic, event_date_col="report_date")
    assert by_transaction_date["car_market_30"][0] is None  # not enough forward sessions from day 245 of 250
    assert by_report_date["car_market_30"][0] is not None  # plenty of forward sessions from day 200


def _sector_fixture():
    """EVENT + two real same-sector peers (SIC 7372, Business Equipment)
    with DIFFERENT dollar volumes, plus UNRELATED in a different sector
    (SIC 2911, Energy) and SPY as the market anchor -- enough peer
    structure for size_industry_matched_car's own decile logic to have
    something real to match against, unlike this file's other fixtures
    (single-ticker, no SIC peers at all)."""
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(100)]
    price_rows = []
    for i, d in enumerate(sessions):
        price_rows.append({"ticker": "EVENT", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0 + i, "volume": 100_000.0, "close_adj": 100.0 + i})
        price_rows.append({"ticker": "PEERA", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 50.0 + i * 0.5, "volume": 90_000.0, "close_adj": 50.0 + i * 0.5})
        price_rows.append({"ticker": "PEERB", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 80.0 + i * 0.8, "volume": 110_000.0, "close_adj": 80.0 + i * 0.8})
        price_rows.append({"ticker": "UNRELATED", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 200.0 - i, "volume": 500_000.0, "close_adj": 200.0 - i})
        price_rows.append({"ticker": "SPY", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 300.0, "volume": 1_000_000.0, "close_adj": 300.0})
    prices = pl.DataFrame(price_rows, schema=PRICE_SCHEMA)
    sic = pl.DataFrame(
        {
            "ticker": ["EVENT", "PEERA", "PEERB", "UNRELATED"], "cik": [1, 2, 3, 4],
            "sic_code": ["7372", "7372", "7372", "2911"], "sic_description": ["x"] * 4,
        },
        schema=SIC_SCHEMA,
    )
    return sessions, prices, sic


def test_attach_car_bhar_size_industry_matches_the_unsliced_computation_exactly():
    # THE regression test for the real full-universe performance fix:
    # attach_car_bhar now slices `prices` per sector before calling
    # car.py's functions (confirmed live -- passing the full, unsliced
    # equity_eod table through unchanged made the real pipeline run a
    # plausible multi-day computation, dominated by size_industry_matched_
    # car/bhar's own peer-group scan, up to 487 tickers in this study's
    # real "Money" sector, recomputed per horizon per metric per
    # transaction with no caching at all). This must not change the
    # computed value -- car.py itself is untouched, only what gets passed
    # to it -- so the sliced result is compared directly against calling
    # car.size_industry_matched_car with the FULL, unsliced frame.
    sessions, prices, sic = _sector_fixture()
    factors = pl.DataFrame(schema=FACTOR_SCHEMA)
    sample = pl.DataFrame(
        {
            "ticker": ["EVENT"], "bioguide_id": ["A1"], "transaction": ["Sale"],
            "transaction_date": [sessions[40]], "report_date": [sessions[40]],
        },
        schema=SAMPLE_SCHEMA,
    )
    out = attach.attach_car_bhar(sample, prices, factors, sic)
    expected = car.size_industry_matched_car("EVENT", sessions[40], 30, prices, sic)
    assert out["car_size_industry_30"][0] == pytest.approx(expected)
    assert expected is not None  # sanity: the fixture actually exercises real peer matching, not a None short-circuit


def test_attach_car_bhar_sector_slice_extends_for_a_ticker_with_no_sic_classification():
    # A ticker absent from `sic` entirely still needs its OWN price rows
    # for the market/four-factor methods -- the sector slicer's "extra"
    # append path (module docstring) is what supplies them, since such a
    # ticker is never part of any sector's precomputed peer set.
    sessions, prices, sic = _sector_fixture()
    # NOCLASS has price history but is deliberately absent from `sic`.
    extra_rows = [
        {"ticker": "NOCLASS", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 10.0 + i * 0.1, "volume": 1000.0, "close_adj": 10.0 + i * 0.1}
        for i, d in enumerate(sessions)
    ]
    prices = pl.concat([prices, pl.DataFrame(extra_rows, schema=PRICE_SCHEMA)])
    factors = pl.DataFrame(schema=FACTOR_SCHEMA)
    sample = pl.DataFrame(
        {
            "ticker": ["NOCLASS"], "bioguide_id": ["A1"], "transaction": ["Sale"],
            "transaction_date": [sessions[40]], "report_date": [sessions[40]],
        },
        schema=SAMPLE_SCHEMA,
    )
    out = attach.attach_car_bhar(sample, prices, factors, sic)
    expected = car.market_adjusted_car("NOCLASS", sessions[40], 30, prices)
    assert expected is not None
    assert out["car_market_30"][0] == pytest.approx(expected)
    assert out["industry"][0] == "Other"  # unclassified -> ff12_industry(None)'s own fallback, unaffected by slicing
