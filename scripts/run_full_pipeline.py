"""End-to-end pipeline: ingest -> sample -> screen -> attach CAR -> models
-> robustness -> outputs. Excludes the 18-month holdout period entirely
(see run_holdout.py, run last and once only, per PRE_ANALYSIS_PLAN.md
Section 4/9)."""

from __future__ import annotations

from datetime import date, timedelta

import matplotlib.pyplot as plt
import polars as pl

from congressional_sales import storage
from congressional_sales.events import car
from congressional_sales.events.attach import attach_car_bhar
from congressional_sales.events.permutation import random_control_test
from congressional_sales.models import model2, model3, multiple_comparisons
from congressional_sales.outputs import figures, paper, tables
from congressional_sales.robustness import run_robustness_suite, year_by_year_effects
from congressional_sales.sample import classify, descriptive
from congressional_sales.sample.funnel import build_sample
from congressional_sales.sample.screens import screen1_rebalancing, screen2_tax_management, screen3_liquidation
from congressional_sales.verification.audits import delisting_audit, nan_audit, ticker_reuse_audit
from congressional_sales.verification.hand_check import build_worksheet, select_worksheet_sample

# models.model1 is NOT imported directly here -- it doesn't need to be.
# tables.t4_mean_car (Task 24, revised during the whole-branch review) now
# routes through models.model1.unconditional_means_table itself, so T4
# ("Mean CAR by transaction type and horizon, all three adjustment methods",
# Section 10) carries member- and month-clustered SEs, satisfying Section
# 7's "report both" on the unconditional sale-vs-purchase CAR comparison
# (the most direct H1/H2 statistic). This was an open, undecided question
# earlier in this build (see git history / progress.md for the prior
# state); it has since been resolved by folding Model 1's output into T4
# rather than reporting it separately, since T4's Section 10 description IS
# Model 1's output shape and adding its pre-registered SEs to it is not a
# new, post-hoc specification.
#
# models.multiple_comparisons.run_eighteen_variant_grid fits Section 8's
# full 18-cell (horizon x method x sample) grid and feeds bh_adjust /
# bh_corrected_threshold below -- see the note at the build_paper_markdown
# call for why this matters: without it, no result this pipeline produces
# could be certified as "supportive" under Section 12's own rule.

# --- Sample period constants (PRE_ANALYSIS_PLAN.md Section 4) ------------------
# "Period: 2014 through the most recent complete year. Hold out the final 18
# months as an untouched validation sample."
#
# These constants are set for a run made in 2026: the most recent COMPLETE year
# is 2025, so the study period is 2014-01-01 .. 2025-12-31 (2025-12-31 is
# run_holdout.py's HOLDOUT_END -- this script never reads that far, since it
# excludes the holdout window entirely, so it is not re-declared here) and its
# final 18 months are 2024-07-01 .. 2025-12-31. Re-confirm and update them when
# the study period rolls forward -- do not leave them stale and do not
# hardcode silently.
SAMPLE_PERIOD_START = date(2014, 1, 1)
HOLDOUT_START = date(2024, 7, 1)  # first day of the final 18 months; keep in sync with run_holdout.py
# build_sample's period filter is INCLUSIVE on both ends (report_date >= start
# AND report_date <= end), so the main sample must stop the day BEFORE
# HOLDOUT_START. Passing period_end=HOLDOUT_START directly would place every
# transaction reported exactly on HOLDOUT_START in BOTH this run and the holdout
# run -- a one-day leak out of the sample Section 4 requires be left untouched.
MAIN_PERIOD_END = HOLDOUT_START - timedelta(days=1)

# The study's single pre-registered primary specification (Section 7): the
# `sale` coefficient at the 90-day horizon, four-factor adjusted.
PRIMARY_CAR_COL = "car_four_factor_90"
PRIMARY_HORIZON = 90

