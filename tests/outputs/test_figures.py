from __future__ import annotations

import matplotlib
import polars as pl

matplotlib.use("Agg")  # headless -- these tests never open a display

from congressional_sales.outputs import figures


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
