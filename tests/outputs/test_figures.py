from __future__ import annotations

import matplotlib
import polars as pl
import pytest

matplotlib.use("Agg")  # headless -- these tests never open a display

from congressional_sales.outputs import figures
from congressional_sales.sample.funnel import FunnelResult, FunnelStep


def test_f2_filing_lag_histogram_returns_a_figure_and_marks_45_days():
    lags = pl.Series([1, 5, 10, 30, 46, 60, 90])
    fig = figures.f2_filing_lag_histogram(lags)
    assert fig is not None
    ax = fig.axes[0]
    # A vertical line at x=45 must exist -- verified via axvline's stored data.
    assert any(abs(line.get_xdata()[0] - 45) < 1e-6 for line in ax.get_lines())


def test_f3_event_time_car_plot_returns_a_figure_with_two_series():
    sale_series = {-30: 0.0, 0: -0.01, 90: -0.03, 180: -0.05}
    purchase_series = {-30: 0.0, 0: 0.005, 90: 0.02, 180: 0.04}
    fig = figures.f3_event_time_car(sale_series, purchase_series)
    ax = fig.axes[0]
    assert len(ax.get_lines()) >= 2


def test_f6_random_control_distribution_marks_the_actual_result():
    simulated = [0.0, 0.001, -0.002, 0.003, -0.001] * 20  # 100 values
    fig = figures.f6_random_control_distribution(simulated, actual=0.05)
    ax = fig.axes[0]
    assert any(abs(line.get_xdata()[0] - 0.05) < 1e-9 for line in ax.get_lines())


def test_f1_sample_funnel_bar_widths_and_labels_match_the_funnel_steps_in_order():
    # Review coverage gap: F1 had no dedicated test. Bar width is
    # count_after (not count_before/excluded), and bar order/labels must
    # match result.steps order -- a swapped field or reordering would not
    # crash, only silently mislabel the figure.
    result = FunnelResult(
        steps=[FunnelStep("common_stock_only", 100, 90), FunnelStep("above_statutory_threshold", 90, 70), FunnelStep("dedupe_filings", 70, 50)],
        sample=pl.DataFrame(),
    )
    fig = figures.f1_sample_funnel(result)
    ax = fig.axes[0]
    assert [p.get_width() for p in ax.patches] == [90, 70, 50]
    assert [t.get_text() for t in ax.get_yticklabels()] == ["common_stock_only", "above_statutory_threshold", "dedupe_filings"]


def test_f7_year_by_year_effect_errorbar_whiskers_match_ci_bounds_exactly():
    # Review coverage gap: F7's asymmetric errorbar construction
    # ([[e - lo for e, lo in ...], [hi - e for ...]]) is exactly the kind
    # of arithmetic a "does it crash" check would miss if it had a sign
    # or off-by-one error -- verify the actual plotted whisker endpoints
    # equal ci_lower/ci_upper, not just that a Figure comes back.
    # Deliberately asymmetric CIs (distance from effect to ci_lower != distance
    # to ci_upper on every row) -- a symmetric fixture would make a lo/hi-swap
    # bug in the errorbar magnitude construction invisible, since swapping two
    # equal magnitudes produces the same plotted bounds.
    years = [2019, 2020, 2021]
    effects = [0.01, -0.02, 0.03]
    ci_lower = [0.002, -0.05, 0.005]
    ci_upper = [0.015, -0.01, 0.09]
    fig = figures.f7_year_by_year_effect(years, effects, ci_lower, ci_upper)
    ax = fig.axes[0]
    container = ax.containers[0]
    main_line = container.lines[0]
    assert list(main_line.get_xdata()) == years
    assert list(main_line.get_ydata()) == effects
    whisker_segments = container.lines[2][0].get_segments()
    assert len(whisker_segments) == len(years)
    for (x, y_lo), (_, y_hi) in whisker_segments:
        i = years.index(int(x))
        assert y_lo == pytest.approx(ci_lower[i])
        assert y_hi == pytest.approx(ci_upper[i])
