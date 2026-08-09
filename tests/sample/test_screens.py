from __future__ import annotations

from datetime import date

import polars as pl

from congressional_sales.sample import screens

SAMPLE_SCHEMA = {
    "ticker": pl.Utf8, "politician": pl.Utf8, "bioguide_id": pl.Utf8, "chamber": pl.Utf8,
    "party": pl.Utf8, "transaction": pl.Utf8, "transaction_date": pl.Date, "report_date": pl.Date,
    "amount_low": pl.Float64, "amount_range": pl.Utf8, "ticker_type": pl.Utf8, "description": pl.Utf8,
    "excess_return": pl.Float64, "price_change": pl.Float64, "spy_change": pl.Float64,
}


def _row(ticker, bioguide, transaction, tdate, rdate=None, amount=1001.0, amount_range="$1,001 - $15,000"):
    return {
        "ticker": ticker, "politician": bioguide, "bioguide_id": bioguide, "chamber": "Representatives",
        "party": "R", "transaction": transaction, "transaction_date": tdate, "report_date": rdate or tdate,
        "amount_low": amount, "amount_range": amount_range, "ticker_type": "ST", "description": None,
        "excess_return": None, "price_change": None, "spy_change": None,
    }


def _df(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=SAMPLE_SCHEMA)


def test_screen1_flags_sale_with_nearby_purchase_of_same_ticker():
    rows = _df(
        [
            _row("AAPL", "A1", "Sale", date(2020, 6, 1)),
            _row("AAPL", "A1", "Purchase", date(2020, 5, 1)),  # 31 days before -- within 90
        ]
    )
    out = screens.screen1_rebalancing(rows)
    sale = out.filter(pl.col("transaction") == "Sale")
    assert sale["excluded_rebalancing"][0] is True


def test_screen1_does_not_flag_sale_with_distant_purchase():
    rows = _df(
        [
            _row("AAPL", "A1", "Sale", date(2020, 6, 1)),
            _row("AAPL", "A1", "Purchase", date(2019, 1, 1)),  # far more than 90 days before
        ]
    )
    out = screens.screen1_rebalancing(rows)
    sale = out.filter(pl.col("transaction") == "Sale")
    assert sale["excluded_rebalancing"][0] is False


def test_screen1_flags_three_simultaneous_sales_across_sectors():
    d = date(2020, 6, 1)
    rows = _df(
        [
            _row("AAPL", "A1", "Sale", d),
            _row("XOM", "A1", "Sale", d),
            _row("JPM", "A1", "Sale", d),
        ]
    )
    out = screens.screen1_rebalancing(rows)
    assert out["excluded_rebalancing"].to_list() == [True, True, True]


def test_screen1_does_not_flag_isolated_single_sale():
    rows = _df([_row("AAPL", "A1", "Sale", date(2020, 6, 1))])
    out = screens.screen1_rebalancing(rows)
    assert out["excluded_rebalancing"][0] is False
