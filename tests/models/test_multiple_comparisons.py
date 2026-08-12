from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from congressional_sales.models import multiple_comparisons as mc


def _grid_fixture() -> tuple[pl.DataFrame, pl.DataFrame, dict, pl.DataFrame]:
    # Same panel-construction discipline as test_robustness.py's own
    # fixture: real within-member variation on every regressor, or
    # AbsorbingLS finds the whole design degenerate (single-observation
    # members, constant controls) rather than merely underpowered.
    rng = np.random.default_rng(11)
    members = [f"M{i}" for i in range(10)]
    industries = ["Business Equipment", "Energy", "Money", "Manufacturing"]
    bands = ["$1,001 - $15,000", "$15,001 - $50,000"]
    methods = ["market", "four_factor", "size_industry"]
    horizons = [30, 90, 180]

    def random_date(start_year, end_year):
        start = date(start_year, 1, 1)
        days = (date(end_year, 12, 31) - start).days
        return start + timedelta(days=int(rng.integers(0, days)))

    rows = []
    for i in range(80):
        m = members[int(rng.integers(0, len(members)))]
        row = {
            "ticker": f"T{i}", "bioguide_id": m,
            "transaction": "Sale" if int(rng.integers(0, 2)) else "Purchase",
            "report_date": random_date(2015, 2022),
            "is_routine": bool(rng.integers(0, 2)),
            "committee_match": bool(rng.integers(0, 2)),
            "amount_range": bands[int(rng.integers(0, len(bands)))],
            "chamber": "Senate" if m in ("M0", "M1", "M2") else "Representatives",
            "party": "R",
            "industry": industries[int(rng.integers(0, len(industries)))],
            "prior_12mo_return": 0.05 + float(rng.normal(0, 0.1)),
        }
        for method in methods:
            for h in horizons:
                row[f"car_{method}_{h}"] = float(rng.normal(0, 0.05))
        rows.append(row)
    unscreened = pl.DataFrame(rows)
    screened = unscreened.filter(pl.arange(0, pl.len()) % 2 == 0)  # an arbitrary proper subset

    terms_rows = []
    for m in members:
        for _ in range(int(rng.integers(1, 4))):
            terms_rows.append(
                {
                    "bioguide_id": m, "full_name": "x", "chamber": "rep",
                    "term_start": random_date(2005, 2020), "term_end": random_date(2021, 2023),
                    "state": "XX", "party": "R",
                }
            )
    terms = pl.DataFrame(
        terms_rows,
        schema={
            "bioguide_id": pl.Utf8, "full_name": pl.Utf8, "chamber": pl.Utf8,
            "term_start": pl.Date, "term_end": pl.Date, "state": pl.Utf8, "party": pl.Utf8,
        },
    )
    size_proxies = {(r["ticker"], r["report_date"]): float(rng.uniform(10_000, 1_000_000)) for r in rows}
    return unscreened, screened, size_proxies, terms


def test_bh_adjust_matches_hand_worked_three_value_example():
    """p=[0.01, 0.04, 0.03], n=3: sorted order statistics p(1)=0.01,
    p(2)=0.03, p(3)=0.04 give q(1)=0.03, q(2)=0.045, q(3)=0.04; the
    running-minimum-from-the-top monotone adjustment gives adj(3)=0.04,
    adj(2)=min(0.045,0.04)=0.04, adj(1)=min(0.03,0.04)=0.03. Mapped back
    to input order [0.01, 0.04, 0.03] -> [0.03, 0.04, 0.04]."""
    got = mc.bh_adjust([0.01, 0.04, 0.03])
    assert got == pytest.approx([0.03, 0.04, 0.04])


def test_bh_adjust_empty_input():
    assert mc.bh_adjust([]) == []


def test_bh_adjust_preserves_order_and_length():
    # Strengthened per review: the original version of this test only
    # checked len(got) == len(p), which would pass even if index mapping
    # were broken (e.g. results silently returned in sorted-p order
    # instead of input order). p is not pre-sorted, so a mismap would
    # produce visibly wrong values here.
    p = [0.5, 0.001, 0.3, 0.02]
    got = mc.bh_adjust(p)
    assert len(got) == len(p)
    assert got == pytest.approx([0.5, 0.004, 0.4, 0.04])


def test_bh_adjust_monotonizes_ties_and_a_non_monotonic_raw_q_sequence():
    # Adversarial case (from task review): three tied p=0.02 values plus a
    # raw per-rank q = p*n/rank sequence that is NON-monotonic before the
    # running-min correction is applied (rank6's raw q=0.1333 > rank7's raw
    # q=8*0.30/7=0.3429 is fine, but rank5's raw q=0.08 < rank6's raw
    # q=0.1333 forces a real monotonization step). Verified independently
    # against statsmodels.stats.multitest.multipletests(method="fdr_bh").
    p = [0.02, 0.02, 0.02, 0.05, 0.05, 0.10, 0.30, 0.30]
    got = mc.bh_adjust(p)
    n = len(p)
    expected = [8 * 0.02 / 3, 8 * 0.02 / 3, 8 * 0.02 / 3, 0.08, 0.08, 8 * 0.10 / 6, 0.30, 0.30]
    assert got == pytest.approx(expected)
    # Adjusted q-values must be non-decreasing in sorted-p order -- the
    # defining monotonicity property BH's running-min pass exists to
    # enforce.
    by_p = sorted(zip(p, got))
    assert [q for _, q in by_p] == sorted(q for _, q in by_p)
    assert n == 8


