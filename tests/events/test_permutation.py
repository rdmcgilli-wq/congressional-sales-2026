from __future__ import annotations

from datetime import date, timedelta

import pytest

from congressional_sales.events import permutation


def test_random_control_test_actual_mean_matches_direct_computation():
    def compute_fn(ticker, d):
        return 1.0 if ticker == "AAPL" else 2.0

    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(300)]
    result = permutation.random_control_test(
        transactions=[("AAPL", sessions[10]), ("MSFT", sessions[20])],
        compute_fn=compute_fn, period_start=sessions[0], period_end=sessions[-1],
        sessions=sessions, n_iterations=5, seed=42,
    )
    assert result["actual_mean"] == pytest.approx(1.5)


def test_random_control_test_reports_1000_iterations_by_default():
    def compute_fn(ticker, d):
        return 1.0

    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(300)]
    result = permutation.random_control_test(
        transactions=[("AAPL", sessions[10])], compute_fn=compute_fn,
        period_start=sessions[0], period_end=sessions[-1], sessions=sessions, seed=1,
    )
    assert result["n_iterations_used"] == 1000
    assert len(result["simulated_means"]) == 1000


def test_random_control_test_is_reproducible_with_the_same_seed():
    def compute_fn(ticker, d):
        return d.toordinal() % 7  # value depends on the (randomized) date -> exercises real resampling

    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(300)]
    kwargs = dict(
        transactions=[("AAPL", sessions[10]), ("AAPL", sessions[50])], compute_fn=compute_fn,
        period_start=sessions[0], period_end=sessions[-1], sessions=sessions, n_iterations=50,
    )
    r1 = permutation.random_control_test(**kwargs, seed=7)
    r2 = permutation.random_control_test(**kwargs, seed=7)
    assert r1["simulated_means"] == r2["simulated_means"]


def test_random_control_test_percentile_is_between_zero_and_one():
    def compute_fn(ticker, d):
        return float(d.toordinal() % 11)

    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(300)]
    result = permutation.random_control_test(
        transactions=[("AAPL", sessions[100])], compute_fn=compute_fn,
        period_start=sessions[0], period_end=sessions[-1], sessions=sessions, n_iterations=100, seed=3,
    )
    assert 0.0 <= result["percentile"] <= 1.0
