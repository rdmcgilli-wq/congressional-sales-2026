"""Section 11's 20-transaction hand-check: this module builds the
worksheet a human fills in -- it does not perform the hand-check itself."""

from __future__ import annotations

import polars as pl


def select_worksheet_sample(sample_with_car: pl.DataFrame, n: int = 20, seed: int = 42) -> pl.DataFrame:
    return sample_with_car.sample(n=min(n, sample_with_car.height), seed=seed)


def build_worksheet(rows: pl.DataFrame) -> pl.DataFrame:
    return rows.with_columns(
        pl.lit(None).cast(pl.Float64).alias("manual_car_market_90"),
        pl.lit(None).cast(pl.Utf8).alias("manual_notes"),
        pl.lit(None).cast(pl.Utf8).alias("matches_pipeline"),
    )