def test_bh_corrected_threshold_on_hand_worked_example():
    # Same 3-value example: adjusted q-values are [0.03, 0.04, 0.04], all
    # <= 0.05, so the largest RAW p-value whose own BH critical value
    # condition holds is the threshold. p(3)=0.04 <= (3/3)*0.05=0.05 -- holds.
    assert mc.bh_corrected_threshold([0.01, 0.04, 0.03], alpha=0.05) == pytest.approx(0.04)


def test_bh_corrected_threshold_none_when_nothing_survives():
    assert mc.bh_corrected_threshold([0.9, 0.8, 0.99], alpha=0.05) is None


def test_bh_corrected_threshold_survives_a_gap_in_the_critical_value_condition():
    # Adversarial "gap" case (from task review): sorted p = [0.005, 0.025,
    # 0.03, 0.05, 0.06], n=5, alpha=0.05. k=1 holds (0.005<=0.01), k=2
    # FAILS (0.025>0.02), k=3 holds again (0.03<=0.03), k=4/k=5 fail. The
    # correct BH threshold is the largest k whose own condition holds --
    # 0.03 at k=3 -- not the first-failing or first-passing k. This would
    # catch a break-on-first-failure bug that the brief's own tests (only
    # a strictly-ascending-success case and an all-fail case) could not.
    assert mc.bh_corrected_threshold([0.06, 0.005, 0.05, 0.025, 0.03], alpha=0.05) == pytest.approx(0.03)


def test_eighteen_variant_grid_has_exactly_18_cells():
    grid = mc.eighteen_variant_grid()
    assert len(grid) == 18
    assert len(set(grid)) == 18  # no duplicate cells
    assert (90, "four_factor", "screened") in grid  # the pre-specified PRIMARY test cell (Section 8)


def test_eighteen_variant_grid_matches_full_pre_registered_cell_list():
    # Full-contents check per review: the count/uniqueness/membership test
    # above would not catch a typo'd horizon or a swapped "screened"/
    # "unscreened" label as long as the grid still produced 18 unique
    # tuples. This asserts the exact literal cell set against
    # PRE_ANALYSIS_PLAN.md Section 8/Section 6's wording, which is this
    # function's entire reason for existing.
    expected = {
        (h, m, s)
        for h in (30, 90, 180)
        for m in ("market_adjusted", "four_factor", "size_industry_matched")
        for s in ("unscreened", "screened")
    }
    assert set(mc.eighteen_variant_grid()) == expected


def test_run_eighteen_variant_grid_produces_18_rows_with_valid_pvalues():
    unscreened, screened, size_proxies, terms = _grid_fixture()
    grid = mc.run_eighteen_variant_grid(unscreened, screened, size_proxies, terms)
    assert grid.height == 18
    assert set(zip(grid["horizon"], grid["method"], grid["sample"])) == set(mc.eighteen_variant_grid())
    # Every cell here is well-powered by construction (10 members, 80/40 rows) --
    # confirm the grid actually fit real regressions, not 18 None rows.
    non_null = grid.filter(pl.col("p_value").is_not_null())
    assert non_null.height == 18
    for p in non_null["p_value"].to_list():
        assert 0.0 <= p <= 1.0


def test_run_eighteen_variant_grid_feeds_bh_adjust_end_to_end():
    # The point of this grid: its p_value column must be usable as direct
    # input to bh_adjust/bh_corrected_threshold with no further massaging.
    unscreened, screened, size_proxies, terms = _grid_fixture()
    grid = mc.run_eighteen_variant_grid(unscreened, screened, size_proxies, terms)
    p_values = grid["p_value"].to_list()
    assert all(p is not None for p in p_values)
    adjusted = mc.bh_adjust(p_values)
    assert len(adjusted) == 18
    threshold = mc.bh_corrected_threshold(p_values)
    assert threshold is None or 0.0 <= threshold <= 1.0


def test_run_eighteen_variant_grid_reports_none_row_for_a_missing_car_column():
    # A caller whose sample lacks a given method's CAR columns entirely
    # (e.g. attach_car_bhar was never run for that method) must get an
    # explicit None row for every cell needing that column, not a KeyError.
    unscreened, screened, size_proxies, terms = _grid_fixture()
    missing_col_frame = unscreened.drop([c for c in unscreened.columns if c.startswith("car_size_industry")])
    grid = mc.run_eighteen_variant_grid(missing_col_frame, screened, size_proxies, terms)
    size_industry_unscreened = grid.filter(
        (pl.col("method") == "size_industry_matched") & (pl.col("sample") == "unscreened")
    )
    assert size_industry_unscreened.height == 3  # one per horizon
    assert all(v is None for v in size_industry_unscreened["p_value"].to_list())
