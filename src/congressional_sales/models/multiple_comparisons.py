"""Benjamini-Hochberg FDR correction, PRE_ANALYSIS_PLAN.md Section 8: the
study runs 3 horizons x 3 adjustment methods x 2 samples = 18 variants of
the main test, and this correction must be applied across all of them."""

from __future__ import annotations


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
