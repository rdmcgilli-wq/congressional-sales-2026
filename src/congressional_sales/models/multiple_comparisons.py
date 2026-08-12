"""Benjamini-Hochberg FDR correction, PRE_ANALYSIS_PLAN.md Section 8: the
study runs 3 horizons x 3 adjustment methods x 2 samples = 18 variants of
the main test, and this correction must be applied across all of them."""

from __future__ import annotations

import polars as pl


def bh_adjust(p_values: list[float]) -> list[float]:
    n = len(p_values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: p_values[i])
    adjusted_sorted = [0.0] * n
    running_min = 1.0
    for rank in range(n, 0, -1):
        idx = order[rank - 1]
        q = p_values[idx] * n / rank
        running_min = min(running_min, q)
        adjusted_sorted[rank - 1] = running_min
    result = [0.0] * n
    for rank in range(n):
        result[order[rank]] = adjusted_sorted[rank]
    return result


def bh_corrected_threshold(p_values: list[float], alpha: float = 0.05) -> float | None:
    n = len(p_values)
    if n == 0:
        return None
    sorted_p = sorted(p_values)
    threshold = None
    for k, p in enumerate(sorted_p, start=1):
        if p <= (k / n) * alpha:
            threshold = p
    return threshold


def eighteen_variant_grid(
    horizons: list[int] | None = None,
    methods: list[str] | None = None,
    samples: list[str] | None = None,
) -> list[tuple[int, str, str]]:
    horizons = horizons or [30, 90, 180]
    methods = methods or ["market_adjusted", "four_factor", "size_industry_matched"]
    samples = samples or ["unscreened", "screened"]
    return [(h, m, s) for h in horizons for m in methods for s in samples]


# eighteen_variant_grid's method labels ("market_adjusted", ...) match this
# study's write-up vocabulary (PRE_ANALYSIS_PLAN.md Section 6); CAR columns
# on a sample frame are named with events.attach's shorter prefixes
# ("car_market_90", not "car_market_adjusted_90") -- same mapping
# outputs/tables.py's METHOD_LABELS already carries in the other direction,
# duplicated here rather than imported to avoid models/ reaching into
# outputs/.
_METHOD_LABEL_TO_CAR_PREFIX = {
    "market_adjusted": "market", "four_factor": "four_factor", "size_industry_matched": "size_industry",
}


def run_eighteen_variant_grid(
    unscreened_with_car: pl.DataFrame,
    screened_with_car: pl.DataFrame,
    size_proxies: dict,
    terms: pl.DataFrame,
) -> pl.DataFrame:
    """Fits Model 2's primary test (the `sale` coefficient) across all 18
    pre-specified (horizon, method, sample) variants (Section 8), one row
    per cell, collecting each cell's p-value -- the input the
    Benjamini-Hochberg correction below needs and this module previously
    had no producer of.

    A cell whose sample is too thin, or whose fixed-effects structure
    degenerates on that particular CAR column's non-null subset, is
    reported as a None row rather than raising: the same defensive pattern
    robustness.py's `_run_primary` already uses, for the identical reason
    -- Section 8 requires reporting across all 18 variants, not silently
    dropping the ones that don't fit cleanly.
    """
    from linearmodels.panel.utility import AbsorbingEffectError

    from . import model2 as model2_mod

    frames = {"unscreened": unscreened_with_car, "screened": screened_with_car}
    rows = []
    for horizon, method_label, sample_name in eighteen_variant_grid():
        car_col = f"car_{_METHOD_LABEL_TO_CAR_PREFIX[method_label]}_{horizon}"
        df = frames[sample_name]
        row = {
            "horizon": horizon, "method": method_label, "sample": sample_name,
            "beta_sale": None, "se_sale": None, "p_value": None, "n": 0,
        }
        if car_col in df.columns:
            try:
                frame = model2_mod.build_model2_frame(df, size_proxies, terms, car_col)
                if frame.height >= 10 and frame["bioguide_id"].n_unique() >= 2:
                    result = model2_mod.run_model2(frame)
                    row["beta_sale"] = result["params"].get("sale")
                    row["se_sale"] = result["se"].get("sale")
                    row["p_value"] = result["pvalues"].get("sale")
                    row["n"] = result["n_obs"]
            except (ValueError, AbsorbingEffectError):
                pass
        rows.append(row)
    return pl.DataFrame(rows)
