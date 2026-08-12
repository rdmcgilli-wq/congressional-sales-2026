"""Robustness suite, PRE_ANALYSIS_PLAN.md Section 9 / T7. Every check
reruns only the pre-specified primary test (beta_sale in Model 2, 90-day
horizon, four-factor, screened sample) -- see this task's plan notes for
why items 6 and 10 are handled outside this module."""

from __future__ import annotations

import polars as pl
from linearmodels.panel.utility import AbsorbingEffectError

from .models import model2


def winsorize(values: pl.Series, lower: float = 0.01, upper: float = 0.99) -> pl.Series:
    # interpolation="linear" is required, not cosmetic: polars' default
    # quantile interpolation is "nearest", which for small/boundary-heavy
    # samples can return the sample's own max/min as the clip bound (e.g.
    # a 6-point [1,2,3,4,100,-100] array's nearest-interpolated 90th
    # percentile is exactly 100.0), silently no-op'ing the clip on
    # precisely the extreme values winsorizing exists to control. Linear
    # interpolation is also the standard convention for winsorizing in
    # applied statistics (matches numpy.percentile's default), not just a
    # fix for this test.
    lo = values.quantile(lower, interpolation="linear")
    hi = values.quantile(upper, interpolation="linear")
    return values.clip(lo, hi)


def _most_frequent(sample: pl.DataFrame, col: str, n: int) -> set:
    counts = sample.group_by(col).agg(pl.len().alias("_n")).sort("_n", descending=True)
    return set(counts[col].head(n).to_list())


def _run_primary(label: str, df: pl.DataFrame, size_proxies: dict, terms: pl.DataFrame, car_col: str) -> dict:
    if df.height < 10:
        return {"check": label, "beta_sale": None, "se": None, "n": df.height}
    frame = model2.build_model2_frame(df, size_proxies, terms, car_col)
    if frame.height < 10 or frame["bioguide_id"].n_unique() < 2:
        return {"check": label, "beta_sale": None, "se": None, "n": frame.height}
    # A robustness check restricting the sample (by chamber, by year, by
    # excluding top traders, ...) can leave a subset where the fixed-
    # effects structure itself degenerates -- e.g. every remaining row
    # shares one year or one industry (AbsorbingLS/pyhdfe: "All fixed
    # effects after the first one should have more than one level",
    # plain ValueError), or a regressor becomes perfectly collinear with
    # the absorbed effects on that particular subset (AbsorbingEffectError,
    # NOT a ValueError subclass -- confirmed against the installed
    # linearmodels version before this task was built; both must be
    # caught explicitly). Confirmed empirically pre-build: even a
    # reasonably sized, well-randomized 10-member/80-row panel produces
    # this on its senate_only subset (only 3 of 10 members are Senate).
    # This is exactly the "too few observations to run a meaningful
    # regression" case the None-row contract already covers -- a
    # degenerate FE structure is a form of insufficient variation, not a
    # different failure category -- so it must return the same None row
    # rather than letting the whole suite crash.
    try:
        result = model2.run_model2(frame)
    except (ValueError, AbsorbingEffectError):
        return {"check": label, "beta_sale": None, "se": None, "n": frame.height}
    return {"check": label, "beta_sale": result["params"].get("sale"), "se": result["se"].get("sale"), "n": result["n_obs"]}


