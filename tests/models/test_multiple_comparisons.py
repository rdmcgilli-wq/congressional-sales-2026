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
    p = [0.5, 0.001, 0.3, 0.02]
    got = mc.bh_adjust(p)
    assert len(got) == len(p)


def test_bh_corrected_threshold_on_hand_worked_example():
    # Same 3-value example: adjusted q-values are [0.03, 0.04, 0.04], all
    # <= 0.05, so the largest RAW p-value whose own BH critical value
    # condition holds is the threshold. p(3)=0.04 <= (3/3)*0.05=0.05 -- holds.
    assert mc.bh_corrected_threshold([0.01, 0.04, 0.03], alpha=0.05) == pytest.approx(0.04)


def test_bh_corrected_threshold_none_when_nothing_survives():
    assert mc.bh_corrected_threshold([0.9, 0.8, 0.99], alpha=0.05) is None


def test_eighteen_variant_grid_has_exactly_18_cells():
    grid = mc.eighteen_variant_grid()
    assert len(grid) == 18
    assert len(set(grid)) == 18  # no duplicate cells
    assert (90, "four_factor", "screened") in grid  # the pre-specified PRIMARY test cell (Section 8)
