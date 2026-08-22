"""Quiver Quantitative congressional trading adapter.

Same point-in-time trap as Form 4 insider trading: the STOCK Act gives
members of Congress up to 45 days to disclose a trade, so transaction_date
is NOT knowable on the date it happened -- only report_date (when the
periodic transaction report was actually filed) is. Every sample-
construction and event-study step in this study must gate on
report_date <= as_of, never transaction_date.

There is no unique row ID in Quiver's response, so idempotent upsert keys
on a natural composite (ticker, bioguide_id, transaction_date, transaction,
amount_range). Two genuinely distinct disclosures on the same day of the
same type/range by the same politician for the same ticker will collapse
to one row -- an accepted limitation given the data as published.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from .. import storage
from ..config import QUIVER_API_TOKEN
from ..http import get_json

CONGRESS_HISTORICAL_URL = "https://api.quiverquant.com/beta/historical/congresstrading/{ticker}"
BULK_CONGRESS_TRADES_URL = "https://api.quiverquant.com/beta/bulk/congresstrading"


class MissingTokenError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    if not QUIVER_API_TOKEN:
        raise MissingTokenError(
            "QUIVER_API_TOKEN is not set. Get a Trader-tier key at "
            "https://www.quiverquant.com/api-setup/, then add it to .env."
        )
    return {"Accept": "application/json", "Authorization": f"Token {QUIVER_API_TOKEN}"}


CONGRESS_TRADES_SCHEMA = {
    "ticker": pl.Utf8, "politician": pl.Utf8, "bioguide_id": pl.Utf8, "chamber": pl.Utf8,
    "party": pl.Utf8, "transaction": pl.Utf8, "transaction_date": pl.Date, "report_date": pl.Date,
    "amount_low": pl.Float64, "amount_range": pl.Utf8, "ticker_type": pl.Utf8, "description": pl.Utf8,
    "excess_return": pl.Float64, "price_change": pl.Float64, "spy_change": pl.Float64,
}

_RENAME = {
    "Ticker": "ticker", "Representative": "politician", "BioGuideID": "bioguide_id",
    "House": "chamber", "Party": "party", "Transaction": "transaction",
    "TransactionDate": "transaction_date", "ReportDate": "report_date",
    "Range": "amount_range", "Amount": "amount_low", "TickerType": "ticker_type",
    "Description": "description",
    "ExcessReturn": "excess_return", "PriceChange": "price_change", "SPYChange": "spy_change",
}


def parse_congress_trades(rows: list[dict]) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame(schema=CONGRESS_TRADES_SCHEMA)

    df = pl.DataFrame(rows, infer_schema_length=None)
    present = {k: v for k, v in _RENAME.items() if k in df.columns}
    df = df.rename(present)
    for col in CONGRESS_TRADES_SCHEMA:
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).alias(col))

    return (
        df.with_columns(
            pl.col("transaction_date").cast(pl.Utf8).str.to_date("%Y-%m-%d", strict=False),
            pl.col("report_date").cast(pl.Utf8).str.to_date("%Y-%m-%d", strict=False),
            pl.col("amount_low").cast(pl.Utf8).str.replace_all(",", "").cast(pl.Float64, strict=False),
        )
        .select(list(CONGRESS_TRADES_SCHEMA))
        .cast(CONGRESS_TRADES_SCHEMA)  # type: ignore[arg-type]
    )


def parse_bulk_tickers(rows: list[dict], period_start: date, period_end: date) -> list[str]:
    """PRE_ANALYSIS_PLAN.md Addendum A: the study's ticker universe is
    disclosure-defined, discovered via a single bulk call, not assumed
    from any index. Used ONLY to discover which ticker symbols exist --
    every discovered symbol still goes through the ordinary, already-
    reviewed ingest_congress_trades per-ticker pipeline exactly as any
    manually-chosen ticker would (Addendum A's own text); this function
    never feeds a transaction record into the study directly.

    The bulk endpoint's own JSON field names are NOT the same as the
    per-ticker endpoint's -- confirmed live before this function was
    written: it uses "Filed" (not "ReportDate") for the disclosure date,
    "Traded" (not "TransactionDate"), "Name" (not "Representative"), and
    has no "Range"/"Amount" fields at all. Reusing parse_congress_trades
    on this response silently maps every field to null instead of raising
    -- the exact "join silently mis-bucketing rows instead of dropping
    them" failure mode already documented elsewhere in this codebase (see
    sample/classify.py's skip_nulls=False comments) -- so this is a
    dedicated parser, not a reuse of that function.

    "Filed" is used for the period restriction, matching this study's
    report_date point-in-time discipline: a ticker enters the universe iff
    at least one disclosure naming it was FILED (not merely traded) within
    the sample period.
    """
    if not rows:
        return []
    df = pl.DataFrame(rows, infer_schema_length=None)
    filed = df.select(
        pl.col("Ticker").alias("ticker"),
        pl.col("Filed").str.to_date("%Y-%m-%d", strict=False).alias("filed_date"),
    )
    in_period = filed.filter(
        pl.col("filed_date").is_not_null()
        & (pl.col("filed_date") >= period_start)
        & (pl.col("filed_date") <= period_end)
    )
    return sorted(in_period["ticker"].drop_nulls().unique().to_list())


def discover_ticker_universe(period_start: date, period_end: date) -> list[str]:
    """Single call to Quiver's bulk endpoint (no pagination -- confirmed
    live), returning every distinct ticker named in a disclosure filed
    within [period_start, period_end]. See parse_bulk_tickers for why this
    is not simply parse_congress_trades applied to a bigger response."""
    rows = get_json(BULK_CONGRESS_TRADES_URL, headers=_headers())
    return parse_bulk_tickers(rows, period_start, period_end)


def ingest_congress_trades(ticker: str) -> int:
    rows = get_json(CONGRESS_HISTORICAL_URL.format(ticker=ticker.upper()), headers=_headers())
    df = parse_congress_trades(rows)
    if df.is_empty():
        return 0
    df = df.with_columns(pl.lit(ticker.upper()).alias("ticker"))
    storage.write(
        "congress_trades", df,
        key_cols=["ticker", "bioguide_id", "transaction_date", "transaction", "amount_range"],
        partition=ticker.upper(),
    )
    return df.height
