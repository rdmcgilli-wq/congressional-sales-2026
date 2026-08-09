"""T2 (descriptive statistics) and T3 (filing lag distribution),
PRE_ANALYSIS_PLAN.md Section 10."""

from __future__ import annotations

import polars as pl

from .industry import ff12_industry


def filing_lag_days(sample: pl.DataFrame) -> pl.Series:
    return (sample["report_date"] - sample["transaction_date"]).dt.total_days()


def build_t3(sample: pl.DataFrame) -> dict:
    lag = filing_lag_days(sample)
    return {
        "median": lag.median(),
        "mean": lag.mean(),
        "p90": lag.quantile(0.90),
        "max": lag.max(),
        "share_beyond_45d": (lag > 45).mean(),
    }


def _count_dimension(sample: pl.DataFrame, dimension: str, value_col: pl.Expr) -> pl.DataFrame:
    return (
        sample.with_columns(value_col.alias("value"))
        .group_by("value")
        .agg(pl.len().alias("count"))
        .with_columns(pl.lit(dimension).alias("dimension"))
        .select("dimension", "value", "count")
    )


def build_t2(sample: pl.DataFrame, sic: pl.DataFrame) -> pl.DataFrame:
    by_year = _count_dimension(sample, "year", pl.col("report_date").dt.year().cast(pl.Utf8))
    by_chamber = _count_dimension(sample, "chamber", pl.col("chamber"))
    by_party = _count_dimension(sample, "party", pl.col("party"))
    by_size = _count_dimension(sample, "size_band", pl.col("amount_range"))

    with_sic = sample.join(sic.select("ticker", "sic_code"), on="ticker", how="left")
    with_sector = with_sic.with_columns(
        # skip_nulls=False: a ticker with no SIC match (left-join miss) has a
        # null sic_code, and map_elements' default skip_nulls=True lets that
        # null pass straight through untouched -- producing a "null" sector
        # label instead of calling ff12_industry(None), which is explicitly
        # coded to return "Other". This is the join "silently mis-bucketing
        # rows instead of dropping them" failure mode: row counts stay
        # correct, but unmatched tickers land in an unlabeled null group
        # rather than the intended "Other" catch-all.
        pl.col("sic_code").map_elements(ff12_industry, return_dtype=pl.Utf8, skip_nulls=False).alias("sector")
    )
    by_sector = _count_dimension(with_sector, "sector", pl.col("sector"))

    return pl.concat([by_year, by_chamber, by_party, by_sector, by_size], how="vertical_relaxed").sort(
        ["dimension", "value"]
    )
