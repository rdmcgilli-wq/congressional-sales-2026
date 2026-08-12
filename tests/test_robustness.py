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


def test_run_robustness_suite_omits_filing_date_entry_when_no_variant_is_passed():
    sample, terms, size_proxies = _robustness_fixture()
    result = robustness.run_robustness_suite(sample, size_proxies, terms)
    assert "filing_date_entry" not in result["check"].to_list()


def test_run_robustness_suite_includes_filing_date_entry_when_a_variant_is_passed():
    # Section 9 robustness item 6: entry at filing (report) date rather
    # than transaction date. Whole-branch review finding: this check was
    # wired into scripts/run_full_pipeline.py but had zero test coverage
    # anywhere in this suite. Confirm the row appears when a variant is
    # supplied, and confirm it's genuinely computed from the VARIANT's
    # own car_four_factor_90 column -- not silently reusing
    # full_screened_sample's number -- by giving the variant deliberately
    # different CAR values and asserting the resulting beta differs.
    # A constant shift to every row's CAR would NOT move beta_sale (OLS/FE
    # coefficients on other regressors are invariant to a constant additive
    # shift in the dependent variable -- only the intercept moves), so the
    # perturbation is applied only to Sale rows specifically, to actually
    # move the treatment-group estimate.
    sample, terms, size_proxies = _robustness_fixture()
    filing_date_variant = sample.with_columns(
        pl.when(pl.col("transaction") == "Sale")
        .then(pl.col("car_four_factor_90") + 5.0)
        .otherwise(pl.col("car_four_factor_90"))
        .alias("car_four_factor_90")
    )

    result = robustness.run_robustness_suite(sample, size_proxies, terms, filing_date_variant=filing_date_variant)
    labels = set(result["check"].to_list())
    assert "filing_date_entry" in labels

    filing_row = result.filter(pl.col("check") == "filing_date_entry")
    full_row = result.filter(pl.col("check") == "full_screened_sample")
    assert filing_row["beta_sale"][0] is not None
    assert filing_row["n"][0] == 80
    assert filing_row["beta_sale"][0] != pytest.approx(full_row["beta_sale"][0])


def test_year_by_year_effects_has_one_row_per_calendar_year_present():
    sample, terms, size_proxies = _robustness_fixture()
    result = robustness.year_by_year_effects(sample, size_proxies, terms, car_col="car_four_factor_90")
    expected_years = sorted(sample["report_date"].dt.year().unique().to_list())
    assert result["year"].to_list() == expected_years


def test_year_by_year_effects_fits_a_well_populated_year_with_a_real_ci():
    # Concentrate every row into a single, well-populated year so this test
    # doesn't depend on the fixture's random per-year row counts clearing
    # the >=10-row floor by chance. Spread across DISTINCT dates within
    # that one year, not one shared date -- report_date also drives
    # build_model2_frame's seniority_terms lookup, and collapsing every
    # row of a member's own transactions onto one identical date makes
    # seniority_terms member-constant, perfectly collinear with the
    # already-absorbed MemberFE (a real, if incidental, AbsorbingEffectError
    # this test tripped over before this comment was written).
    sample, terms, size_proxies = _robustness_fixture()
    n = sample.height
    new_dates = [date(2019, 1, 1) + timedelta(days=i % 300) for i in range(n)]
    old_report_dates = sample["report_date"].to_list()
    tickers = sample["ticker"].to_list()
    sample = sample.with_columns(pl.Series("report_date", new_dates))
    # size_proxies is keyed on (ticker, report_date) from the ORIGINAL random
    # dates -- rekey it to each row's new date or build_model2_frame's
    # log_size lookup misses on every row and silently drops the whole frame.
    old_to_new = dict(zip(zip(tickers, old_report_dates), new_dates))
    size_proxies = {
        (ticker, old_to_new[(ticker, old_date)]): v
        for (ticker, old_date), v in size_proxies.items()
        if (ticker, old_date) in old_to_new
    }
    result = robustness.year_by_year_effects(sample, size_proxies, terms, car_col="car_four_factor_90")
    assert result.height == 1
    row = result.row(0, named=True)
    assert row["year"] == 2019
    assert row["beta_sale"] is not None
    assert row["ci_lower"] < row["beta_sale"] < row["ci_upper"]
    assert row["ci_lower"] == pytest.approx(row["beta_sale"] - 1.96 * row["se_sale"])
    assert row["n"] == 80


def test_year_by_year_effects_reports_none_row_for_a_too_thin_year():
    sample, terms, size_proxies = _robustness_fixture()
    thin_year = sample.head(3).with_columns(pl.date(2099, 1, 1).alias("report_date"))
    result = robustness.year_by_year_effects(thin_year, size_proxies, terms, car_col="car_four_factor_90")
    assert result.height == 1
    row = result.row(0, named=True)
    assert row["year"] == 2099
    assert row["beta_sale"] is None
    assert row["n"] == 3
