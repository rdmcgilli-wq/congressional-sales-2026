"""Model 2 (Section 7): pooled fixed-effects regression.

    CAR_i = b0 + b1*Sale_i + b2*Opportunistic_i + b3*(Sale x Opportunistic)_i
            + b4*CommitteeMatch_i + b5*(Sale x CommitteeMatch)_i
            + gamma*Controls_i + MemberFE + YearFE + IndustryFE + e_i

This is the study's PRIMARY specification: b1 (the `sale` coefficient) at
the 90-day horizon, four-factor adjusted, screened sample, is the single
pre-registered primary test the whole study is built around.

Controls implemented: log_size (Task 16's dollar-volume proxy, in place of
log market cap -- no shares-outstanding source in this project),
prior_12mo_return, size_band, seniority_terms.

book-to-market is OMITTED -- no data source for it exists in this
project. This is a documented deviation from Section 7, not a silent
gap; state it in the paper's limitations section.

chamber and party are NOT regressors -- they are mechanically absorbed
by MemberFE.

`chamber` and `party` are member-INVARIANT: a member's chamber and party
essentially never change within the sample window. MemberFE is explicitly
part of the pre-registered Model 2 specification above, and once member
fixed effects are included, ANY time-invariant covariate is perfectly
collinear with (fully redundant with) the member effect -- its own
coefficient is not identified. This is a basic, unavoidable fact of
linear algebra that holds in any statistical software, not a quirk of
`linearmodels` or of this codebase.

Including chamber/party dummies in `exog` alongside MemberFE absorption
therefore makes the model unidentified, and `AbsorbingLS` correctly
raises `AbsorbingEffectError` ("chamber_Senate, party_R ... have been
fully absorbed") on essentially any realistic screened sample. They are
consequently excluded from the regressor set.

This is NOT a deviation from the pre-analysis plan's intent, and not a
choice to drop pre-registered variables for convenience: the plan
pre-registers MemberFE, and chamber/party being subsumed by it is a
direct mathematical consequence of that pre-registered choice. A member
fixed effect controls for chamber and party strictly more flexibly than
chamber/party dummies do (it additionally absorbs every other
member-level characteristic, observed or not). This will be noted in the
paper's methodology section.

`size_band` dummies ARE retained: transaction size varies within a member
across transactions, so size_band has genuine within-member variation and
is not collinear with MemberFE.

`build_model2_frame` still carries `chamber`/`party` through as
DATA-ONLY columns (they are part of its documented output contract and
are useful for descriptive tables and heterogeneity splits); `run_model2`
simply never places them in `exog`.

Fixed effects (member, year, industry) are absorbed via
`linearmodels.iv.absorbing.AbsorbingLS` rather than materialized as dummy
columns, since member alone can span hundreds of levels. Standard errors
are clustered at the member (bioguide_id) level, with `debiased=True`
(see `run_model2`).

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

    `sample_with_car` MUST already carry `industry` and `prior_12mo_return`
    as real columns -- both are produced by
    `events.attach.attach_car_bhar` (Task 22). Their absence is a caller
    error (the sample was never run through `attach_car_bhar`) and raises
    `ValueError` rather than being silently defaulted: an all-null
    `prior_12mo_return` control, or an `industry` collapsed to a single
    value, yields a silently degenerate primary regression. Note that a
    genuinely unclassified ticker's REAL `industry` value is the string
    "Other" (computed by `ff12_industry`); that is a legitimate value and
    is entirely different from the column not existing at all.
    """
    required = ("industry", "prior_12mo_return")
    missing = [c for c in required if c not in sample_with_car.columns]
    if missing:
        raise ValueError(
            f"sample_with_car is missing required column(s): {', '.join(repr(c) for c in missing)}. "
            "Run the sample through events.attach.attach_car_bhar (Task 22) before "
            "build_model2_frame -- it computes 'industry' (Fama-French 12 sector via "
            "sample.industry.ff12_industry) and 'prior_12mo_return' (trailing ~252-session "
            "return). These are Model 2 controls/fixed effects and must not be defaulted."
        )

    def _seniority(bioguide: str, report_date) -> int:
        prior = terms.filter(
            (pl.col("bioguide_id") == bioguide) & (pl.col("term_start") < report_date)
        )
        return prior.height

    rows = []
    for row in sample_with_car.iter_rows(named=True):
        # Fail loud on an unrecognized transaction value rather than
        # silently coding it as a purchase (`1 if == "Sale" else 0`'s
        # original behavior). sample.funnel.build_sample's
        # directional_transaction_only step already normalizes real
        # Quiver Sale variants ("Sale (Full)"/"Sale (Partial)") to "Sale"
        # and excludes anything that isn't Purchase/Sale (Section 4's
        # "exchanges and transfers" exclusion) -- so this should never
        # fire on a sample that went through the funnel. It exists as a
        # safety net for a caller that bypasses the funnel, since a
        # silent default here would contaminate the comparison group of
        # this study's single pre-registered primary test (found during
        # the whole-branch review, not any single task review).
        if row["transaction"] not in ("Purchase", "Sale"):
            raise ValueError(
                f"Unrecognized transaction value {row['transaction']!r} for "
                f"{row['ticker']}/{row['bioguide_id']} reached build_model2_frame -- "
                "expected exactly 'Purchase' or 'Sale'. Run the sample through "
                "sample.funnel.build_sample first; its directional_transaction_only "
                "step normalizes Sale variants and excludes non-directional "
                "transactions (exchanges/transfers, Section 4)."
            )
        size = size_proxies.get((row["ticker"], row["report_date"]))
        rows.append(
            {
                "car": row[car_col],
                "sale": 1 if row["transaction"] == "Sale" else 0,
                "opportunistic": 0 if row.get("is_routine") else 1,
                "committee_match": 1 if row.get("committee_match") else 0,
                "log_size": math.log(size) if size and size > 0 else None,
                "prior_12mo_return": row["prior_12mo_return"],
                "size_band": row["amount_range"],
                # chamber/party are DATA-ONLY passengers here: part of this
                # function's documented output contract (descriptive tables,
                # heterogeneity splits), but never regressors in run_model2 --
                # MemberFE absorbs them. See module docstring.
                "chamber": row["chamber"],
                "party": row["party"],
                "seniority_terms": _seniority(row["bioguide_id"], row["report_date"]),
                "bioguide_id": row["bioguide_id"],
                "year": row["report_date"].year,
                "industry": row["industry"],
            }
        )
    # Complete-case on all three continuous regression inputs -- car,
    # log_size, and prior_12mo_return. A null prior_12mo_return means the
    # ticker lacks ~252 sessions of trailing price history (e.g. a recent
    # IPO or a thinly covered instrument); AbsorbingLS has no null-handling
    # of its own and silently drops such rows internally, producing a
    # length mismatch against the externally-passed `clusters` vector
    # (ValueError: operands could not be broadcast together). Dropping here
    # keeps the frame passed to run_model2 exactly the sample that is
    # actually regressed. This is a documented sample-inclusion decision:
    # trades lacking full trailing price history are excluded from Model 2,
    # not imputed. Note in the paper's limitations section.
    return pl.DataFrame(rows).drop_nulls(["car", "log_size", "prior_12mo_return"])


