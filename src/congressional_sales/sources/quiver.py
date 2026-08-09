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

import polars as pl

from .. import storage
from ..config import QUIVER_API_TOKEN
from ..http import get_json

CONGRESS_HISTORICAL_URL = "https://api.quiverquant.com/beta/historical/congresstrading/{ticker}"


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
