"""Model 1 (Section 7): unconditional mean CAR with cluster-robust SEs,
computed both ways Section 7 requires -- clustered on member and,
separately, on calendar month."""

from __future__ import annotations

import warnings

import numpy as np
import polars as pl
import statsmodels.api as sm


def clustered_mean(values: list[float], cluster_ids: list) -> dict:
    y = np.array(values, dtype=float)
    n = len(y)
    X = np.ones((n, 1))
    n_clusters = len(set(cluster_ids))
    if n_clusters < 2:
        # Cluster-robust variance is undefined with fewer than 2 clusters: the
        # standard estimator's finite-sample correction is G / (G - 1), which
        # divides by zero at G=1 (statsmodels raises ZeroDivisionError for
        # n>1-all-one-cluster, or a ValueError from an array-squeeze edge case
        # when n==1). Report the true arithmetic mean but flag se/t_stat as
        # undefined rather than crashing or reporting a misleadingly-precise
        # se of 0.0 (which would read as "infinitely significant").
        mean = float(np.mean(y)) if n > 0 else float("nan")
        warnings.warn(
            f"cluster-robust SE undefined: {n_clusters} cluster(s) for n={n} observations "
            "-- se/t_stat reported as NaN, not 0.0",
            stacklevel=2,
        )
        return {"mean": mean, "se": float("nan"), "t_stat": float("nan"), "n": n}
    fit = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": np.array(cluster_ids)})
    return {"mean": float(fit.params[0]), "se": float(fit.bse[0]), "t_stat": float(fit.tvalues[0]), "n": n}


def unconditional_means_table(sample: pl.DataFrame, car_col: str) -> pl.DataFrame:
    rows = []
    for txn_type in ("Sale", "Purchase"):
        subset = sample.filter(pl.col("transaction") == txn_type).drop_nulls(car_col)
        if subset.is_empty():
            continue
        values = subset[car_col].to_list()
        by_member = clustered_mean(values, subset["bioguide_id"].to_list())
        month_ids = subset["report_date"].dt.truncate("1mo").cast(pl.Utf8).to_list()
        by_month = clustered_mean(values, month_ids)
        rows.append(
            {
                "transaction": txn_type, "mean": by_member["mean"],
                "se_member": by_member["se"], "se_month": by_month["se"], "n": by_member["n"],
            }
        )
    return pl.DataFrame(rows)
