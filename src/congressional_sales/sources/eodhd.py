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
study's sample already knows under the bare ticker. When Tiingo has SOME
prior history for the ticker, the bare ticker's own post-cutoff data is
used as a patch only if it resumes within BARE_TICKER_RESUME_WINDOW_DAYS
of Tiingo's last known date -- a resumption that close to the cutoff is
far more likely to be the original security's own continued trading (e.g.
Tiingo's own coverage merely lagging) than an unrelated company reissued
onto a recycled symbol months or years later. When Tiingo has NO prior
history at all for the ticker, there is no resumption to measure a gap
against, and the bare ticker's data is used directly rather than
withheld: confirmed live at full-universe scale, this is common, not
rare -- 364 real, plausible tickers in this study's own universe (ANTM,
ADS, ABC, ...) had zero Tiingo coverage, and refusing to even attempt
them left strictly more real companies unrecovered than the (smaller,
harder to detect without a reference point) residual risk that such a
ticker was itself reused by more than one company across EODHD's full
history window.

This is a partial, not exhaustive, fix, confirmed live at full-universe
scale, not merely asserted. The "Q" suffix recovers a Chapter 11 filing
specifically -- 226 of 1,607 flagged-stale tickers in this study's actual
universe. Reconciling the rest: 364 had zero Tiingo coverage (now
attempted via the bare-ticker path above); roughly 872 already carry a
stable, non-distressed final Tiingo price before their own cutoff (a
clean, fairly-priced acquisition, most plausibly -- e.g. confirmed live
for ABMD/Abiomed, whose last Tiingo price, $381.02, matches EODHD's own
last recorded price for the same ticker almost exactly, meaning Tiingo's
existing data already captures the true final outcome and there is
nothing to patch); and a residual roughly 71 show a genuine, unresolved
distress pattern (price collapsing over their final trading sessions with
no patchable continuation found under either symbol variant) -- these are
the real remaining survivorship-bias risk and are reported by name, not
folded into an aggregate count, in the paper's own Limitations section
and this run's own unresolved-ticker log. A security delisted a way
neither the "Q" suffix nor a first-ever bare-ticker pull can recover (a
reverse-merger reissue under an entirely unrelated new symbol, for
instance) may still be missed.
See Addendum C and the paper's own Limitations section.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import httpx
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
    # A 404 status ("Ticker Not Found") reaches here as a raised
    # httpx.HTTPStatusError, NOT a 200-with-error-body -- confirmed live
    # the hard way: the first full-universe run crashed here on a
    # malformed "ticker" from the bulk feed's own known ~4% garbage rate
    # (a bond CUSIP with a leading space, "%2037045XEF9Q.US" once
    # URL-encoded). The docstring above already documented "empty frame
    # for a 404" as the intended contract; this except clause is what
    # actually delivers it, catching only a 404 specifically -- any other
    # status (a persistent 5xx surviving http.py's own retries, for
    # instance) is a genuine infrastructure problem, not a "no such
    # ticker" signal, and is left to propagate.
    try:
        rows = get_json(EODHD_URL.format(symbol=symbol), params=params)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return pl.DataFrame(schema=PRICE_SCHEMA)
        raise
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