def run_robustness_suite(
    sample_with_car: pl.DataFrame, size_proxies: dict, terms: pl.DataFrame,
    car_col: str = "car_four_factor_90", filing_date_variant: pl.DataFrame | None = None,
) -> pl.DataFrame:
    checks = []
    df = sample_with_car

    checks.append(_run_primary("full_screened_sample", df, size_proxies, terms, car_col))

    top5 = _most_frequent(df, "bioguide_id", 5)
    checks.append(_run_primary("excl_top5_traders", df.filter(~pl.col("bioguide_id").is_in(top5)), size_proxies, terms, car_col))
    top10 = _most_frequent(df, "bioguide_id", 10)
    checks.append(_run_primary("excl_top10_traders", df.filter(~pl.col("bioguide_id").is_in(top10)), size_proxies, terms, car_col))

    checks.append(_run_primary("excl_2020_2021", df.filter(~pl.col("report_date").dt.year().is_in([2020, 2021])), size_proxies, terms, car_col))

    for band in df["amount_range"].unique().to_list():
        checks.append(_run_primary(f"size_band_{band}", df.filter(pl.col("amount_range") == band), size_proxies, terms, car_col))

    top_tickers = _most_frequent(df, "ticker", 10)
    checks.append(_run_primary("excl_top10_tickers", df.filter(~pl.col("ticker").is_in(top_tickers)), size_proxies, terms, car_col))

    checks.append(_run_primary("excl_tech_sector", df.filter(pl.col("industry") != "Business Equipment"), size_proxies, terms, car_col))

    winsorized = df.with_columns(winsorize(df[car_col]).alias(car_col))
    checks.append(_run_primary("winsorized_1_99", winsorized, size_proxies, terms, car_col))

    seniority_counts = (
        terms.group_by("bioguide_id").agg(pl.len().alias("n_terms")).filter(pl.col("n_terms") >= 3)["bioguide_id"]
    )
    checks.append(_run_primary("three_plus_terms", df.filter(pl.col("bioguide_id").is_in(seniority_counts)), size_proxies, terms, car_col))

    checks.append(_run_primary("senate_only", df.filter(pl.col("chamber") == "Senate"), size_proxies, terms, car_col))
    checks.append(_run_primary("house_only", df.filter(pl.col("chamber") == "Representatives"), size_proxies, terms, car_col))

    if filing_date_variant is not None:
        checks.append(_run_primary("filing_date_entry", filing_date_variant, size_proxies, terms, car_col))

    return pl.DataFrame(checks)


def year_by_year_effects(
    sample_with_car: pl.DataFrame, size_proxies: dict, terms: pl.DataFrame, car_col: str, ci_z: float = 1.96,
) -> pl.DataFrame:
    """Section 9 item 2 ("does the effect exist outside 2020-2021?") and F7:
    beta_sale re-estimated separately within each calendar year present in
    `sample_with_car` (grouped on `report_date`, matching this module's
    other checks -- e.g. excl_2020_2021 above -- which also group on
    report_date rather than transaction_date).

    Uses model2.run_model2(..., absorb_year=False): a single-year subset
    makes `year` constant, which the pre-registered specification's YearFE
    would find degenerate (see that parameter's docstring). MemberFE and
    IndustryFE remain absorbed exactly as in the primary specification --
    this is not a different model, just the one already-inert term removed.

    Returns one row per year: beta_sale, se_sale, a ci_z-sigma normal-
    approximation confidence interval (ci_z=1.96 -> ~95%, matching what F7
    plots), and n. A year too thin to fit (fewer than 10 rows, fewer than
    10 complete-case regression rows, or a degenerate FE structure even
    without YearFE) reports a None row rather than raising -- the same
    "insufficient variation is not a different failure category" contract
    _run_primary above already uses.
    """
    rows = []
    for year in sorted(sample_with_car["report_date"].dt.year().unique().to_list()):
        year_df = sample_with_car.filter(pl.col("report_date").dt.year() == year)
        row = {"year": year, "beta_sale": None, "se_sale": None, "ci_lower": None, "ci_upper": None, "n": year_df.height}
        if year_df.height >= 10:
            frame = model2.build_model2_frame(year_df, size_proxies, terms, car_col)
            if frame.height >= 10 and frame["bioguide_id"].n_unique() >= 2:
                try:
                    result = model2.run_model2(frame, absorb_year=False)
                except (ValueError, AbsorbingEffectError):
                    result = None
                if result is not None:
                    beta, se = result["params"].get("sale"), result["se"].get("sale")
                    if beta is not None and se is not None:
                        row.update(
                            {
                                "beta_sale": beta, "se_sale": se,
                                "ci_lower": beta - ci_z * se, "ci_upper": beta + ci_z * se,
                                "n": result["n_obs"],
                            }
                        )
        rows.append(row)
    return pl.DataFrame(rows)
