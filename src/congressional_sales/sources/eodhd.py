"""EODHD delisting-inclusive price patch. Tiingo (sources/prices.py) stays
the primary EOD price source for this study -- free, already integrated,
sufficient for any ticker still trading. EODHD is called only to PATCH
tickers whose Tiingo series ends before the true end of their trading
life: Tiingo drops a ticker once it is delisted rather than carrying its
final, often near-worthless prices -- the survivorship-bias deviation
PRE_ANALYSIS_PLAN.md Section 3 originally recorded and Addendum C
resolves. Patching only the (small) apparently-delisted subset, never the
whole universe, keeps this within the cheapest EODHD subscription tier's
daily call budget -- verified live before this module was written.

Ticker symbol reuse during a formal bankruptcy proceeding is a real,
confirmed risk, not a theoretical one: verified live against EODHD's own
data before this module was built -- Bed Bath & Beyond's original,
bankrupt entity only appears under the "Q" suffix Nasdaq/NYSE attach
during Chapter 11 (BBBYQ), while the bare "BBBY" ticker was later reused
entirely by a different company (the rebranded Overstock.com) with a
normal, unrelated, continuously-trading price history under the SAME
symbol. Querying the bare ticker alone for a delisted security can
therefore return a WRONG company's real data rather than an empty/missing
result -- a more dangerous failure mode than Tiingo's silent drop, since
it looks correct rather than absent. patch_delisted_ticker tries the
"Q"-suffix variant first and prefers it whenever it has any data: that
suffix is exchange-assigned specifically for a Chapter 11 filing and is
never reused for an unrelated company the way a plain ticker symbol can
be, so any data under it is guaranteed to belong to the same entity this
study's sample already knows under the bare ticker. The bare ticker's own
post-cutoff data is used as a patch only when it resumes within
BARE_TICKER_RESUME_WINDOW_DAYS of Tiingo's last known date -- a resumption
that close to the cutoff is far more likely to be the original security's
own continued trading (e.g. Tiingo's own coverage merely lagging) than an
unrelated company reissued onto a recycled symbol months or years later.

This is a partial, not exhaustive, fix. The "Q" suffix is the standard,
common convention for a Chapter 11 filing, not the only symbol-reuse
pattern that exists -- a security delisted for a different reason (a
clean cash-out acquisition settled after trading halts, a reverse-merger
reissue under an unrelated new symbol, ...) may still be missed, and is
left as the documented residual gap rather than silently assumed solved.
See Addendum C and the paper's own Limitations section.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import polars as pl

from .. import storage
from ..http import get_json
from .prices import PRICE_SCHEMA

EODHD_URL = "https://eodhd.com/api/eod/{symbol}"

# A bare-ticker resumption further out than this from Tiingo's last known
# date is treated as inconclusive (possibly an unrelated reissue) rather
# than patched -- see module docstring. 30 days comfortably covers a
# provider coverage lag without reaching into the multi-month-to-multi-year
# gaps a real symbol reissue typically shows (the BBBY -> Overstock reuse
# this module was built against had a roughly 3-month gap).
BARE_TICKER_RESUME_WINDOW_DAYS = 30


class ProviderUnavailable(RuntimeError):
    pass


def fetch_eodhd(symbol: str, canonical_ticker: str, start: str | None = None) -> pl.DataFrame:
    """Raw fetch for one exact EODHD symbol (e.g. "BBBYQ.US"), stored under
    `canonical_ticker` (e.g. "BBBY") -- so every row this function returns
    is keyed on the same ticker string this study's sample already uses,
    regardless of which exchange-assigned symbol variant EODHD required to
    retrieve it, rather than trying to infer the canonical ticker back out
    of the symbol string (fragile for a "Q"-suffix symbol specifically,
    since blindly stripping a trailing "Q" would also corrupt any ticker
    that legitimately ends in "Q").

    Returns an empty, correctly-typed frame for a 404 ("Ticker Not
    Found") or any other empty/non-list response body, exactly like a
    genuinely-covered but data-free query -- callers that need to
    distinguish "no such symbol" from "symbol exists, no rows in this
    window" should not rely on this function alone.
    """
    token = os.getenv("EODHD_API_TOKEN", "")
    if not token:
        raise ProviderUnavailable(
            "EODHD_API_TOKEN is not set. Get a key at https://eodhd.com/, then add it to .env."
        )
    params = {"api_token": token, "fmt": "json"}
    if start:
        params["from"] = start
    rows = get_json(EODHD_URL.format(symbol=symbol), params=params)
    if not isinstance(rows, list) or not rows:
        return pl.DataFrame(schema=PRICE_SCHEMA)
    df = pl.DataFrame(rows, infer_schema_length=None)
    return (
        df.with_columns(
            pl.lit(canonical_ticker.upper()).alias("ticker"),
            pl.col("date").str.to_date("%Y-%m-%d"),
            pl.col("adjusted_close").alias("close_adj"),
        )
        .select(list(PRICE_SCHEMA))
        .cast(PRICE_SCHEMA)  # type: ignore[arg-type]
    )


def find_stale_tickers(prices: pl.DataFrame, as_of: date, gap_days: int = 90) -> list[str]:
    """Tickers in `prices` whose last known price date is more than
    `gap_days` before `as_of` -- the same staleness signal
    verification.audits.delisting_audit uses, but standalone (no sample
    frame required) so this patch step can run right after ingestion,
    before any sample has been built.
    """
    if prices.is_empty():
        return []
    last_price = prices.group_by("ticker").agg(pl.col("date").max().alias("last_price_date"))
    stale = last_price.filter((pl.lit(as_of) - pl.col("last_price_date")).dt.total_days() > gap_days)
    return stale["ticker"].to_list()


def patch_delisted_ticker(ticker: str, existing_prices: pl.DataFrame) -> int:
    """Extend `ticker`'s price history with EODHD data past whatever
    `existing_prices` (this study's own already-ingested equity_eod,
    passed in rather than re-read so this is testable without the
    warehouse) already has for it.

    Tries the "Q" (Chapter 11) suffix first and prefers it whenever it has
    any data -- see module docstring for why this ordering, not "whichever
    has more rows", is the safe one. Falls back to the bare ticker's own
    post-cutoff data only if it resumes within
    BARE_TICKER_RESUME_WINDOW_DAYS of the last known date. Writes
    whichever series is used to the equity_eod table via the existing
    upsert (storage.write, key_cols=["ticker","date"]) so every downstream
    consumer -- the funnel, the CAR engine -- sees the extended history
    with no changes of its own. Returns the number of rows written (0 if
    neither variant produced anything usable).
    """
    own = existing_prices.filter(pl.col("ticker") == ticker.upper())
    last_known = own["date"].max() if not own.is_empty() else None
    start = (last_known + timedelta(days=1)).isoformat() if last_known else None

    q_df = fetch_eodhd(f"{ticker.upper()}Q.US", canonical_ticker=ticker, start=start)
    if not q_df.is_empty():
        storage.write("equity_eod", q_df, key_cols=["ticker", "date"], partition=ticker.upper())
        return q_df.height

    bare_df = fetch_eodhd(f"{ticker.upper()}.US", canonical_ticker=ticker, start=start)
    if not bare_df.is_empty() and last_known is not None:
        resume_date = bare_df["date"].min()
        gap = (resume_date - last_known).days
        if gap <= BARE_TICKER_RESUME_WINDOW_DAYS:
            storage.write("equity_eod", bare_df, key_cols=["ticker", "date"], partition=ticker.upper())
            return bare_df.height

    return 0


def patch_all_stale_tickers(as_of: date, gap_days: int = 90) -> dict[str, int]:
    """Orchestration entry point: reads the current equity_eod table,
    finds every ticker find_stale_tickers flags, and runs
    patch_delisted_ticker on each. Meant to run once, after the normal
    per-ticker Tiingo ingestion loop and before the sample funnel --
    every function it calls already writes straight to equity_eod via the
    existing upsert, so nothing downstream (funnel, CAR engine) needs any
    change to see the extended history.

    Returns {ticker: rows_patched} for every stale ticker found, including
    0 for ones neither EODHD variant could extend -- callers can use this
    to see exactly which tickers still have an unresolved gap.
    """
    prices = storage.read("equity_eod")
    stale = find_stale_tickers(prices, as_of=as_of, gap_days=gap_days)
    return {ticker: patch_delisted_ticker(ticker, prices) for ticker in stale}
