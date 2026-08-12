"""The 18-month holdout evaluation -- PRE_ANALYSIS_PLAN.md Section 4/9
item 10: run LAST, run ONCE. Do not re-run after seeing its result; if a
methodology bug is found here, the correct response is to log it as a
limitation, not to quietly patch and re-run."""

from __future__ import annotations

from datetime import date

import polars as pl

from congressional_sales import storage
from congressional_sales.events import car
from congressional_sales.events.attach import attach_car_bhar
from congressional_sales.models import model2
from congressional_sales.outputs import tables
from congressional_sales.sample import classify
from congressional_sales.sample.funnel import build_sample
from congressional_sales.sample.screens import screen1_rebalancing, screen2_tax_management, screen3_liquidation

# Keep in sync with run_full_pipeline.py -- these constants define the
# boundary between the sample the study was developed on and the sample it is
# validated against, and a mismatch between the two scripts either leaks
# holdout data into development or silently drops transactions from both.
# Section 4: "Period: 2014 through the most recent complete year. Hold out the
# final 18 months as an untouched validation sample." Set for a 2026 run: most
# recent complete year is 2025, final 18 months are 2024-07-01 .. 2025-12-31.
SAMPLE_PERIOD_START = date(2014, 1, 1)
HOLDOUT_START = date(2024, 7, 1)
HOLDOUT_END = date(2025, 12, 31)

PRIMARY_CAR_COL = "car_four_factor_90"

EXCLUSION_FLAGS = ["excluded_rebalancing", "excluded_tax_management", "excluded_liquidation"]

# Canonical total row order -- see the matching comment in run_full_pipeline.py.
# funnel.build_sample's dedupe and joins do not pin polars' row order, so its
# output order varies from process to process; these are the columns it
# deduplicates on, so after dedupe this sort is a total order.
CANONICAL_ORDER = ["ticker", "bioguide_id", "transaction_date", "transaction", "amount_range"]


def _populate_size_proxies(sample_with_car: pl.DataFrame, prices: pl.DataFrame) -> dict:
    """(ticker, report_date) -> trailing dollar-volume size proxy.

    Model 2's `log_size` control is looked up from this dict by
    build_model2_frame. An EMPTY dict is not a benign placeholder: every row's
    log_size goes null, build_model2_frame's own
    drop_nulls(["car", "log_size", "prior_12mo_return"]) then empties the frame,
    and run_model2 crashes inside AbsorbingLS on a zero-row array.
    """
    sessions = car.sessions_from_prices(prices)
    pairs = sample_with_car.select("ticker", "report_date").unique()
    return {
        (row["ticker"], row["report_date"]): car.size_proxy(row["ticker"], row["report_date"], prices, sessions)
        for row in pairs.iter_rows(named=True)
    }


def _pl_or(cols: list[str]) -> pl.Expr:
    expr = pl.col(cols[0])
    for c in cols[1:]:
        expr = expr | pl.col(c)
    return expr


