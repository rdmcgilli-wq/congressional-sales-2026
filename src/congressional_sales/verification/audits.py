"""Section 11 audits: NaN accounting, delisting-gap detection (quantifies
the survivorship-bias deviation, does not fix it), and ticker-reuse
detection (the "match on a permanent identifier, symbols get reused"
warning)."""

from __future__ import annotations

import polars as pl


def nan_audit(sample_with_car: pl.DataFrame) -> pl.DataFrame:
    car_cols = [c for c in sample_with_car.columns if c.startswith("car_") or c.startswith("bhar_")]
    n = sample_with_car.height
    rows = [
        {"column": c, "n_null": sample_with_car[c].null_count(), "pct_null": sample_with_car[c].null_count() / n if n else 0.0}
        for c in car_cols
    ]
    return pl.DataFrame(rows)


def delisting_audit(sample: pl.DataFrame, prices: pl.DataFrame, gap_days: int = 90) -> pl.DataFrame:
    as_of = sample["report_date"].max()
    last_price = prices.group_by("ticker").agg(pl.col("date").max().alias("last_price_date"))
    sample_tickers = sample.select("ticker").unique()
    joined = sample_tickers.join(last_price, on="ticker", how="left")
    gapped = joined.with_columns(
        (pl.lit(as_of) - pl.col("last_price_date")).dt.total_days().alias("days_since_last_price")
    ).filter(
        # A ticker absent from `prices` entirely gets a null
        # last_price_date from this left join, and `null > gap_days`
        # evaluates to null (not True) in a polars filter -- so without
        # the explicit is_null() branch, a ticker with ZERO price history
        # (a worse data-completeness problem than merely-stale data)
        # would silently vanish from this audit's output rather than
        # being flagged, understating the very survivorship-bias signal
        # this function exists to quantify. Confirmed empirically before
        # this task was built.
        (pl.col("days_since_last_price") > gap_days) | pl.col("last_price_date").is_null()
    )
    return gapped.select("ticker", "last_price_date", "days_since_last_price")


def ticker_reuse_audit(sic: pl.DataFrame) -> pl.DataFrame:
    return (
        sic.group_by("cik")
        .agg(pl.col("ticker").unique().alias("tickers"))
        .with_columns(pl.col("tickers").list.len().alias("n_tickers"))
        .filter(pl.col("n_tickers") > 1)
    )
