from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from congressional_sales.sample import descriptive

SAMPLE_SCHEMA = {
    "ticker": pl.Utf8, "politician": pl.Utf8, "bioguide_id": pl.Utf8, "chamber": pl.Utf8,
    "party": pl.Utf8, "transaction": pl.Utf8, "transaction_date": pl.Date, "report_date": pl.Date,
    "amount_low": pl.Float64, "amount_range": pl.Utf8, "ticker_type": pl.Utf8, "description": pl.Utf8,
    "excess_return": pl.Float64, "price_change": pl.Float64, "spy_change": pl.Float64,
}


def _sample() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT", "AAPL"],
            "politician": ["A", "B", "C"], "bioguide_id": ["A1", "B1", "C1"],
            "chamber": ["Representatives", "Senate", "Representatives"],
            "party": ["R", "D", "R"], "transaction": ["Purchase", "Sale", "Purchase"],
            "transaction_date": [date(2020, 1, 1), date(2020, 6, 1), date(2021, 1, 1)],
            "report_date": [date(2020, 1, 20), date(2020, 6, 10), date(2021, 3, 1)],
            "amount_low": [1001.0, 15001.0, 1001.0],
            "amount_range": ["$1,001 - $15,000", "$15,001 - $50,000", "$1,001 - $15,000"],
            "ticker_type": ["ST", "ST", "ST"], "description": [None, None, None],
            "excess_return": [None, None, None], "price_change": [None, None, None], "spy_change": [None, None, None],
        },
        schema=SAMPLE_SCHEMA,
    )


def _sic() -> pl.DataFrame:
    return pl.DataFrame(
        {"ticker": ["AAPL", "MSFT"], "cik": [320193, 789019], "sic_code": ["3571", "7372"], "sic_description": ["x", "y"]},
        schema={"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8},
    )


def test_build_t2_counts_by_year():
    t2 = descriptive.build_t2(_sample(), _sic())
    years = t2.filter(pl.col("dimension") == "year").sort("value")
    assert years["value"].to_list() == ["2020", "2021"]
    assert years["count"].to_list() == [2, 1]


def test_build_t2_counts_by_chamber_and_party():
    t2 = descriptive.build_t2(_sample(), _sic())
    chambers = t2.filter(pl.col("dimension") == "chamber")
    assert set(chambers["value"].to_list()) == {"Representatives", "Senate"}
    parties = t2.filter(pl.col("dimension") == "party")
    assert dict(zip(parties["value"], parties["count"])) == {"R": 2, "D": 1}


def test_build_t2_counts_by_sector_via_ff12():
    t2 = descriptive.build_t2(_sample(), _sic())
    sectors = t2.filter(pl.col("dimension") == "sector")
    # AAPL (SIC 3571, Electronic Computers) -> Business Equipment; MSFT (SIC 7372) -> Business Equipment too.
    assert sectors.filter(pl.col("value") == "Business Equipment")["count"][0] == 3


def test_build_t2_counts_by_size_band_using_disclosed_range():
    t2 = descriptive.build_t2(_sample(), _sic())
    bands = t2.filter(pl.col("dimension") == "size_band")
    assert dict(zip(bands["value"], bands["count"])) == {"$1,001 - $15,000": 2, "$15,001 - $50,000": 1}


def test_filing_lag_days_computes_report_minus_transaction():
    lag = descriptive.filing_lag_days(_sample())
    assert lag.to_list() == [19, 9, 59]


def test_build_t3_summary_stats():
    t3 = descriptive.build_t3(_sample())
    assert t3["max"] == 59
    assert t3["median"] == 19
    assert t3["share_beyond_45d"] == pytest.approx(1 / 3)