def main() -> None:
    storage.paths().ensure()
    # The funnel, the H3/H4 classification and Screens 1-3 are all run over the
    # FULL study period and only then sliced down to the holdout window --
    # they are NOT run on an 18-month frame. Every one of those steps reads a
    # member's trading HISTORY out of the frame it is handed, so handing it 18
    # months of data does not just weaken it, it breaks it:
    #
    #  * classify.is_routine_trader asks whether the member traded the same
    #    calendar month in each of the THREE PRIOR YEARS, looked up in the frame
    #    it is given. An 18-month frame contains at most one prior year, so
    #    is_routine is False for EVERY holdout row, by construction, on any
    #    dataset. `opportunistic` then becomes a CONSTANT 1, which makes
    #    sale + opportunistic - sale*opportunistic identically equal to the
    #    intercept -- and run_model2 dies with AbsorbingEffectError before
    #    producing any holdout result at all. Confirmed empirically against a
    #    synthetic warehouse before this script was finalized: the earlier draft
    #    (screens + classification applied to build_sample(period_start=
    #    HOLDOUT_START)) crashed 100% of the time, not intermittently.
    #  * screen1's rebalancing rule looks for an offsetting purchase within 90
    #    days, screen2 looks for the last prior purchase of the same ticker, and
    #    screen3 accumulates the member's signed exposure from the start of the
    #    frame. Restricted to the holdout window, all three silently see a
    #    truncated history and under-screen the boundary months.
    #
    # This is also what makes the holdout a genuine re-run of the SAME primary
    # specification run_full_pipeline.py estimates, which is the entire point of
    # Section 9 item 10. It leaks nothing: pre-holdout transactions inform only
    # each holdout row's own classification and screen flags -- exactly as they
    # do in the main run -- and no holdout OUTCOME enters anything.
    #
    # period_end is pinned to HOLDOUT_END rather than left to build_sample's
    # date.today() default: Section 4 ends the study period at the most recent
    # COMPLETE year, so letting it run to today would pull partial-year
    # transactions into the holdout that the pre-registered period excludes.
    result = build_sample(period_start=SAMPLE_PERIOD_START, period_end=HOLDOUT_END)
    if result.sample.is_empty():
        raise SystemExit(
            f"No transactions survived the sample funnel for {SAMPLE_PERIOD_START}..{HOLDOUT_END}. "
            "Ingest the warehouse first (see README.md 'Reproducing this study'), and confirm "
            "CONGRESS_SALES_HOME points at it."
        )
    prices, factors = storage.read("equity_eod"), storage.read("ff_factors")
    sic = storage.read("sic_codes")
    terms, assignments = storage.read("legislator_terms"), storage.read("committee_assignments")
    # Empty (not None) if never ingested -- see the matching comment in
    # run_full_pipeline.py; classify.committee_match treats that exactly
    # like historical_assignments=None.
    historical_assignments = storage.read("committee_assignments_historical")

    # Section 9 item 10 is the last of "10 checks, primary specification
    # only" (Section 9's own header) -- it re-runs the SCREENED-sample
    # primary specification on the holdout period, not an unscreened
    # variant. The earlier draft of this script attached CAR and ran
    # Model 2 directly on build_sample()'s raw output, skipping Screens
    # 1-4 and the H3/H4 classification entirely -- silently testing a
    # different (unscreened) specification than every other robustness
    # check, and leaving is_routine/committee_match absent from the
    # frame entirely. build_model2_frame reads those via row.get(...)
    # (not the strict ValueError guard industry/prior_12mo_return get),
    # so a missing column doesn't raise -- it silently defaults
    # opportunistic to a CONSTANT 1 and committee_match to a CONSTANT 0
    # for every row, the exact same class of intercept-collinearity bug
    # already found and fixed in Task 19 (chamber/party) and worked
    # around in Task 23's robustness fixture. Fixed by applying the same
    # screening funnel run_full_pipeline.py uses for its `screened`
    # sample, before attaching CAR.
    #
    # Classification runs BEFORE the screens and on the unscreened frame, for
    # the same reason run_full_pipeline.py does it in that order.
    classified = classify.committee_match(
        classify.is_routine_trader(result.sample.sort(CANONICAL_ORDER)), assignments, sic,
        historical_assignments=historical_assignments,
    )
    screened_all = screen3_liquidation(
        screen2_tax_management(screen1_rebalancing(classified), prices), terms
    ).filter(~(_pl_or(EXCLUSION_FLAGS))).sort(CANONICAL_ORDER)
    # Only now drop to the holdout window. Everything above needed the full
    # history; everything below -- CAR attachment, size proxies, Model 2 -- must
    # see holdout transactions and nothing else.
    screened = screened_all.filter(pl.col("report_date") >= HOLDOUT_START)
    if screened.is_empty():
        raise SystemExit(
            f"No transaction in {HOLDOUT_START}..{HOLDOUT_END} survived Screens 1-3; "
            "nothing left to evaluate."
        )

    with_car = attach_car_bhar(screened, prices, factors, sic)
    size_proxies = _populate_size_proxies(with_car, prices)
    frame = model2.build_model2_frame(with_car, size_proxies, terms, PRIMARY_CAR_COL)
    holdout_result = model2.run_model2(frame)
    print(f"Holdout window: {HOLDOUT_START} .. {HOLDOUT_END} -- {screened.height} screened holdout "
          f"transactions (from a {result.sample.height}-transaction full-period funnel, "
          f"{screened_all.height} screened overall) -> {frame.height} estimated")
    print("HOLDOUT RESULT (Section 9 item 10 -- run once, report as-is):")
    print(holdout_result)

    # T8 (Section 10) -- this is this script's whole reason for writing to
    # `outputs/` at all: printing holdout_result to stdout, as the earlier
    # version of this script did exclusively, gives Section 9 item 10 no
    # durable record if that terminal output isn't captured by hand. Written
    # as its own file rather than folded into run_full_pipeline.py's
    # paper.md, since this script runs later, once, against a warehouse
    # state paper.md was already generated from -- rewriting paper.md here
    # would require re-deriving T1-T7 this script never computes.
    storage.paths().ensure()
    t8 = tables.t8_holdout(holdout_result)
    t8.write_csv(storage.paths().outputs / "t8_holdout.csv")
    print(f"Wrote T8 (holdout results) to {storage.paths().outputs / 't8_holdout.csv'}")

    # Append T8 to paper.md if run_full_pipeline.py has already produced one
    # in this same outputs/ directory -- Section 10's output list treats T8
    # as part of one paper, and appending it here (rather than requiring a
    # second manual step) is the only way this script can satisfy that
    # without re-deriving T1-T7. This script is documented to run once, last
    # (module docstring); re-running it against the same paper.md would
    # append a second "## Table T8" section rather than replace the first,
    # which is a re-run problem this project's own protocol already forbids
    # ("do not re-run after seeing its result"), not a new failure mode this
    # append needs to guard against.
    paper_path = storage.paths().outputs / "paper.md"
    if paper_path.exists():
        with paper_path.open("a") as f:
            f.write("\n## Table T8\n\n")
            f.write(t8.to_pandas().to_markdown(index=False))
            f.write("\n")
        print(f"Appended Table T8 to {paper_path}")


if __name__ == "__main__":
    main()
