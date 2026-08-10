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
    rows = []
    for txn_type in ("Sale", "Purchase"):
        subset = sample_with_car.filter(pl.col("transaction") == txn_type)
        if subset.is_empty():
            continue
        for h in HORIZONS:
            for m in METHODS:
                col = f"car_{m}_{h}"
                values = subset[col].drop_nulls()
                rows.append(
                    {
                        "transaction": txn_type, "horizon": h, "method": METHOD_LABELS[m],
                        "mean_car": float(values.mean()) if values.len() else None, "n": values.len(),
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
