"""Full-universe ingestion, PRE_ANALYSIS_PLAN.md Addendum A. Run once,
before scripts/run_full_pipeline.py.

Discovers the disclosure-defined ticker universe via Quiver's bulk
endpoint, ingests every one-time global source, then per-ticker
prices/trades/SIC for every distinct ticker, and finally patches
delisted tickers via EODHD (Addendum C).

Deliberately does NOT pre-filter the discovered universe by any judgment
call about what "looks like" a real equity ticker -- confirmed live
before this script was written, Quiver's bulk feed's "Ticker" field
sometimes carries a bond CUSIP, a T-bill maturity description, or other
non-equity artifact instead of a real symbol (roughly 4% of the
5,046-ticker universe at verification time). Addendum A's own rule is
that Section 4's ticker_type=='ST' funnel step is the one place
common-stock filtering happens; this script leaves a malformed "ticker"
to fail cleanly there (or in its own per-ticker ingestion calls below,
logged, never silently dropped) rather than adding a second, undocumented
filtering judgment on top of an already-committed addendum.

Idempotent, not automatically resumable: every ingest_* call upserts on
its own key, so interrupting this script and re-running it will not
duplicate anything already written -- but it WILL re-request every
ticker's price/trade data from scratch, spending API quota again. For a
genuinely interrupted run, prefer manually trimming `universe` to the
tail that has not been processed yet over a blind re-run.
"""

from __future__ import annotations

from datetime import date

from congressional_sales import storage
from congressional_sales.sources.eodhd import patch_all_stale_tickers
from congressional_sales.sources.french import ingest_factors
from congressional_sales.sources.legislators import (
    ingest_committee_assignments,
    ingest_historical_committee_assignments,
    ingest_icpsr_crosswalk,
    ingest_legislator_terms,
)
from congressional_sales.sources.prices import ingest_prices
from congressional_sales.sources.quiver import discover_ticker_universe, ingest_congress_trades
from congressional_sales.sources.sic import ingest_sic_codes

# Matches SAMPLE_PERIOD_START/HOLDOUT_END in run_full_pipeline.py and
# run_holdout.py -- the full study period, 2014 through the most recent
# complete year (2025 for a 2026 run). Keep in sync with those scripts.
SAMPLE_PERIOD_START = date(2014, 1, 1)
SAMPLE_PERIOD_END = date(2025, 12, 31)

# Prices need history well before the sample period starts: the funnel's
# min_prior_trading_history floor is 60 sessions, and Model 2's
# four-factor estimation window looks back up to 250 sessions before an
# event -- so a disclosure filed in early January 2014 needs price data
# starting well before 2014. 2012-01-01 matches the depth used in this
# project's own earlier live sanity checks.
PRICE_HISTORY_START = "2012-01-01"

PROGRESS_EVERY = 100


def main() -> None:
    storage.paths().ensure()

    print("Discovering ticker universe (Addendum A)...")
    universe = discover_ticker_universe(SAMPLE_PERIOD_START, SAMPLE_PERIOD_END)
    print(f"  {len(universe)} distinct tickers named in a disclosure filed "
          f"{SAMPLE_PERIOD_START}..{SAMPLE_PERIOD_END}")
    if "SPY" not in universe:
        universe = ["SPY"] + universe
        print("  SPY added explicitly (it is the market benchmark and calendar "
              "anchor, not itself a ticker Congress discloses trading).")

    print("\nOne-time global sources...")
    print(f"  Fama-French factors: {ingest_factors()} rows")
    print(f"  Legislator terms: {ingest_legislator_terms()} rows")
    print(f"  Committee assignments (current): {ingest_committee_assignments()} rows")
    print(f"  ICPSR crosswalk: {ingest_icpsr_crosswalk()} rows")
    print(f"  Historical committee assignments: {ingest_historical_committee_assignments()} rows")

    print(f"\nPer-ticker ingestion for {len(universe)} tickers "
          f"(prices from {PRICE_HISTORY_START}, congress trades full history)...")
    price_failures: list[tuple[str, str]] = []
    trade_failures: list[tuple[str, str]] = []
    for i, ticker in enumerate(universe, start=1):
        try:
            ingest_prices(ticker, start=PRICE_HISTORY_START)
        except Exception as e:  # noqa: BLE001 -- deliberately broad: log and keep going
            price_failures.append((ticker, str(e)[:120]))
        try:
            ingest_congress_trades(ticker)
        except Exception as e:  # noqa: BLE001
            trade_failures.append((ticker, str(e)[:120]))
        if i % PROGRESS_EVERY == 0 or i == len(universe):
            print(f"  {i}/{len(universe)} tickers processed "
                  f"({len(price_failures)} price failures, {len(trade_failures)} trade failures so far)")

    print("\nSIC codes for the full universe...")
    print(f"  {ingest_sic_codes(universe)} tickers resolved to a SIC code")

    print("\nDelisting patch (Addendum C)...")
    result = patch_all_stale_tickers(universe=universe, as_of=SAMPLE_PERIOD_END)
    patched = {t: n for t, n in result.items() if n > 0}
    unresolved = sorted(t for t, n in result.items() if n == 0)
    print(f"  {len(patched)} tickers patched, {len(unresolved)} still unresolved")
    if unresolved:
        print(f"  Unresolved (logged, not silently dropped): {unresolved}")

    print(f"\nDone. Price ingestion failures: {len(price_failures)}, "
          f"trade ingestion failures: {len(trade_failures)}")
    if price_failures:
        print(f"  Sample price failures: {price_failures[:15]}")
    if trade_failures:
        print(f"  Sample trade failures: {trade_failures[:15]}")


if __name__ == "__main__":
    main()
