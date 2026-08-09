"""Random control permutation test, PRE_ANALYSIS_PLAN.md Section 8: for
each result, resample the same tickers on random dates within the sample
period, 1,000 times, and report where the actual result falls in that
null distribution. "The single most persuasive robustness check
available" per the plan -- treated here as a generic tool over any CAR/
BHAR compute_fn so it applies uniformly to every Table T4/T5 cell.
"""

from __future__ import annotations

import random
import statistics
from collections.abc import Callable
from datetime import date


def random_control_test(
    transactions: list[tuple[str, date]],
    compute_fn: Callable[[str, date], float | None],
    period_start: date,
    period_end: date,
    sessions: list[date],
    n_iterations: int = 1000,
    seed: int | None = None,
) -> dict:
    real_values = [v for t, d in transactions if (v := compute_fn(t, d)) is not None]
    actual_mean = statistics.mean(real_values) if real_values else float("nan")

    candidate_sessions = [d for d in sessions if period_start <= d <= period_end]
    rng = random.Random(seed)
    simulated_means: list[float] = []
    for _ in range(n_iterations):
        sim_values = []
        for ticker, _ in transactions:
            random_date = rng.choice(candidate_sessions)
            v = compute_fn(ticker, random_date)
            if v is not None:
                sim_values.append(v)
        if sim_values:
            simulated_means.append(statistics.mean(sim_values))

    if simulated_means:
        percentile = sum(1 for s in simulated_means if s <= actual_mean) / len(simulated_means)
    else:
        percentile = float("nan")

    return {
        "actual_mean": actual_mean,
        "simulated_means": simulated_means,
        "percentile": percentile,
        # Number of iterations that actually produced a usable simulated
        # mean -- NOT the requested `n_iterations`. An iteration where
        # compute_fn returns None for every transaction contributes
        # nothing to simulated_means and must not count here, since this
        # value is reported downstream (T4/T5 tables) as "N random-
        # control iterations" and must reflect what actually happened.
        "n_iterations_used": len(simulated_means),
    }