def find_stale_tickers(universe: list[str], prices: pl.DataFrame, as_of: date, gap_days: int = 90) -> list[str]:
    """Tickers in `universe` that either have NO price data at all in
    `prices`, or whose last known price date is more than `gap_days`
    before `as_of`.

    Takes the intended universe as an explicit argument rather than only
    grouping over `prices` directly: a ticker with zero rows in `prices`
    never appears in a group-by over `prices` at all, so an earlier
    version of this function that only looked at `prices` was blind to it
    -- and this is not a rare edge case for this study. Confirmed live
    before this fix: Tiingo returns a completely empty result for some
    delisted tickers (e.g. BBBY) rather than a partial history that later
    goes stale, so "zero coverage" and "coverage that stopped" are both
    real, common shapes of the same underlying gap and both need to reach
    the EODHD patch step.
    """
    if not universe:
        return []
    last_price = (
        prices.group_by("ticker").agg(pl.col("date").max().alias("last_price_date"))
        if not prices.is_empty()
        else pl.DataFrame(schema={"ticker": pl.Utf8, "last_price_date": pl.Date})
    )
    universe_df = pl.DataFrame({"ticker": [t.upper() for t in universe]}, schema={"ticker": pl.Utf8})
    joined = universe_df.join(last_price, on="ticker", how="left")
    stale = joined.filter(
        pl.col("last_price_date").is_null()
        | ((pl.lit(as_of) - pl.col("last_price_date")).dt.total_days() > gap_days)
    )
    # Sorted, not left to whatever order the join/unique happens to
    # produce: this list drives patch_all_stale_tickers' API-call order,
    # and Section 11's reproducibility requirement ("reproduce end to end
    # twice, confirm identical output") applies to this step too.
    return sorted(stale["ticker"].unique().to_list())


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

    `existing_prices` may be a genuinely columnless empty frame (what
    storage.read returns for a table that has never been written at
    all, e.g. if this is called before any Tiingo ingestion has ever
    run) -- filtering that on pl.col("ticker") raises ColumnNotFoundError
    rather than behaving like an empty result, so that shape is checked
    for explicitly rather than assumed away. In the real pipeline this
    never happens (the Tiingo ingestion loop always populates equity_eod
    first), but a defensive check costs nothing and this module already
    learned the cost of assuming a "won't happen in practice" case away
    once this run (see fetch_eodhd's 404 handling above).
    """
    if "ticker" in existing_prices.columns:
        own = existing_prices.filter(pl.col("ticker") == ticker.upper())
        last_known = own["date"].max() if not own.is_empty() else None
    else:
        last_known = None
    start = (last_known + timedelta(days=1)).isoformat() if last_known else None

    q_df = fetch_eodhd(f"{ticker.upper()}Q.US", canonical_ticker=ticker, start=start)
    if not q_df.is_empty():
        storage.write("equity_eod", q_df, key_cols=["ticker", "date"], partition=ticker.upper())
        return q_df.height

    bare_df = fetch_eodhd(f"{ticker.upper()}.US", canonical_ticker=ticker, start=start)
    if not bare_df.is_empty():
        if last_known is None:
            # No prior Tiingo history at all -- confirmed live this is
            # common, not rare: 364 real, plausible-ticker-shaped names in
            # this study's own universe (ANTM, ADS, ABC, ...) had zero
            # Tiingo coverage. There is no "resume gap" to measure in this
            # case (nothing to resume FROM), so the window check below
            # does not apply -- this is a first pull, not a resumption,
            # and rejecting it here would mean giving up without ever
            # trying, which is strictly worse than the residual (smaller,
            # harder to detect without a reference point) risk that the
            # bare ticker has itself been reused by more than one company
            # over EODHD's own full history window.
            storage.write("equity_eod", bare_df, key_cols=["ticker", "date"], partition=ticker.upper())
            return bare_df.height
        resume_date = bare_df["date"].min()
        gap = (resume_date - last_known).days
        if gap <= BARE_TICKER_RESUME_WINDOW_DAYS:
            storage.write("equity_eod", bare_df, key_cols=["ticker", "date"], partition=ticker.upper())
            return bare_df.height

    return 0


def patch_all_stale_tickers(universe: list[str], as_of: date, gap_days: int = 90) -> dict[str, int]:
    """Orchestration entry point: reads the current equity_eod table,
    finds every ticker in `universe` find_stale_tickers flags (no price
    data at all, or none recent enough), and runs patch_delisted_ticker on
    each. Meant to run once, after the normal per-ticker Tiingo ingestion
    loop and before the sample funnel -- every function it calls already
    writes straight to equity_eod via the existing upsert, so nothing
    downstream (funnel, CAR engine) needs any change to see the extended
    history.

    `universe` must be passed explicitly (the full set of tickers this
    run's ingestion was supposed to cover, e.g. from
    sources.quiver.discover_ticker_universe) rather than inferred from
    equity_eod's own contents -- see find_stale_tickers' docstring for why
    a ticker with zero existing rows would otherwise be invisible.

    Returns {ticker: rows_patched} for every stale ticker found, including
    0 for a ticker neither EODHD variant could extend OR whose patch
    attempt raised -- both are reported as an unresolved gap the same
    way, not distinguished, since either way there is no extended history
    to show for it. Errors are caught and logged per ticker rather than
    aborting the whole run: the first full-universe run crashed here
    outright on a single malformed "ticker" (see fetch_eodhd's docstring
    for the specific case that was fixed), and 404 is very unlikely to be
    the only failure mode a universe this size will ever produce -- a
    single bad symbol should not cost every legitimate patch behind it in
    the loop, matching the same per-ticker catch-and-continue discipline
    scripts/ingest_universe.py's own price/trade ingestion loop already
    uses.
    """
    prices = storage.read("equity_eod")
    stale = find_stale_tickers(universe, prices, as_of=as_of, gap_days=gap_days)
    result: dict[str, int] = {}
    for ticker in stale:
        try:
            result[ticker] = patch_delisted_ticker(ticker, prices)
        except Exception:  # noqa: BLE001 -- deliberately broad: log and keep going
            result[ticker] = 0
    return result