# F3/F4/F5 average an event-time CAR path across a capped, SEEDED subsample of
# transactions rather than the whole sample. car.event_time_series walks ~210
# trading sessions per transaction and is not vectorized, so averaging across
# every transaction in a full-scale sample is compute-bound with no visual
# payoff (the mean path stabilizes long before then). The seed makes the choice
# deterministic, which Section 11's "reproduce twice, confirm identical output"
# requirement demands.
EVENT_SERIES_MAX_TXNS = 100
SUBSAMPLE_SEED = 42

# F6's permutation test (Section 8) is pre-registered at 1,000 iterations. Each
# iteration recomputes the primary four-factor CAR for every transaction in the
# set, so the transaction set is capped: 1,000 x N four-factor CAR computations
# is the binding cost -- uncapped, that's hours of compute on a full-scale
# sample with no automated test able to exercise it end to end in reasonable
# time. Decided, not left open: keep the cap as a PERMANENT, documented
# deviation from Section 8's literal "the same tickers" -- reported in
# outputs/paper.py's LIMITATIONS block on every run, not a TODO to lift later.
# Set PERMUTATION_MAX_TXNS = None to run the full screened-sale set instead,
# if a specific run's compute budget allows it.
PERMUTATION_MAX_TXNS: int | None = 50
PERMUTATION_ITERATIONS = 1000
PERMUTATION_SEED = 42  # Section 11 reproducibility: an unseeded permutation
# test produces a different F6 on every run and can never satisfy "reproduce
# end to end twice and confirm identical output".

# F8 refits the calendar-time four-factor regression to recover month-by-month
# abnormal returns; below this many months that 5-parameter fit is not
# meaningfully identified and the figure is skipped rather than drawn from noise.
MIN_ALPHA_MONTHS = 12

EXCLUSION_FLAGS = ["excluded_rebalancing", "excluded_tax_management", "excluded_liquidation"]

# A canonical, total row order re-imposed on the sample after the funnel and
# again after the screens. This is NOT cosmetic in either of two separate ways:
#
# 1. Reproducibility (Section 11's "reproduce end to end twice, on different
#    days, and confirm identical output"). funnel.build_sample ends in
#    df.unique(subset=[...], keep="first") and several joins, none of which
#    pass polars' maintain_order, so the ROW ORDER of its output varies from
#    process to process. Verified empirically: three separate runs of
#    build_sample over the identical warehouse produced three different row
#    orders and therefore three different 20-transaction hand-check
#    worksheets (select_worksheet_sample is a seeded sample -- deterministic
#    given an order, but there was no stable order to give it). The same
#    instability would reach F3-F6's seeded subsamples.
# 2. screen3_liquidation's own CONTENT, not just presentation. It computes
#    cumulative net exposure via cum_sum().over("bioguide_id"), sorted only on
#    ["bioguide_id", "transaction_date"] -- a partial key when a member has
#    same-day transactions, which polars does not order deterministically on
#    its own. Verified empirically: three same-day rows for one member fed in
#    canonical vs. reversed order produced DIFFERENT excluded_liquidation
#    flags ([F,T,T] vs [F,F,F]), not just a different row order. The sort
#    below must run BEFORE the screens for this reason -- moving it to after
#    the screens (e.g. during a future refactor) would silently reintroduce
#    this as a correctness bug, not just a reproducibility one.
#
# These are exactly the columns the funnel deduplicates on, so after dedupe they
# are unique and this sort is a genuine total order, not a partial one that
# leaves ties free to move. Fixing funnel.py itself would be the better repair;
# that module is out of this task's scope, so the order is pinned here instead.
CANONICAL_ORDER = ["ticker", "bioguide_id", "transaction_date", "transaction", "amount_range"]


def pl_or(cols: list[str]) -> pl.Expr:
    expr = pl.col(cols[0])
    for c in cols[1:]:
        expr = expr | pl.col(c)
    return expr


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


