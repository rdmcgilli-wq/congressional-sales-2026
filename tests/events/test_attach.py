from __future__ import annotations

from datetime import date, timedelta

import polars as pl
import pytest

from congressional_sales.events import attach

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