def run_model2(df: pl.DataFrame, absorb_year: bool = True) -> dict:
    """Fit Model 2: pooled OLS with member/year/industry FE absorbed via
    AbsorbingLS, standard errors clustered at the member level.

    book-to-market is intentionally OMITTED as a control -- no data source
    for it exists in this project. This is a documented, pre-registered
    scope decision (see module docstring), not a silent gap.

    `chamber` and `party` are intentionally NOT in the regressor set, even
    when present on `df`. Both are member-invariant (a member's chamber and
    party do not change within the sample), so once MemberFE is absorbed --
    and MemberFE is explicitly part of the pre-registered Model 2 spec --
    they are perfectly collinear with the member effect and their
    coefficients are not identified. Including them makes the model
    unidentified and `AbsorbingLS` raises `AbsorbingEffectError` on any
    sample with real House/Senate or R/D variation across members. This is
    standard, expected behavior for a fixed-effects regression with a
    time-invariant covariate in any statistical package, not a deviation
    from the plan's intent: MemberFE controls for chamber and party more
    flexibly than chamber/party dummies would. Noted in the paper's
    methodology section.

    `size_band` dummies ARE included -- transaction size varies within a
    member over time, so size_band is not collinear with MemberFE.

    `absorb_year=False` drops YearFE from the absorbed set, for exactly one
    caller: `robustness.year_by_year_effects` (Section 9 item 2 / F7), which
    fits this same specification separately within each single calendar
    year. `year` is constant within a single-year subset, so YearFE there
    has exactly one level -- degenerate ("All fixed effects after the first
    one should have more than one level", confirmed empirically against the
    installed linearmodels version before this parameter was added) and
    controls for nothing anyway, since there is no cross-year variation left
    within the subset to explain. MemberFE and IndustryFE are unaffected and
    still absorbed either way; this is the pre-registered specification with
    exactly one already-inert term removed, not a different model.
    """
    from linearmodels.iv.absorbing import AbsorbingLS

    pdf = df.to_pandas()
    pdf["sale_x_opportunistic"] = pdf["sale"] * pdf["opportunistic"]
    pdf["sale_x_committee_match"] = pdf["sale"] * pdf["committee_match"]

    numeric_regressors = [
        "sale", "opportunistic", "sale_x_opportunistic", "committee_match",
        "sale_x_committee_match", "log_size", "prior_12mo_return", "seniority_terms",
    ]
    # size_band ONLY. chamber/party are deliberately excluded -- they are
    # member-invariant and thus perfectly collinear with the absorbed
    # MemberFE (see docstring above). size_band varies within a member.
    categorical_regressors = pd.get_dummies(pdf[["size_band"]], drop_first=True)
    exog = pd.concat([pdf[numeric_regressors], categorical_regressors], axis=1).astype(float)
    exog = pd.concat([pd.Series(1.0, index=exog.index, name="const"), exog], axis=1)

    absorb_cols = ["bioguide_id", "year", "industry"] if absorb_year else ["bioguide_id", "industry"]
    absorb = pdf[absorb_cols].astype("category")

    model = AbsorbingLS(pdf["car"].astype(float), exog, absorb=absorb)
    # debiased=True applies the finite-sample cluster correction (a G/(G-1)-
    # style adjustment); linearmodels defaults it to False, which understates
    # clustered SEs by ~3% at realistic cluster counts. Set explicitly rather
    # than inherited from the library default, since b1 (`sale`) is the single
    # pre-registered primary test of this study and its SE must not be
    # understated. Standard practice for cluster-robust inference.
    fit = model.fit(cov_type="clustered", clusters=pdf["bioguide_id"], debiased=True)

    return {
        "params": {k: float(v) for k, v in fit.params.items() if k != "const"},
        "se": {k: float(v) for k, v in fit.std_errors.items() if k != "const"},
        # p-values for the same cluster-robust t-stats the params/se above
        # come from -- confirmed present on the installed linearmodels
        # version's AbsorbingLSResults (`'pvalues' in dir(...)`) before this
        # was added. Feeds Section 8's Benjamini-Hochberg correction, which
        # needs a p-value per one of the 18 pre-specified test variants.
        "pvalues": {k: float(v) for k, v in fit.pvalues.items() if k != "const"},
        "n_obs": int(fit.nobs),
        "n_absorbed_member": pdf["bioguide_id"].nunique(),
        "n_absorbed_year": pdf["year"].nunique(),
        "n_absorbed_industry": pdf["industry"].nunique(),
    }