def _ticker_price_slicer(prices: pl.DataFrame, market_ticker: str = "SPY"):
    """Return a cached ticker -> {ticker, market_ticker} price-slice lookup.

    Pure performance, zero effect on results. Every function in events.car is a
    pure function of the `prices` frame it is handed (see that module's
    docstring), and market_adjusted/four_factor CAR only ever read the event
    ticker's rows and the market ticker's rows -- so a two-ticker slice yields
    numerically identical output to the full frame while making each of the
    hundreds of per-session `prices.filter(...)` scans inside those functions
    two orders of magnitude cheaper. The market ticker is always retained, so
    sessions_from_prices derives the identical trading calendar from the slice.
    """
    cache: dict[str, pl.DataFrame] = {}

    def slice_for(ticker: str) -> pl.DataFrame:
        if ticker not in cache:
            cache[ticker] = prices.filter(pl.col("ticker").is_in([ticker, market_ticker]))
        return cache[ticker]

    return slice_for


def _mean_event_series(sample: pl.DataFrame, slice_for, max_txns: int = EVENT_SERIES_MAX_TXNS) -> dict:
    """Average car.event_time_series across a seeded subsample of `sample`.

    There is no canonical single event-time path for a whole sample -- each
    transaction has its own -- so F3/F4/F5 plot the MEAN path across
    transactions, offset by offset, which is the standard event-study
    presentation. Offsets where every sampled transaction ran out of usable
    sessions stay None; figures._plot_event_series already drops those.
    """
    if sample.is_empty():
        return {}
    subset = sample.sample(n=max_txns, seed=SUBSAMPLE_SEED) if sample.height > max_txns else sample
    paths = [
        car.event_time_series(row["ticker"], row["transaction_date"], slice_for(row["ticker"]))
        for row in subset.iter_rows(named=True)
    ]
    offsets = sorted({o for p in paths for o in p})
    mean_path: dict[int, float | None] = {}
    for offset in offsets:
        values = [p[offset] for p in paths if p.get(offset) is not None]
        mean_path[offset] = sum(values) / len(values) if values else None
    return mean_path


def _cumulative_alpha_series(portfolio_returns: pl.DataFrame, factors: pl.DataFrame) -> tuple[list, list]:
    """Month-by-month cumulative abnormal return of the calendar-time portfolio.

    model3.calendar_time_alpha returns a single point estimate, so there is no
    existing producer of the time SERIES F8 plots. This refits exactly the same
    regression it fits -- same monthly_factor_returns input, same
    (portfolio_return - rf) dependent variable, same four factors -- and
    cumulates (alpha_hat + residual_t), i.e. the portfolio's realized return net
    of its factor-model-predicted return, which is the textbook cumulative
    calendar-time alpha. The intercept it recovers is by construction identical
    to alpha_result["alpha"].

    This is the ONE place this orchestration script contains analysis logic
    rather than pure composition. It belongs in models/model3.py (as e.g.
    calendar_time_alpha_series) if F8 is kept; it lives here only because
    promoting it would mean editing an already-reviewed module.
    """
    import numpy as np
    import statsmodels.api as sm

    monthly_factors = model3.monthly_factor_returns(factors)
    merged = portfolio_returns.join(monthly_factors, on="month", how="inner").sort("month")
    if merged.height < MIN_ALPHA_MONTHS:
        return [], []
    y = (merged["portfolio_return"] - merged["rf"]).to_numpy()
    X = sm.add_constant(merged.select("mkt_rf", "smb", "hml", "mom").to_numpy())
    fit = sm.OLS(y, X).fit()
    abnormal = float(fit.params[0]) + fit.resid
    if not np.all(np.isfinite(abnormal)):
        return [], []
    return merged["month"].to_list(), [float(v) for v in np.cumsum(abnormal)]


def _save(fig, key: str, filename: str, figure_paths: dict[str, str]) -> None:
    fig.savefig(storage.paths().outputs / filename)
    plt.close(fig)
    figure_paths[key] = filename
    print(f"  {key} -> {filename}")


