from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from congressional_sales.models import model1


def test_clustered_mean_recovers_the_simple_average():
    values = [0.10, 0.20, 0.30, 0.40]
    clusters = ["A", "A", "B", "B"]
    got = model1.clustered_mean(values, clusters)
    assert got["mean"] == pytest.approx(0.25)
    assert got["n"] == 4
    assert got["se"] > 0


def test_clustered_mean_se_differs_by_clustering_choice():
    """Clustering by a variable correlated with the outcome (here: cluster
    B is uniformly higher-valued) should generally produce a different SE
    than clustering by an uncorrelated grouping -- this is a sanity check
    that cluster_ids actually flows into the statsmodels call, not a
    from-scratch re-derivation of cluster-robust variance."""
    values = [0.10, 0.12, 0.30, 0.32, 0.11, 0.31]
    by_pair = ["A", "A", "B", "B", "A", "B"]
    by_row = ["1", "2", "3", "4", "5", "6"]  # every row its own cluster
    se_pair = model1.clustered_mean(values, by_pair)["se"]
    se_row = model1.clustered_mean(values, by_row)["se"]
    assert se_pair != pytest.approx(se_row)


def test_unconditional_means_table_has_one_row_per_transaction_type():
    sample = pl.DataFrame(
        {
            "transaction": ["Sale", "Sale", "Purchase"],
            "bioguide_id": ["A1", "A2", "A1"],
            "report_date": [date(2020, 1, 15), date(2020, 2, 20), date(2020, 1, 10)],
            "car": [-0.05, -0.03, 0.04],
        }
    )
    t = model1.unconditional_means_table(sample, car_col="car")
    assert set(t["transaction"].to_list()) == {"Sale", "Purchase"}
    sale_row = t.filter(pl.col("transaction") == "Sale")
    assert sale_row["mean"][0] == pytest.approx(-0.04)
    assert sale_row["n"][0] == 2


def test_unconditional_means_table_drops_null_car_rows():
    sample = pl.DataFrame(
        {
            "transaction": ["Sale", "Sale"],
            "bioguide_id": ["A1", "A2"],
            "report_date": [date(2020, 1, 15), date(2020, 2, 20)],
            "car": [-0.05, None],
        }
    )
    t = model1.unconditional_means_table(sample, car_col="car")
    assert t.filter(pl.col("transaction") == "Sale")["n"][0] == 1


def test_clustered_mean_warns_when_fewer_than_two_clusters():
    """Regression: cluster-robust SE is undefined at n_clusters<2 (statsmodels'
    G/(G-1) finite-sample correction divides by zero). The degenerate branch
    must not fire silently -- a NaN sitting in a rendered T4/T5 table cell is
    ambiguous (formatting bug vs. genuinely underpowered subgroup) unless the
    pipeline surfaces a warning when it happens."""
    with pytest.warns(UserWarning, match="cluster-robust SE undefined"):
        got = model1.clustered_mean([0.05], ["A1"])
    assert got["mean"] == pytest.approx(0.05)
    assert got["se"] != got["se"]  # NaN
    assert got["t_stat"] != got["t_stat"]  # NaN
    assert got["n"] == 1
