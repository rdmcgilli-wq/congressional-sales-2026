from __future__ import annotations

import pytest

from congressional_sales.models import multiple_comparisons as mc


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