def _write_figures(
    result,
    screened: pl.DataFrame,
    screened_with_car: pl.DataFrame,
    prices: pl.DataFrame,
    factors: pl.DataFrame,
    portfolio_returns: pl.DataFrame,
    size_proxies: dict,
    terms: pl.DataFrame,
) -> dict[str, str]:
    """Generate and save F1-F8 (Section 10). Returns {figure key -> filename}.

    Filenames are relative, and paper.md is written into the same directory, so
    the markdown image links resolve without any path rewriting.
    """
    # These scripts only ever savefig -- never show -- so force the
    # non-interactive backend rather than depending on whatever GUI toolkit
    # happens to exist on the machine running the reproduction.
    plt.switch_backend("Agg")

    figure_paths: dict[str, str] = {}
    slice_for = _ticker_price_slicer(prices)
    sales = screened.filter(pl.col("transaction") == "Sale")

    print("Figures:")
    _save(figures.f1_sample_funnel(result), "F1", "f1_sample_funnel.png", figure_paths)
    _save(figures.f2_filing_lag_histogram(descriptive.filing_lag_days(screened)), "F2", "f2_filing_lag.png", figure_paths)

    # F3: sales vs. purchases (H1/H2). F4/F5 split the SALES only -- H3 and H4
    # are both hypotheses about "the sale effect", and figures.py titles both
    # panels accordingly.
    _save(
        figures.f3_event_time_car(
            _mean_event_series(sales, slice_for),
            _mean_event_series(screened.filter(pl.col("transaction") == "Purchase"), slice_for),
        ),
        "F3", "f3_event_time_car.png", figure_paths,
    )
    _save(
        figures.f4_event_time_car_by_routine(
            _mean_event_series(sales.filter(~pl.col("is_routine")), slice_for),
            _mean_event_series(sales.filter(pl.col("is_routine")), slice_for),
        ),
        "F4", "f4_event_time_car_by_routine.png", figure_paths,
    )
    _save(
        figures.f5_event_time_car_by_committee_match(
            _mean_event_series(sales.filter(pl.col("committee_match")), slice_for),
            _mean_event_series(sales.filter(~pl.col("committee_match")), slice_for),
        ),
        "F5", "f5_event_time_car_by_committee_match.png", figure_paths,
    )

    # F6: the Section 8 random-control permutation test, run on the primary
    # specification (four-factor CAR, 90-day horizon) so the null distribution
    # is the null distribution of the actual pre-registered test.
    permutation_sales = sales
    if PERMUTATION_MAX_TXNS is not None and permutation_sales.height > PERMUTATION_MAX_TXNS:
        permutation_sales = permutation_sales.sample(n=PERMUTATION_MAX_TXNS, seed=SUBSAMPLE_SEED)
    if not permutation_sales.is_empty():
        transactions = [(r["ticker"], r["transaction_date"]) for r in permutation_sales.iter_rows(named=True)]
        rc = random_control_test(
            transactions,
            lambda ticker, event_date: car.four_factor_car(
                ticker, event_date, PRIMARY_HORIZON, slice_for(ticker), factors
            ),
            period_start=SAMPLE_PERIOD_START,
            period_end=MAIN_PERIOD_END,
            sessions=car.sessions_from_prices(prices),
            n_iterations=PERMUTATION_ITERATIONS,
            seed=PERMUTATION_SEED,
        )
        if rc["simulated_means"]:
            _save(
                figures.f6_random_control_distribution(rc["simulated_means"], rc["actual_mean"]),
                "F6", "f6_random_control.png", figure_paths,
            )
            print(f"  F6 permutation: actual={rc['actual_mean']:.6g} "
                  f"percentile={rc['percentile']:.4g} iterations_used={rc['n_iterations_used']}")
        else:
            print("  F6 SKIPPED: no permutation iteration produced a usable simulated mean.")

    # F7 (year-by-year effect, Section 9 robustness item 2): beta_sale
    # re-estimated within each calendar year via
    # robustness.year_by_year_effects, which fits model2.run_model2(...,
    # absorb_year=False) per year -- YearFE is degenerate on a single-year
    # subset (constant, one level) and controls for nothing there anyway;
    # MemberFE and IndustryFE remain absorbed exactly as in the primary
    # specification. Only years that actually fit (non-null beta_sale) are
    # plotted; a too-thin or degenerate year reports a None row there and is
    # dropped here rather than plotted as a fabricated zero-width point.
    year_effects = year_by_year_effects(screened_with_car, size_proxies, terms, car_col=PRIMARY_CAR_COL)
    fitted_years = year_effects.filter(pl.col("beta_sale").is_not_null())
    if fitted_years.height >= 2:
        _save(
            figures.f7_year_by_year_effect(
                fitted_years["year"].to_list(), fitted_years["beta_sale"].to_list(),
                fitted_years["ci_lower"].to_list(), fitted_years["ci_upper"].to_list(),
            ),
            "F7", "f7_year_by_year_effect.png", figure_paths,
        )
    else:
        print(f"  F7 SKIPPED: only {fitted_years.height} of {year_effects.height} calendar years in the "
              "screened sample fit the primary specification (too few observations, or a degenerate "
              "fixed-effects structure, in the rest) -- fewer than 2 points to plot.")

    months, cumulative_alpha = _cumulative_alpha_series(portfolio_returns, factors)
    if months:
        _save(
            figures.f8_calendar_time_alpha(months, cumulative_alpha),
            "F8", "f8_calendar_time_alpha.png", figure_paths,
        )
    else:
        print(f"  F8 SKIPPED: fewer than {MIN_ALPHA_MONTHS} months of calendar-time portfolio returns "
              "overlap the factor series -- a four-factor fit there would be noise, not alpha.")

    return figure_paths


