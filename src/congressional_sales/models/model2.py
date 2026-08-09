"""Model 2 (Section 7): pooled fixed-effects regression.

    CAR_i = b0 + b1*Sale_i + b2*Opportunistic_i + b3*(Sale x Opportunistic)_i
            + b4*CommitteeMatch_i + b5*(Sale x CommitteeMatch)_i
            + gamma*Controls_i + MemberFE + YearFE + IndustryFE + e_i

This is the study's PRIMARY specification: b1 (the `sale` coefficient) at
the 90-day horizon, four-factor adjusted, screened sample, is the single
pre-registered primary test the whole study is built around.

Controls implemented: log_size (Task 16's dollar-volume proxy, in place of
log market cap -- no shares-outstanding source in this project),
prior_12mo_return, size_band, chamber, party, seniority_terms.

book-to-market is OMITTED -- no data source for it exists in this
project. This is a documented deviation from Section 7, not a silent
gap; state it in the paper's limitations section.

Fixed effects (member, year, industry) are absorbed via
`linearmodels.iv.absorbing.AbsorbingLS` rather than materialized as dummy
columns, since member alone can span hundreds of levels. Standard errors
are clustered at the member (bioguide_id) level.

Library-version note: `AbsorbingLS.fit()`'s keyword arguments for
cluster-robust covariance have varied across `linearmodels` releases.
Confirmed against the installed version (linearmodels==7.0) via
`help(AbsorbingLS.fit)`: `fit()` accepts `cov_type: str` as a named
parameter plus `**cov_config` for covariance-estimator-specific options.
`cov_type="clustered"` selects `linearmodels.iv.covariance.
ClusteredCovariance`, whose constructor takes a `clusters` argument --
confirmed via `help(ClusteredCovariance.__init__)`. So
`fit(cov_type="clustered", clusters=pdf["bioguide_id"])` is the correct
call for this installed version.
"""

from __future__ import annotations

import math

import pandas as pd
import polars as pl


def build_model2_frame(
    sample_with_car: pl.DataFrame,
    size_proxies: dict,
    terms: pl.DataFrame,
    car_col: str,
) -> pl.DataFrame:
    """Assemble the Model 2 regression frame from the CAR sample.

    `sale` = 1 iff `transaction == "Sale"`.
    `opportunistic` = 1 - is_routine (i.e. 1 iff the trade is NOT flagged routine).
    `seniority_terms` = count of prior terms for that `bioguide_id` in `terms`
    with `term_start < report_date`.
    """

    def _seniority(bioguide: str, report_date) -> int:
        prior = terms.filter(
            (pl.col("bioguide_id") == bioguide) & (pl.col("term_start") < report_date)
        )
        return prior.height

    rows = []
    for row in sample_with_car.iter_rows(named=True):
        size = size_proxies.get((row["ticker"], row["report_date"]))
        rows.append(
            {
                "car": row[car_col],
                "sale": 1 if row["transaction"] == "Sale" else 0,
                "opportunistic": 0 if row.get("is_routine") else 1,
                "committee_match": 1 if row.get("committee_match") else 0,
                "log_size": math.log(size) if size and size > 0 else None,
                "prior_12mo_return": row.get("prior_12mo_return"),
                "size_band": row["amount_range"],
                "chamber": row["chamber"],
                "party": row["party"],
                "seniority_terms": _seniority(row["bioguide_id"], row["report_date"]),
                "bioguide_id": row["bioguide_id"],
                "year": row["report_date"].year,
                "industry": row.get("industry", "Other"),
            }
        )
    return pl.DataFrame(rows).drop_nulls(["car", "log_size"])


def run_model2(df: pl.DataFrame) -> dict:
    """Fit Model 2: pooled OLS with member/year/industry FE absorbed via
    AbsorbingLS, standard errors clustered at the member level.

    book-to-market is intentionally OMITTED as a control -- no data source
    for it exists in this project. This is a documented, pre-registered
    scope decision (see module docstring), not a silent gap.
    """
    from linearmodels.iv.absorbing import AbsorbingLS

    pdf = df.to_pandas()
    pdf["sale_x_opportunistic"] = pdf["sale"] * pdf["opportunistic"]
    pdf["sale_x_committee_match"] = pdf["sale"] * pdf["committee_match"]

    numeric_regressors = [
        "sale", "opportunistic", "sale_x_opportunistic", "committee_match",
        "sale_x_committee_match", "log_size", "prior_12mo_return", "seniority_terms",
    ]
    categorical_regressors = pd.get_dummies(pdf[["size_band", "chamber", "party"]], drop_first=True)
    exog = pd.concat([pdf[numeric_regressors], categorical_regressors], axis=1).astype(float)
    exog = pd.concat([pd.Series(1.0, index=exog.index, name="const"), exog], axis=1)

    absorb = pdf[["bioguide_id", "year", "industry"]].astype("category")

    model = AbsorbingLS(pdf["car"].astype(float), exog, absorb=absorb)
    fit = model.fit(cov_type="clustered", clusters=pdf["bioguide_id"])

    return {
        "params": {k: float(v) for k, v in fit.params.items() if k != "const"},
        "se": {k: float(v) for k, v in fit.std_errors.items() if k != "const"},
        "n_obs": int(fit.nobs),
        "n_absorbed_member": pdf["bioguide_id"].nunique(),
        "n_absorbed_year": pdf["year"].nunique(),
        "n_absorbed_industry": pdf["industry"].nunique(),
    }
