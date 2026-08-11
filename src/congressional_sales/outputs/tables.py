"""T1-T8, PRE_ANALYSIS_PLAN.md Section 10."""

from __future__ import annotations

import polars as pl

from ..sample.funnel import FunnelResult

HORIZONS = (30, 90, 180)
METHODS = ("market", "four_factor", "size_industry")
METHOD_LABELS = {"market": "market_adjusted", "four_factor": "four_factor", "size_industry": "size_industry_matched"}


def t1_funnel(result: FunnelResult) -> pl.DataFrame:
    return pl.DataFrame(
        [{"step": s.name, "count_before": s.count_before, "count_after": s.count_after, "excluded": s.count_before - s.count_after} for s in result.steps]
    )


def t2(sample: pl.DataFrame, sic: pl.DataFrame):
    from ..sample.descriptive import build_t2

    return build_t2(sample, sic)


def t3(sample: pl.DataFrame) -> pl.DataFrame:
    from ..sample.descriptive import build_t3

    return pl.DataFrame([build_t3(sample)])


def t4_mean_car(sample_with_car: pl.DataFrame) -> pl.DataFrame:
    """Whole-branch review finding: T4 is Model 1's own output shape
    ("Mean CAR by transaction type and horizon, all three adjustment
    methods", Section 10) and Section 7 requires it be reported WITH
    member- and month-clustered standard errors -- "Report both." The
    original implementation computed a bare mean/n with no inference at
    all, so nothing in this pipeline's output could support or refute
    H1/H2 (whether mean CAR differs from zero, or Sale differs from
    Purchase). Routed through models.model1.unconditional_means_table,
    which already computes exactly this (Task 18, already reviewed and
    tested) -- called once per (horizon, method) car column rather than
    inventing new statistics."""
    from ..models import model1

    rows = []
    for h in HORIZONS:
        for m in METHODS:
            car_col = f"car_{m}_{h}"
            means = model1.unconditional_means_table(sample_with_car, car_col=car_col)
            for row in means.iter_rows(named=True):
                rows.append(
                    {
                        "transaction": row["transaction"], "horizon": h, "method": METHOD_LABELS[m],
                        "mean_car": row["mean"], "se_member": row["se_member"], "se_month": row["se_month"],
                        "n": row["n"],
                    }
                )
    return pl.DataFrame(rows)


def t5_model2(full_result: dict, screened_result: dict) -> pl.DataFrame:
    params = sorted(set(full_result["params"]) | set(screened_result["params"]))
    return pl.DataFrame(
        [
            {
                "param": p,
                "beta_full": full_result["params"].get(p), "se_full": full_result["se"].get(p),
                "beta_screened": screened_result["params"].get(p), "se_screened": screened_result["se"].get(p),
            }
            for p in params
        ]
    )


def t6_model3(alpha_result: dict) -> pl.DataFrame:
    return pl.DataFrame([alpha_result])


def t7_robustness(robustness_table: pl.DataFrame) -> pl.DataFrame:
    return robustness_table


def t8_holdout(holdout_result: dict) -> pl.DataFrame:
    return pl.DataFrame([holdout_result])
