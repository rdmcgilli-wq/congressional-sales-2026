from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from congressional_sales.outputs import tables
from congressional_sales.sample.funnel import FunnelResult, FunnelStep


def test_t1_funnel_reports_step_before_after_and_excluded_count():
    result = FunnelResult(
        steps=[FunnelStep("common_stock_only", 100, 90), FunnelStep("above_statutory_threshold", 90, 88)],
        sample=pl.DataFrame(),
    )
    t1 = tables.t1_funnel(result)
    assert t1.height == 2
    row = t1.filter(pl.col("step") == "common_stock_only")
    assert row["count_before"][0] == 100
    assert row["count_after"][0] == 90
    assert row["excluded"][0] == 10


def _t4_fixture() -> pl.DataFrame:
    # 4 Sale rows and 4 Purchase rows, across 2 distinct members and 2+
    # distinct report-date months each, so model1.unconditional_means_table's
    # member- and month-clustering is genuinely non-degenerate (n_clusters
    # >= 2 both ways) rather than hitting its own <2-cluster NaN guard.
    # Symmetric per-row jitter (-0.003, -0.001, +0.001, +0.003; sums to 0)
    # around each horizon's target mean keeps mean_car exactly equal to the
    # single-value fixture's original numbers while giving se_member/se_month
    # real, non-zero values to assert on.
    def _jittered(base: float) -> list[float]:
        return [base - 0.003, base - 0.001, base + 0.001, base + 0.003]

    rows = []
    members = ["M1", "M1", "M2", "M2"]
    dates = [date(2020, 1, 15), date(2020, 2, 15), date(2020, 1, 20), date(2020, 3, 15)]
    for txn_type, base30, base90, base180 in (("Sale", -0.01, -0.02, -0.03), ("Purchase", 0.02, 0.03, 0.04)):
        car30, car90, car180 = _jittered(base30), _jittered(base90), _jittered(base180)
        for i in range(4):
            rows.append(
                {
                    "transaction": txn_type, "bioguide_id": members[i], "report_date": dates[i],
                    "car_market_30": car30[i], "car_market_90": car90[i], "car_market_180": car180[i],
                    "car_four_factor_30": car30[i], "car_four_factor_90": car90[i], "car_four_factor_180": car180[i],
                    "car_size_industry_30": car30[i], "car_size_industry_90": car90[i], "car_size_industry_180": car180[i],
                }
            )
    return pl.DataFrame(rows)


def test_t4_mean_car_has_18_rows_per_transaction_type_pair():
    t4 = tables.t4_mean_car(_t4_fixture())
    assert t4.height == 18  # 2 transaction types x 3 horizons x 3 methods
    sale_90_four_factor = t4.filter(
        (pl.col("transaction") == "Sale") & (pl.col("horizon") == 90) & (pl.col("method") == "four_factor")
    )
    assert sale_90_four_factor["mean_car"][0] == pytest.approx(-0.02)


def test_t4_mean_car_reports_member_and_month_clustered_standard_errors():
    # Whole-branch review finding: T4 previously carried no inference at
    # all (bare mean/n), so nothing in the pipeline's outputs could
    # support or refute H1/H2. Section 7 requires both member- and
    # month-clustered SEs, "report both" -- confirm both are now real,
    # finite, non-negative numbers (not None, not NaN) for a properly
    # non-degenerate fixture (>=2 members, >=2 months).
    t4 = tables.t4_mean_car(_t4_fixture())
    sale_90_four_factor = t4.filter(
        (pl.col("transaction") == "Sale") & (pl.col("horizon") == 90) & (pl.col("method") == "four_factor")
    )
    se_member = sale_90_four_factor["se_member"][0]
    se_month = sale_90_four_factor["se_month"][0]
    assert se_member is not None and se_member == se_member and se_member >= 0  # == self rules out NaN
    assert se_month is not None and se_month == se_month and se_month >= 0


def test_t5_model2_combines_full_and_screened():
    full = {"params": {"sale": 0.01}, "se": {"sale": 0.005}}
    screened = {"params": {"sale": -0.02}, "se": {"sale": 0.008}}
    t5 = tables.t5_model2(full, screened)
    row = t5.filter(pl.col("param") == "sale")
    assert row["beta_full"][0] == 0.01
    assert row["beta_screened"][0] == -0.02


def test_t8_holdout_has_one_row_per_param_with_beta_and_se():
    holdout_result = {
        "params": {"sale": -0.015, "opportunistic": 0.004},
        "se": {"sale": 0.006, "opportunistic": 0.003},
        "n_obs": 214,
        "n_absorbed_member": 42,
        "n_absorbed_year": 2,
        "n_absorbed_industry": 8,
    }
    t8 = tables.t8_holdout(holdout_result)
    assert t8.height == 2
    sale_row = t8.filter(pl.col("param") == "sale")
    assert sale_row["beta"][0] == pytest.approx(-0.015)
    assert sale_row["se"][0] == pytest.approx(0.006)
    assert sale_row["n_obs"][0] == 214
    assert sale_row["n_absorbed_member"][0] == 42


def test_t8_holdout_handles_a_param_with_no_matching_se():
    # run_model2's params/se dicts are built independently (one per fitted
    # coefficient), so a param present in one but missing from the other is
    # not something this table should crash on -- se should come through as
    # null rather than raising a KeyError.
    holdout_result = {
        "params": {"sale": -0.015},
        "se": {},
        "n_obs": 10,
        "n_absorbed_member": 5,
        "n_absorbed_year": 1,
        "n_absorbed_industry": 1,
    }
    t8 = tables.t8_holdout(holdout_result)
    assert t8["se"][0] is None
