"""SIC (Standard Industrial Classification) code lookup via SEC EDGAR --
the same free, no-auth endpoints EDGAR-based platforms use for CIK
resolution and company facts."""

from __future__ import annotations

import polars as pl

from .. import storage
from ..config import USER_AGENT
from ..http import get_json

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"


def resolve_cik(ticker: str) -> int | None:
    payload = get_json(TICKERS_URL, headers={"User-Agent": USER_AGENT})
    for row in payload.values():
        if row["ticker"].upper() == ticker.upper():
            return int(row["cik_str"])
    return None


def fetch_sic(cik: int) -> tuple[str, str] | None:
    payload = get_json(SUBMISSIONS_URL.format(cik=cik), headers={"User-Agent": USER_AGENT})
    sic_code = payload.get("sic")
    if not sic_code:
        return None
    return (sic_code, payload.get("sicDescription", ""))


def ingest_sic_codes(tickers: list[str]) -> int:
    rows = []
    for t in tickers:
        cik = resolve_cik(t)
        if cik is None:
            continue
        result = fetch_sic(cik)
        if result is None:
            continue
        code, desc = result
        rows.append({"ticker": t.upper(), "cik": cik, "sic_code": code, "sic_description": desc})
    if not rows:
        return 0
    df = pl.DataFrame(rows, schema={"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8})
    storage.write("sic_codes", df, key_cols=["ticker"])
    return df.height