def run_model2_auto_year(df: pl.DataFrame) -> dict:
    """`run_model2`, deciding `absorb_year` from `df` itself rather than
    requiring the caller to know in advance whether YearFE will be
    degenerate.

    Built for `scripts/run_holdout.py`: Section 9 item 10's 18-month
    holdout window can legitimately collapse to screened transactions
    within a single calendar year depending on real disclosure timing (an
    18-month window overlaps only 2 calendar years to begin with, and nothing
    guarantees both are represented after Screens 1-3). YearFE is then
    constant -- exactly the degenerate case `run_model2`'s own `absorb_year`
    parameter exists for (see its docstring) -- and the pre-registered fit
    would raise before producing any holdout result at all. Found via a
    synthetic end-to-end test that happened to construct exactly this case,
    not discovered by inspecting a real holdout result and patched
    afterward; PRE_ANALYSIS_PLAN.md's "do not patch and re-run after seeing
    the result" applies to changing the analysis in light of what it found,
    not to fixing a crash that prevents it from running at all.

    Checks `df["year"].n_unique()` directly rather than trying the full
    spec first and catching the resulting error: the failure mode is fully
    determined by this one count, so there is nothing to discover by
    letting `AbsorbingLS` fail first.

    Returns the same dict `run_model2` does, plus `absorbed_year: bool`, so
    a caller (and T8) can tell which specification actually ran rather than
    silently assuming the primary one.
    """
    absorb_year = df["year"].n_unique() > 1
    result = run_model2(df, absorb_year=absorb_year)
    return {**result, "absorbed_year": absorb_year}
