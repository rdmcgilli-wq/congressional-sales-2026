from __future__ import annotations

import polars as pl

from congressional_sales.outputs import paper


def test_build_paper_markdown_includes_every_table_and_figure_and_the_limitations_section():
    tables = {"T1": pl.DataFrame({"step": ["a"], "count_after": [10]}), "T4": pl.DataFrame({"mean_car": [-0.01]})}
    figures = {"F1": "figures/f1.png", "F2": "figures/f2.png"}
    md = paper.build_paper_markdown(tables, figures, bh_threshold=0.012)
    assert "## Table T1" in md
    assert "## Table T4" in md
    assert "figures/f1.png" in md
    assert "figures/f2.png" in md
    assert "## Limitations" in md
    assert "No causal claim" in md
    assert "No investment recommendation" in md
    assert "survivorship-biased" in md.lower()
    assert "0.012" in md  # the reported BH-corrected threshold


def test_build_paper_markdown_handles_missing_bh_threshold():
    md = paper.build_paper_markdown({}, {}, bh_threshold=None)
    assert "no result survived" in md.lower()


def test_build_paper_markdown_distinguishes_not_computed_from_zero_survived():
    # Whole-branch review finding: bh_threshold=None is ambiguous between
    # "the correction was run and nothing survived" (a real finding) and
    # "the correction was never run at all" -- the old unconditional "no
    # result survived correction" wording rendered a false claim for the
    # second case. bh_computed=False must say something different, and
    # must NOT claim anything survived or failed to survive.
    md = paper.build_paper_markdown({}, {}, bh_threshold=None, bh_computed=False)
    assert "not yet computed" in md.lower()
    assert "no result survived" not in md.lower()
