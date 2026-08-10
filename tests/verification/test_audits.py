from __future__ import annotations

from datetime import date

import polars as pl

from congressional_sales.verification import audits


def test_nan_audit_counts_nulls_per_car_column():
    sample = pl.DataFrame({"car_market_30": [0.01, None, 0.02], "car_market_90": [None, None, 0.03]})
    got = audits.nan_audit(sample)
    m30 = got.filter(pl.col("column") == "car_market_30")
    assert m30["n_null"][0] == 1
    m90 = got.filter(pl.col("column") == "car_market_90")
    assert m90["n_null"][0] == 2


def test_delisting_audit_flags_a_ticker_with_a_large_price_gap():
    sample = pl.DataFrame({"ticker": ["DEAD", "LIVE"], "report_date": [date(2020, 6, 1), date(2020, 6, 1)]})
    prices = pl.DataFrame(
        {
            "ticker": ["DEAD", "LIVE"], "date": [date(2020, 1, 1), date(2020, 6, 1)],
            "open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0], "close": [1.0, 1.0],
            "volume": [1.0, 1.0], "close_adj": [1.0, 1.0],
        }
    )
    got = audits.delisting_audit(sample, prices, gap_days=90)
    assert "DEAD" in got["ticker"].to_list()
    assert "LIVE" not in got["ticker"].to_list()


def test_delisting_audit_flags_a_ticker_with_zero_price_history():
    # A ticker absent from `prices` entirely is a WORSE data-completeness
    # problem than merely-stale (>gap_days) data -- silently dropping it
    # from the audit would understate the very survivorship-bias signal
    # this function exists to quantify. Confirmed empirically before this
    # task was built: a plain `days_since_last_price > gap_days` filter
    # evaluates to null (not True) for a ticker whose left-joined
    # last_price_date is null, so it never survives the filter and
    # disappears from the output with no trace -- indistinguishable from
    # "checked and found fine." last_price_date/days_since_last_price
    # must come through as None in the output, not omit the row.
    sample = pl.DataFrame({"ticker": ["GHOST", "LIVE"], "report_date": [date(2020, 6, 1), date(2020, 6, 1)]})
    prices = pl.DataFrame(
        {
            "ticker": ["LIVE"], "date": [date(2020, 6, 1)],
            "open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0],
            "volume": [1.0], "close_adj": [1.0],
        }
    )
    got = audits.delisting_audit(sample, prices, gap_days=90)
    assert "GHOST" in got["ticker"].to_list()
    ghost = got.filter(pl.col("ticker") == "GHOST")
    assert ghost["last_price_date"][0] is None
    assert ghost["days_since_last_price"][0] is None
    assert "LIVE" not in got["ticker"].to_list()


def test_ticker_reuse_audit_flags_a_cik_with_multiple_tickers():
    sic = pl.DataFrame(
        {"ticker": ["OLDNAME", "NEWNAME", "OTHER"], "cik": [1, 1, 2], "sic_code": ["1", "1", "2"], "sic_description": ["x", "x", "y"]}
    )
    got = audits.ticker_reuse_audit(sic)
    assert got.height == 1
    assert got["cik"][0] == 1
    assert set(got["tickers"][0]) == {"OLDNAME", "NEWNAME"}
