"""Inclusion/exclusion funnel (PRE_ANALYSIS_PLAN.md Section 4). Every step
is logged with an exact before/after count -- this IS table T1.

Not implemented as a separate filter (documented, not a silent gap):
Quiver's feed has no filer-relationship field (self/spouse/dependent
child) -- every disclosed transaction already covers all three by legal
definition of what a PTR filing is, so there is nothing to filter here.

Section 4's "Exchanges and transfers (not directional decisions)"
exclusion IS implemented, via directional_transaction_only below --
found missing entirely (whole-branch review, not any single task review:
Task 8's own brief dropped this bullet when the plan was decomposed into
task briefs, so no task-scoped review could see the gap). Confirmed
against this study's own sibling private-repo Quiver adapter (live-
verified against the real API earlier in this project's development,
2,655 real disclosures) that the real Transaction field is NOT limited
to the literal strings "Purchase"/"Sale" -- it includes at least
"Sale (Full)"/"Sale (Partial)" variants, and models.model2's original
`"sale": 1 if row["transaction"] == "Sale" else 0` coding would have
silently coded every one of those real rows as a PURCHASE, contaminating
the comparison group of the single pre-registered primary test. Fixed
here (normalize Sale variants, exclude anything that isn't Purchase or
Sale) and in models/model2.py (fail loud instead of silently defaulting,
as a safety net for any caller that bypasses this funnel).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import polars as pl

from .. import storage


@dataclass
class FunnelStep:
    name: str
    count_before: int
    count_after: int


@dataclass
class FunnelResult:
    steps: list[FunnelStep]
    sample: pl.DataFrame


def _step(steps: list[FunnelStep], name: str, before: pl.DataFrame, after: pl.DataFrame) -> None:
    steps.append(FunnelStep(name=name, count_before=before.height, count_after=after.height))


def build_sample(
    min_prior_trading_days: int = 60,
    max_horizon_trading_days: int = 180,
    period_start: date = date(2014, 1, 1),
    period_end: date | None = None,
) -> FunnelResult:
    steps: list[FunnelStep] = []
    df = storage.read("congress_trades")
    if df.is_empty():
        return FunnelResult(steps=steps, sample=df)

    raw = df
    period_end = period_end or date.today()
    in_period = raw.filter((pl.col("report_date") >= period_start) & (pl.col("report_date") <= period_end))
    _step(steps, "sample_period", raw, in_period)
    df = in_period

    stock_only = df.filter(pl.col("ticker_type") == "ST")
    _step(steps, "common_stock_only", df, stock_only)
    df = stock_only

    # Section 4: "Exchanges and transfers (not directional decisions)" are
    # excluded. Real Quiver data uses Sale variants ("Sale (Full)",
    # "Sale (Partial)") rather than a bare "Sale" string -- normalize any
    # value starting with "Sale" to the canonical "Sale" first (every
    # downstream consumer treats sales as one category; no task in this
    # plan distinguishes full vs. partial), THEN keep only
    # {"Purchase", "Sale"}. This is a whitelist, not a blacklist, so it
    # excludes "Exchange"/"Transfer"/anything else without needing to know
    # Quiver's exact string for them in advance -- the failure mode for an
    # unanticipated value is exclusion-with-a-logged-count, never silent
    # inclusion.
    normalized = df.with_columns(
        pl.when(pl.col("transaction").str.starts_with("Sale"))
        .then(pl.lit("Sale"))
        .otherwise(pl.col("transaction"))
        .alias("transaction")
    )
    directional = normalized.filter(pl.col("transaction").is_in(["Purchase", "Sale"]))
    _step(steps, "directional_transaction_only", df, directional)
    df = directional

    above_threshold = df.filter(pl.col("amount_low") > 1000.0)
    _step(steps, "above_statutory_threshold", df, above_threshold)
    df = above_threshold

    deduped = df.unique(
        subset=["ticker", "bioguide_id", "transaction_date", "transaction", "amount_range"],
        keep="first",
    )
    _step(steps, "dedupe_filings", df, deduped)
    df = deduped

    prices = storage.read("equity_eod")
    if prices.is_empty():
        _step(steps, "min_prior_trading_history", df, df.clear())
        _step(steps, "full_forward_window", df.clear(), df.clear())
        return FunnelResult(steps=steps, sample=df.clear())

    prior_counts = (
        df.join(prices.select("ticker", "date"), on="ticker", how="left")
        .filter(pl.col("date") < pl.col("report_date"))
        .group_by(["ticker", "bioguide_id", "transaction_date", "transaction", "amount_range"])
        .agg(pl.len().alias("n_prior"))
    )
    has_prior_history = df.join(
        prior_counts, on=["ticker", "bioguide_id", "transaction_date", "transaction", "amount_range"], how="inner"
    ).filter(pl.col("n_prior") >= min_prior_trading_days).drop("n_prior")
    _step(steps, "min_prior_trading_history", df, has_prior_history)
    df = has_prior_history

    forward_counts = (
        df.join(prices.select("ticker", "date"), on="ticker", how="left")
        .filter(pl.col("date") > pl.col("report_date"))
        .group_by(["ticker", "bioguide_id", "transaction_date", "transaction", "amount_range"])
        .agg(pl.len().alias("n_forward"))
    )
    has_full_forward = df.join(
        forward_counts, on=["ticker", "bioguide_id", "transaction_date", "transaction", "amount_range"], how="inner"
    ).filter(pl.col("n_forward") >= max_horizon_trading_days).drop("n_forward")
    _step(steps, "full_forward_window", df, has_full_forward)
    df = has_full_forward

    return FunnelResult(steps=steps, sample=df)
