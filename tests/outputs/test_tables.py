from __future__ import annotations

import polars as pl

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


def test_t4_mean_car_has_18_rows_per_transaction_type_pair():
    sample = pl.DataFrame(
        {
            "transaction": ["Sale", "Purchase"],
            "car_market_30": [-0.01, 0.02], "car_market_90": [-0.02, 0.03], "car_market_180": [-0.03, 0.04],
            "car_four_factor_30": [-0.01, 0.02], "car_four_factor_90": [-0.02, 0.03], "car_four_factor_180": [-0.03, 0.04],
            "car_size_industry_30": [-0.01, 0.02], "car_size_industry_90": [-0.02, 0.03], "car_size_industry_180": [-0.03, 0.04],
        }
    )
    t4 = tables.t4_mean_car(sample)
    assert t4.height == 18  # 2 transaction types x 3 horizons x 3 methods
    sale_90_four_factor = t4.filter(
        (pl.col("transaction") == "Sale") & (pl.col("horizon") == 90) & (pl.col("method") == "four_factor")
    )
    assert sale_90_four_factor["mean_car"][0] == -0.02


def test_t5_model2_combines_full_and_screened():
    full = {"params": {"sale": 0.01}, "se": {"sale": 0.005}}
    screened = {"params": {"sale": -0.02}, "se": {"sale": 0.008}}
    t5 = tables.t5_model2(full, screened)
    row = t5.filter(pl.col("param") == "sale")
    assert row["beta_full"][0] == 0.01
    assert row["beta_screened"][0] == -0.02
