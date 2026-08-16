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


def _price_asof(prices: pl.DataFrame, ticker: str, d) -> float | None:
    rows = prices.filter((pl.col("ticker") == ticker) & (pl.col("date") <= d))
    if rows.is_empty():
        return None
    return rows.sort("date")["close_adj"][-1]


def screen2_tax_management(sample: pl.DataFrame, prices: pl.DataFrame) -> pl.DataFrame:
    df = sample
    flags = []
    for row in df.iter_rows(named=True):
        if row["transaction"] != "Sale" or row["transaction_date"].month not in (11, 12):
            flags.append(False)
            continue
        prior_purchases = df.filter(
            (pl.col("bioguide_id") == row["bioguide_id"])
            & (pl.col("ticker") == row["ticker"])
            & (pl.col("transaction") == "Purchase")
            & (pl.col("transaction_date") < row["transaction_date"])
        ).sort("transaction_date", descending=True)
        if prior_purchases.is_empty():
            flags.append(False)
            continue
        last_purchase_date = prior_purchases["transaction_date"][0]
        purchase_price = _price_asof(prices, row["ticker"], last_purchase_date)
        sale_price = _price_asof(prices, row["ticker"], row["transaction_date"])
        if purchase_price is None or sale_price is None:
            flags.append(False)
            continue
        flags.append(sale_price < purchase_price)
    return df.with_columns(pl.Series("excluded_tax_management", flags))


def screen3_liquidation(
    sample: pl.DataFrame,
    terms: pl.DataFrame,
    portfolio_liquidation_pct: float = 0.60,
    retirement_window_days: int = 90,
    apply_3a: bool = True,
) -> pl.DataFrame:
    """`apply_3a=False` (PRE_ANALYSIS_PLAN.md Addendum B) drops
    sub-condition 1 (the >60%-of-cumulative-disclosed-exposure proxy)
    entirely, keeping sub-condition 2 (the retirement window) exactly as
    specified. This exists to report the screened sample BOTH with and
    without sub-condition 1 applied, not to replace it: that sub-condition
    is built purely from disclosed transaction amounts WITHIN the sample
    period and has no visibility into a member's true pre-existing
    holdings, so it can structurally never fire for a sale where
    cumulative prior DISCLOSED exposure isn't positive -- a real,
    documented limitation, not a bug. See Addendum B for the full
    reasoning; this parameter is the mechanism, not the decision.
    """
    # Sorted on the full canonical key, not just ["bioguide_id",
    # "transaction_date"]: cum_sum().over("bioguide_id") below needs a
    # deterministic order WITHIN each member, and polars does not
    # guarantee tie-stable ordering for rows sharing (bioguide_id,
    # transaction_date) under a partial sort key (default
    # maintain_order=False). Whole-branch review finding, verified
    # empirically: three same-day rows for one member fed to this
    # function in canonical vs. reversed order produced DIFFERENT
    # excluded_liquidation flags ([F,T,T] vs [F,F,F]), not just a
    # different row order -- this was a latent correctness dependency on
    # every CALLER happening to pre-sort consistently (which
    # scripts/run_full_pipeline.py and scripts/run_holdout.py do, for
    # their own reproducibility reasons, but that was never a contract
    # this function itself enforced). The extra columns are deterministic
    # tie-breakers only; the semantically meaningful order is still
    # bioguide_id then transaction_date.
    df = sample.sort(["bioguide_id", "transaction_date", "ticker", "transaction", "amount_range"])

    # Sub-condition 1: cumulative net-exposure proxy.
    signed = pl.when(pl.col("transaction") == "Purchase").then(pl.col("amount_low")).otherwise(-pl.col("amount_low"))
    with_cum = df.with_columns(signed.alias("_signed")).with_columns(
        pl.col("_signed").cum_sum().over("bioguide_id").alias("_cum_exposure")
    )
    prior_exposure = with_cum["_cum_exposure"] - with_cum["_signed"]
    if apply_3a:
        is_big_sale = (with_cum["transaction"] == "Sale") & (prior_exposure > 0) & (
            with_cum["amount_low"] > portfolio_liquidation_pct * prior_exposure
        )
    else:
        is_big_sale = pl.Series([False] * with_cum.height)

    # Sub-condition 2: retirement window.
    last_terms = (
        terms.sort(["bioguide_id", "term_start"])
        .group_by("bioguide_id")
        .agg(pl.col("term_end").last().alias("last_term_end"))
    )
    # maintain_order="left" is required, not optional: is_near_retirement
    # (derived from with_terms, i.e. this join's output order) gets combined
    # below with is_big_sale (derived from with_cum, i.e. df's own order) via
    # plain positional Series `|` -- not key-based alignment. Polars' own
    # docs explicitly do not guarantee left-join output order matches input
    # order without this parameter ("may break in a future release... might
    # differ even between different runs"). This exact bug class was found
    # and fixed in Task 10's screen1_rebalancing; fixed here pre-emptively.
    with_terms = df.join(last_terms, on="bioguide_id", how="left", maintain_order="left")
    gap = (with_terms["transaction_date"] - with_terms["last_term_end"]).dt.total_days().abs()
    is_near_retirement = with_terms["last_term_end"].is_not_null() & (gap <= retirement_window_days)

    excluded = is_big_sale | is_near_retirement
    return df.with_columns(excluded.alias("excluded_liquidation"))
