"""Inclusion/exclusion funnel (PRE_ANALYSIS_PLAN.md Section 4). Every step
is logged with an exact before/after count -- this IS table T1.

Not implemented as a separate filter (documented, not a silent gap):
Quiver's feed has no filer-relationship field (self/spouse/dependent
child) -- every disclosed transaction already covers all three by legal
definition of what a PTR filing is, so there is nothing to filter here.
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
