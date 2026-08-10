from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from congressional_sales import robustness


def test_winsorize_clips_extreme_values_to_the_percentile_bounds():
    values = pl.Series([1.0, 2.0, 3.0, 4.0, 100.0, -100.0])
    got = robustness.winsorize(values, lower=0.10, upper=0.90)
    assert got.max() < 100.0
    assert got.min() > -100.0
    assert got.len() == 6  # winsorizing clips, never drops rows


def _robustness_fixture():
    # A 30-distinct-member, 1-transaction-each fixture (the original draft
    # of this test) is UNFIT for a fixed-effects regression: with exactly
    # one observation per bioguide_id, MemberFE has zero within-member
    # degrees of freedom and perfectly absorbs every regressor --
    # AbsorbingLS raises AbsorbingEffectError on literally any exog column,
    # confirmed empirically before this task was built. A single
    # deterministic control value shared by every row (is_routine=False
    # for all -> opportunistic constant 1; an empty terms frame ->
    # seniority_terms constant 0; one size_proxies value for every ticker
    # -> log_size constant) is independently fatal too: a column that
    # never varies is perfectly collinear with the regression's own
    # intercept, with or without any fixed effect involved. This fixture
    # instead builds a genuinely varied panel -- multiple transactions per
    # member, randomized is_routine/committee_match/size/prior-return/
    # report_date, and a terms table with real term_start variation -- so
    # the primary regression the robustness suite reruns can actually be
    # estimated, mirroring the panel-construction lessons already applied
    # in tests/models/test_model2.py's own fixtures.
    rng = np.random.default_rng(7)
    members = [f"M{i}" for i in range(10)]
    industries = ["Business Equipment", "Energy", "Money", "Manufacturing"]
    bands = ["$1,001 - $15,000", "$15,001 - $50,000", "$50,001 - $100,000"]

    def random_date(start_year, end_year):
        start = date(start_year, 1, 1)
        days = (date(end_year, 12, 31) - start).days
        return start + timedelta(days=int(rng.integers(0, days)))

    rows = []
    for i in range(80):
        m = members[int(rng.integers(0, len(members)))]
        rows.append(
            {
                "ticker": f"T{i}", "bioguide_id": m,
                "transaction": "Sale" if int(rng.integers(0, 2)) else "Purchase",
                "report_date": random_date(2015, 2022),
                "car_four_factor_90": float(rng.normal(0, 0.05)),
                "is_routine": bool(rng.integers(0, 2)),
                "committee_match": bool(rng.integers(0, 2)),
                "amount_range": bands[int(rng.integers(0, len(bands)))],
                "chamber": "Senate" if m in ("M0", "M1", "M2") else "Representatives",
                "party": "R",
                "industry": industries[int(rng.integers(0, len(industries)))],
                "prior_12mo_return": 0.05 + float(rng.normal(0, 0.1)),
            }
        )
    sample = pl.DataFrame(rows)

    # prior_12mo_return/industry must be real columns: Task 19's
    # build_model2_frame raises ValueError if either is missing from its
    # input frame entirely (added in Task 19's fix, after this fixture was
    # originally drafted -- patched in before Task 23 was built, mirroring
    # the join-order pre-emptive fixes applied to Tasks 12/13). Every
    # robustness check below runs its filtered subset through
    # build_model2_frame, so both must be present from the start.
    terms_rows = []
    for m in members:
        for _ in range(int(rng.integers(0, 4))):
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
    return sample, terms, size_proxies


def test_run_robustness_suite_produces_one_row_per_check_and_the_full_sample():
    sample, terms, size_proxies = _robustness_fixture()
    result = robustness.run_robustness_suite(sample, size_proxies, terms)
    labels = set(result["check"].to_list())
    assert "full_screened_sample" in labels
    assert "excl_top5_traders" in labels
    assert "senate_only" in labels
    assert "house_only" in labels
    assert "winsorized_1_99" in labels
    # full_screened_sample has real within-member variation across every
    # regressor and 10 members -- the primary regression must actually
    # succeed here, not silently fall through to a None row (which would
    # make this test pass even if run_model2 never ran at all).
    full_row = result.filter(pl.col("check") == "full_screened_sample")
    assert full_row["beta_sale"][0] is not None
    assert full_row["n"][0] == 80
