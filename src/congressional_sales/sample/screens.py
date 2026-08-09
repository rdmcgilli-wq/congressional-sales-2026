"""The four sequential screens, PRE_ANALYSIS_PLAN.md Section 5. Each
screen ADDS a boolean exclusion-flag column rather than dropping rows, so
downstream code can compute both the unscreened and screened view of the
same sample without re-deriving the funnel."""

from __future__ import annotations

from datetime import timedelta

import polars as pl


def screen1_rebalancing(sample: pl.DataFrame) -> pl.DataFrame:
    df = sample

    # Condition A: same member bought the same ticker within 90 days
    # before/after a sale (uses transaction_date -- see this task's
    # methodology note in the plan).
    sales = df.filter(pl.col("transaction") == "Sale").select("bioguide_id", "ticker", "transaction_date")
    purchases = df.filter(pl.col("transaction") == "Purchase").select(
        pl.col("bioguide_id"), pl.col("ticker"), pl.col("transaction_date").alias("purchase_date")
    )
    matched = sales.join(purchases, on=["bioguide_id", "ticker"], how="inner").with_columns(
        (pl.col("purchase_date") - pl.col("transaction_date")).dt.total_days().abs().alias("gap_days")
    )
    flagged_pairs = matched.filter(pl.col("gap_days") <= 90).select("bioguide_id", "ticker", "transaction_date").unique()

    # Condition B: >=3 simultaneous sales by the same member across >=3
    # distinct tickers on the same date ("unrelated sectors" approximated
    # here as distinct tickers -- sector diversity requires the SIC join
    # from Task 7/9, which this pure function deliberately does not take
    # as a dependency; a stricter sector-diversity check can be layered on
    # by the caller before/after this function if the reviewer determines
    # ticker-distinctness alone is too weak a proxy for "unrelated sectors").
    same_day_sales = (
        df.filter(pl.col("transaction") == "Sale")
        .group_by(["bioguide_id", "transaction_date"])
        .agg(pl.col("ticker").n_unique().alias("n_tickers"))
        .filter(pl.col("n_tickers") >= 3)
        .select("bioguide_id", "transaction_date")
    )

    # maintain_order="left" is required, not cosmetic: the code below combines
    # these join results with `df`'s other columns via positional Series
    # &/| rather than a key-based join, so it depends on row order matching
    # `df` exactly. polars' join docstring explicitly declines to guarantee
    # any particular row order unless maintain_order is set -- see this
    # task's review note.
    flag_a = df.join(
        flagged_pairs.with_columns(pl.lit(True).alias("_flag_a")),
        on=["bioguide_id", "ticker", "transaction_date"], how="left", maintain_order="left",
    )["_flag_a"].fill_null(False)

    flag_b = df.join(
        same_day_sales.with_columns(pl.lit(True).alias("_flag_b")),
        on=["bioguide_id", "transaction_date"], how="left", maintain_order="left",
    )["_flag_b"].fill_null(False)

    is_sale = df["transaction"] == "Sale"
    excluded = is_sale & (flag_a | flag_b)
    return df.with_columns(excluded.alias("excluded_rebalancing"))
