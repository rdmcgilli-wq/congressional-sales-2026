"""Daily equity EOD prices, adjusted for splits/dividends.

Tiingo is the sole provider (a free key covers ~500 symbols/month with
adjusted history back decades -- see https://www.tiingo.com/). This price
feed does NOT include delisted securities -- see the "documented deviation"
in PRE_ANALYSIS_PLAN.md Section 3/11 and Global Constraints: this is a
known, reported limitation of this study, not a bug to silently paper over.
"""

from __future__ import annotations

import os

import polars as pl

from .. import storage
from ..http import get_json

TIINGO_URL = "https://api.tiingo.com/tiingo/daily/{ticker}/prices"

PRICE_SCHEMA = {
    "ticker": pl.Utf8, "date": pl.Date, "open": pl.Float64, "high": pl.Float64,
    "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64, "close_adj": pl.Float64,
}


class ProviderUnavailable(RuntimeError):
    pass


def fetch_tiingo(ticker: str, start: str | None = None) -> pl.DataFrame:
    token = os.getenv("TIINGO_API_TOKEN", "")
    if not token:
        raise ProviderUnavailable(
            "TIINGO_API_TOKEN is not set. Free key at https://www.tiingo.com/, then add it to .env."
        )
    params = {"token": token, "format": "json"}
    if start:
        params["startDate"] = start
    rows = get_json(TIINGO_URL.format(ticker=ticker.lower()), params=params)
    if not rows:
        return pl.DataFrame(schema=PRICE_SCHEMA)
    df = pl.DataFrame(rows, infer_schema_length=None)
    return (
        df.with_columns(
            pl.lit(ticker.upper()).alias("ticker"),
            pl.col("date").str.slice(0, 10).str.to_date("%Y-%m-%d"),
            pl.col("adjClose").alias("close_adj"),
        )
        .select(list(PRICE_SCHEMA))
        .cast(PRICE_SCHEMA)  # type: ignore[arg-type]
    )


def ingest_prices(ticker: str, start: str | None = None) -> int:
    df = fetch_tiingo(ticker, start=start)
    if df.is_empty():
        return 0
    storage.write("equity_eod", df, key_cols=["ticker", "date"], partition=ticker.upper())
    return df.height