def main() -> None:
    # ensure() creates raw/, parquet/, and outputs/ if they don't exist --
    # required before any write_csv/write_text call below. Without this,
    # the script crashes with FileNotFoundError on a genuinely fresh
    # clone/environment where outputs/ has never been created (confirmed
    # empirically before this task was built: outputs/ is not tracked in
    # git and write_csv does not auto-create parent directories).
    storage.paths().ensure()

    result = build_sample(period_start=SAMPLE_PERIOD_START, period_end=MAIN_PERIOD_END)
    if result.sample.is_empty():
        raise SystemExit(
            "No transactions survived the sample funnel. Ingest the warehouse first "
            "(see README.md 'Reproducing this study'), and confirm CONGRESS_SALES_HOME "
            "points at it."
        )
    prices, factors = storage.read("equity_eod"), storage.read("ff_factors")
    terms, assignments = storage.read("legislator_terms"), storage.read("committee_assignments")
    sic = storage.read("sic_codes")
    # Empty (not None) if ingest_historical_committee_assignments() was
    # never run -- classify.committee_match treats that identically to
    # historical_assignments=None (falls back to the current-only
    # snapshot for every row), so this script works unchanged whether or
    # not the historical source has been ingested.
    historical_assignments = storage.read("committee_assignments_historical")

    # is_routine (H3) and committee_match (H4) are classified ONCE, on the
    # unscreened sample, before splitting into unscreened/screened -- not
    # separately on each. Two reasons, both load-bearing:
    #  1. Section 4 states "Report main results on both the unscreened and
    #     screened samples. The gap between them is itself informative" --
    #     a meaningful gap requires the SAME opportunistic/committee_match
    #     classification framework under both, not two different ones.
    #  2. is_routine_trader's classification ("traded in the same calendar
    #     month in each of the three prior years") is computed from every
    #     row's transaction_date PRESENT IN THE FRAME IT'S GIVEN -- run
    #     against the already-screened subset, it would silently see a
    #     PARTIAL trading history (screens 1-3 remove some of a member's
    #     transactions) and misclassify members whose true routine pattern
    #     included exactly the transactions those screens exclude.
    # Confirmed empirically before this task was built: the earlier draft
    # of this script classified only `screened`, leaving `unscreened`
    # without is_routine/committee_match columns at all --
    # build_model2_frame reads them via row.get(...) (not a strict
    # ValueError guard), so a missing column doesn't raise, it silently
    # defaults opportunistic to a CONSTANT 1 and committee_match to a
    # CONSTANT 0 for every row of the "full" Model 2 run -- the same class
    # of intercept-collinearity bug already found in Task 19
    # (chamber/party) and Task 23's robustness fixture design.
    unscreened = classify.committee_match(
        classify.is_routine_trader(result.sample.sort(CANONICAL_ORDER)), assignments, sic,
        historical_assignments=historical_assignments,
    )
    # Re-sorted after the screens too: screen3_liquidation sorts by
    # (bioguide_id, transaction_date), which is not a total order here, and
    # polars' sort does not maintain the relative order of ties by default.
    screened = screen3_liquidation(
        screen2_tax_management(screen1_rebalancing(unscreened), prices), terms
    ).filter(~(pl_or(EXCLUSION_FLAGS))).sort(CANONICAL_ORDER)
    if screened.is_empty():
        raise SystemExit("Every transaction was removed by Screens 1-3; nothing left to analyze.")
    print(f"Sample: {result.sample.height} unscreened -> {screened.height} screened transactions")

    unscreened_with_car = attach_car_bhar(unscreened, prices, factors, sic)
    screened_with_car = attach_car_bhar(screened, prices, factors, sic)

    t1 = tables.t1_funnel(result)
    t2 = tables.t2(screened, sic)
    t3 = tables.t3(screened)
    t4 = tables.t4_mean_car(screened_with_car)

    # One dict for every Model 2 consumer below. unscreened_with_car's
    # (ticker, report_date) pairs are a superset of screened_with_car's, since
    # `screened` is filtered from the same initial sample -- so this single
    # population covers full_frame, screened_frame, and run_robustness_suite.
    size_proxies = _populate_size_proxies(unscreened_with_car, prices)
    full_frame = model2.build_model2_frame(unscreened_with_car, size_proxies, terms, PRIMARY_CAR_COL)
    screened_frame = model2.build_model2_frame(screened_with_car, size_proxies, terms, PRIMARY_CAR_COL)
    full_result = model2.run_model2(full_frame)
    screened_result = model2.run_model2(screened_frame)
    t5 = tables.t5_model2(full_result, screened_result)

    screened_sales = [
        (r["ticker"], r["report_date"])
        for r in screened_with_car.filter(screened_with_car["transaction"] == "Sale").iter_rows(named=True)
    ]
    portfolio_returns = model3.calendar_time_portfolio_returns(screened_sales, prices)
    alpha_result = model3.calendar_time_alpha(portfolio_returns, factors)
    t6 = tables.t6_model3(alpha_result)

    # Section 9 robustness item 6: entry at filing (report) date rather than
    # transaction date -- the actionability question. attach_car_bhar's
    # event_date_col="report_date" variant and run_robustness_suite's
    # filing_date_variant parameter (Tasks 22/23) exist for exactly this
    # check; review finding: this call previously left filing_date_variant
    # at its default None, so the check silently never ran and T7 shipped
    # with 9 of 10 pre-specified robustness checks instead of all 10.
    filing_date_variant = attach_car_bhar(screened, prices, factors, sic, event_date_col="report_date")
    robustness_table = run_robustness_suite(
        screened_with_car, size_proxies, terms, car_col=PRIMARY_CAR_COL, filing_date_variant=filing_date_variant
    )
    # .sort("check") is a reproducibility requirement, not a formatting choice.
    # run_robustness_suite emits one row per size band by iterating
    # df["amount_range"].unique(), and polars does not pin the order of unique()
    # -- so the size_band_* rows land in a different position on every run.
    # Caught by diffing two independent runs over the identical warehouse: every
    # number matched, one row had moved. Section 11 asks for byte-for-byte
    # identical output, so the row order has to be pinned somewhere; here is the
    # only place in scope.
    t7 = tables.t7_robustness(robustness_table.sort("check"))

    # Section 8: the full 18-variant (3 horizons x 3 methods x 2 samples)
    # grid, each cell a Model 2 fit for beta_sale, feeding the
    # Benjamini-Hochberg correction. Written to its own CSV (not one of
    # T1-T8 -- outputs/__init__.py: "Nothing beyond this pre-specified list
    # goes in the paper") purely so the 18 individual p-values behind the
    # single reported threshold are independently auditable, matching this
    # script's other verification CSVs (nan_audit.csv etc.).
    bh_grid = multiple_comparisons.run_eighteen_variant_grid(unscreened_with_car, screened_with_car, size_proxies, terms)
    bh_grid.sort(["horizon", "method", "sample"]).write_csv(storage.paths().outputs / "bh_correction_grid.csv")
    bh_p_values = bh_grid.filter(pl.col("p_value").is_not_null())["p_value"].to_list()
    if len(bh_p_values) < bh_grid.height:
        print(f"  BH grid: {len(bh_p_values)}/{bh_grid.height} of the 18 pre-specified variants produced "
              "a usable p-value; the rest are reported as None rows in bh_correction_grid.csv (too few "
              "observations, or a degenerate fixed-effects structure, for that specific horizon/method/sample cell).")
    bh_threshold = multiple_comparisons.bh_corrected_threshold(bh_p_values) if bh_p_values else None

    # nan_audit walks sample_with_car.columns in order, so it needs no sort. The
    # other two both start from a polars unique()/group_by(), whose output order
    # is not pinned -- same reproducibility issue as T7 above, and it only shows
    # up once these audits have more than one row to report. Sorted here rather
    # than left to chance.
    nan_audit(screened_with_car).write_csv(storage.paths().outputs / "nan_audit.csv")
    delisting_audit(screened, prices).sort("ticker").write_csv(
        storage.paths().outputs / "delisting_audit.csv"
    )
    # ticker_reuse_audit returns `tickers` as a List(Utf8) -- the whole point of
    # the audit is "which tickers share one CIK", so the column is genuinely
    # nested. write_csv on it raises
    # `ComputeError: CSV format does not support nested data`, and it raises
    # precisely when the audit HAS something to report, i.e. exactly when the
    # ticker-reuse problem Section 11 asks about actually exists. Flattened to a
    # delimited string here, at the serialization boundary, rather than changing
    # the audit's own (correct, already-reviewed) return shape.
    ticker_reuse_audit(sic).with_columns(pl.col("tickers").list.sort().list.join(";")).sort(
        "cik"
    ).write_csv(storage.paths().outputs / "ticker_reuse_audit.csv")
    build_worksheet(select_worksheet_sample(screened_with_car)).write_csv(
        storage.paths().outputs / "hand_check_worksheet.csv"
    )

    figure_paths = _write_figures(
        result, screened, screened_with_car, prices, factors, portfolio_returns, size_proxies, terms
    )

    # bh_computed=True: the Section 8 18-variant grid above was genuinely
    # fit, so bh_threshold=None here (when it happens) means "computed, and
    # nothing survived correction" -- a real finding -- not "never
    # computed", which is bh_computed=False's meaning (see
    # build_paper_markdown's own docstring). Prior to this, this script
    # always passed bh_threshold=None with bh_computed=False, so no result
    # it produced could ever be certified as "supportive" under Section 12's
    # own rule ("only if it survives Benjamini-Hochberg correction").
    md = paper.build_paper_markdown(
        {"T1": t1, "T2": t2, "T3": t3, "T4": t4, "T5": t5, "T6": t6, "T7": t7},
        figure_paths,
        bh_threshold=bh_threshold,
        bh_computed=True,
    )
    (storage.paths().outputs / "paper.md").write_text(md)
    print(f"Wrote outputs to {storage.paths().outputs}")


if __name__ == "__main__":
    main()
