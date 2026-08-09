from __future__ import annotations

from datetime import date

import polars as pl

from congressional_sales.sample import classify

SAMPLE_SCHEMA = {
    "ticker": pl.Utf8, "politician": pl.Utf8, "bioguide_id": pl.Utf8, "chamber": pl.Utf8,
    "party": pl.Utf8, "transaction": pl.Utf8, "transaction_date": pl.Date, "report_date": pl.Date,
    "amount_low": pl.Float64, "amount_range": pl.Utf8, "ticker_type": pl.Utf8, "description": pl.Utf8,
    "excess_return": pl.Float64, "price_change": pl.Float64, "spy_change": pl.Float64,
}


def _row(ticker, bioguide, tdate, transaction="Purchase"):
    return {
        "ticker": ticker, "politician": bioguide, "bioguide_id": bioguide, "chamber": "Representatives",
        "party": "R", "transaction": transaction, "transaction_date": tdate, "report_date": tdate,
        "amount_low": 1001.0, "amount_range": "$1,001 - $15,000", "ticker_type": "ST", "description": None,
        "excess_return": None, "price_change": None, "spy_change": None,
    }


def test_is_routine_trader_flags_same_month_three_years_running():
    rows = pl.DataFrame(
        [
            _row("AAPL", "A1", date(2020, 3, 10)),
            _row("MSFT", "A1", date(2019, 3, 5)),
            _row("NVDA", "A1", date(2018, 3, 20)),
            _row("XOM", "A1", date(2017, 3, 1)),
        ],
        schema=SAMPLE_SCHEMA,
    )
    out = classify.is_routine_trader(rows)
    row2020 = out.filter(pl.col("transaction_date") == date(2020, 3, 10))
    assert row2020["is_routine"][0] is True


def test_is_routine_trader_does_not_flag_a_one_off_trade():
    rows = pl.DataFrame([_row("AAPL", "A1", date(2020, 3, 10))], schema=SAMPLE_SCHEMA)
    out = classify.is_routine_trader(rows)
    assert out["is_routine"][0] is False


def test_committee_match_flags_matching_sector():
    rows = pl.DataFrame([_row("XOM", "A1", date(2020, 3, 10))], schema=SAMPLE_SCHEMA)
    assignments = pl.DataFrame(
        {
            "bioguide_id": ["A1"], "committee_code": ["SSEG"], "chamber": ["senate"],
            "committee_name": ["Senate Committee on Energy and Natural Resources"],
        }
    )
    sic = pl.DataFrame(
        {"ticker": ["XOM"], "cik": [34088], "sic_code": ["2911"], "sic_description": ["Petroleum Refining"]},
        schema={"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8},
    )
    out = classify.committee_match(rows, assignments, sic)
    assert out["committee_match"][0] is True


def test_committee_match_false_for_unrelated_sector():
    rows = pl.DataFrame([_row("XOM", "A1", date(2020, 3, 10))], schema=SAMPLE_SCHEMA)
    assignments = pl.DataFrame(
        {
            "bioguide_id": ["A1"], "committee_code": ["SSAF"], "chamber": ["senate"],
            "committee_name": ["Senate Committee on Agriculture, Nutrition, and Forestry"],
        }
    )
    sic = pl.DataFrame(
        {"ticker": ["XOM"], "cik": [34088], "sic_code": ["2911"], "sic_description": ["Petroleum Refining"]},
        schema={"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8},
    )
    out = classify.committee_match(rows, assignments, sic)
    assert out["committee_match"][0] is False
