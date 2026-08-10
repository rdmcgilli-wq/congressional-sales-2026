"""F1-F8, PRE_ANALYSIS_PLAN.md Section 10. Static publication figures via
matplotlib -- every function takes already-computed results and composes,
never recomputes."""

from __future__ import annotations

import matplotlib.pyplot as plt
import polars as pl

from ..sample.funnel import FunnelResult


def f1_sample_funnel(result: FunnelResult):
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = [s.name for s in result.steps]
    counts = [s.count_after for s in result.steps]
    ax.barh(labels, counts)
    ax.set_xlabel("Transactions remaining")
    ax.set_title("Sample Construction Funnel (F1)")
    fig.tight_layout()
    return fig


def f2_filing_lag_histogram(lags: pl.Series):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(lags.to_list(), bins=30)
    ax.axvline(45, color="red", linestyle="--", label="45-day STOCK Act threshold")
    ax.set_xlabel("Filing lag (days)")
    ax.set_ylabel("Count")
    ax.legend()
    ax.set_title("Filing Lag Distribution (F2)")
    fig.tight_layout()
    return fig


def _plot_event_series(ax, series: dict, label: str) -> None:
    offsets = sorted(k for k, v in series.items() if v is not None)
    values = [series[o] for o in offsets]
    ax.plot(offsets, values, label=label)


def f3_event_time_car(sale_series: dict, purchase_series: dict):
    fig, ax = plt.subplots(figsize=(9, 5))
    _plot_event_series(ax, sale_series, "Sales")
    _plot_event_series(ax, purchase_series, "Purchases")
    ax.axvline(0, color="gray", linestyle=":")
    ax.axhline(0, color="gray", linestyle=":")
    ax.set_xlabel("Trading sessions relative to transaction date")
    ax.set_ylabel("Cumulative market-adjusted abnormal return")
    ax.legend()
    ax.set_title("Event-Time CAR: Purchases vs. Sales (F3)")
    fig.tight_layout()
    return fig


def f4_event_time_car_by_routine(opportunistic_series: dict, routine_series: dict):
    fig, ax = plt.subplots(figsize=(9, 5))
    _plot_event_series(ax, opportunistic_series, "Opportunistic")
    _plot_event_series(ax, routine_series, "Routine")
    ax.axvline(0, color="gray", linestyle=":")
    ax.set_xlabel("Trading sessions relative to transaction date")
    ax.set_ylabel("Cumulative market-adjusted abnormal return")
    ax.legend()
    ax.set_title("Event-Time CAR: Opportunistic vs. Routine Sales (F4, H3)")
    fig.tight_layout()
    return fig


def f5_event_time_car_by_committee_match(matched_series: dict, unmatched_series: dict):
    fig, ax = plt.subplots(figsize=(9, 5))
    _plot_event_series(ax, matched_series, "Committee-matched sector")
    _plot_event_series(ax, unmatched_series, "Non-matched sector")
    ax.axvline(0, color="gray", linestyle=":")
    ax.set_xlabel("Trading sessions relative to transaction date")
    ax.set_ylabel("Cumulative market-adjusted abnormal return")
    ax.legend()
    ax.set_title("Event-Time CAR: Committee-Match vs. Non-Match (F5, H4)")
    fig.tight_layout()
    return fig


def f6_random_control_distribution(simulated: list, actual: float):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(simulated, bins=40)
    ax.axvline(actual, color="red", linestyle="--", label="Actual result")
    ax.set_xlabel("Simulated mean CAR")
    ax.legend()
    ax.set_title("Random Control Distribution (F6)")
    fig.tight_layout()
    return fig


def f7_year_by_year_effect(years: list, effects: list, ci_lower: list, ci_upper: list):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.errorbar(years, effects, yerr=[[e - lo for e, lo in zip(effects, ci_lower)], [hi - e for e, hi in zip(effects, ci_upper)]], fmt="o")
    ax.axhline(0, color="gray", linestyle=":")
    ax.set_xlabel("Year")
    ax.set_ylabel("Effect size (beta_sale)")
    ax.set_title("Year-by-Year Effect Size (F7)")
    fig.tight_layout()
    return fig


def f8_calendar_time_alpha(months: list, cumulative_alpha: list):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(months, cumulative_alpha)
    ax.axhline(0, color="gray", linestyle=":")
    ax.set_xlabel("Month")
    ax.set_ylabel("Cumulative calendar-time alpha")
    ax.set_title("Calendar-Time Portfolio Cumulative Alpha (F8)")
    fig.tight_layout()
    return fig
