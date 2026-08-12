from __future__ import annotations

from datetime import date

import numpy as np
import polars as pl
import pytest

from congressional_sales.models import model2


def _regression_frame() -> pl.DataFrame:
    # A small, hand-constructed panel spanning 3 members x 2 years x 2
    # industries, with car deliberately higher for Sale=1 rows so beta_sale
    # should come out positive and detectable even after FE absorption --
    # this is a sanity/wiring check, not an exact-recovery proof (a
    # from-scratch exact-recovery test for a 3-way absorbed-FE model would
    # need a much larger synthetic panel than is proportionate here).
    #
    # opportunistic/committee_match/log_size/prior_12mo_return/seniority_terms
    # get deterministic (seeded) jitter rather than being held constant
    # across every row. A control that's literally constant across the
    # whole panel collapses to the exact zero vector once the
    # member/year/industry within-transformation removes each FE group's
    # mean (every FE group here has exactly one Sale=0 and one Sale=1
    # row, so a constant control has zero within-group variation left) --
    # its coefficient is then mathematically undefined, not just
    # numerically unstable, and AbsorbingLS correctly raises
    # AbsorbingEffectError rather than silently returning nonsense. The
    # seeded jitter gives each control genuine, non-degenerate variation
    # so all 8 coefficients this test asserts on are actually identified.
    rng = np.random.default_rng(20190101)
    rows = []
    for member in ["A1", "A2", "A3"]:
        for year in (2019, 2020):
            for industry in ("Business Equipment", "Energy"):
                for sale in (0, 1):
                    rows.append(
                        {
                            "car": (0.05 if sale else -0.01) + hash((member, year, industry)) % 5 * 0.001,
                            "sale": sale,
                            "opportunistic": int(rng.integers(0, 2)),
                            "committee_match": int(rng.integers(0, 2)),
                            "log_size": 10.0 + float(rng.normal(0, 0.5)),
                            "prior_12mo_return": 0.05 + float(rng.normal(0, 0.02)),
                            "size_band": "$1,001 - $15,000",
                            # chamber/party are carried as DATA-ONLY columns: they are
                            # part of build_model2_frame's output contract (descriptive
                            # tables, heterogeneity splits) but run_model2 must NOT put
                            # them in exog -- see test_run_model2_fits_when_chamber_and_
                            # party_vary_across_members for why.
                            "chamber": "Representatives", "party": "R",
                            "seniority_terms": int(rng.integers(0, 6)),
                            "bioguide_id": member, "year": year, "industry": industry,
                        }
                    )
    return pl.DataFrame(rows)


def _panel_with_chamber_and_party_variation() -> pl.DataFrame:
    # A panel with REAL cross-member variation in chamber (House/Senate) and
    # party (R/D), which is exactly what the real screened sample looks like
    # and what the original fixture above could not exercise (it holds
    # chamber/party at a single level each, so pd.get_dummies(..., drop_first=
    # True) emitted zero dummy columns and the collinearity was invisible).
    #
    # chamber and party are member-INVARIANT: a member's chamber/party
    # essentially never changes within the sample window. Once MemberFE is
    # absorbed, any member-invariant regressor is perfectly collinear with
    # the member effect, so including chamber/party dummies in exog makes
    # the model unidentified and AbsorbingLS raises AbsorbingEffectError.
    #
    # size_band, by contrast, varies WITHIN a member across transactions, so
    # its dummies survive absorption and must still be estimated.
    rng = np.random.default_rng(20200401)
    members = [
        ("M1", "Representatives", "R"),
        ("M2", "Representatives", "D"),
        ("M3", "Senate", "R"),
        ("M4", "Senate", "D"),
    ]
    bands = ["$1,001 - $15,000", "$15,001 - $50,000", "$50,001 - $100,000"]
    rows = []
    for member, chamber, party in members:
        for year in (2019, 2020):
            for industry in ("Business Equipment", "Energy", "Money"):
                for sale in (0, 1):
                    rows.append(
                        {
                            "car": (0.05 if sale else -0.01) + float(rng.normal(0, 0.01)),
                            "sale": sale,
                            "opportunistic": int(rng.integers(0, 2)),
                            "committee_match": int(rng.integers(0, 2)),
                            "log_size": 10.0 + float(rng.normal(0, 0.5)),
                            "prior_12mo_return": 0.05 + float(rng.normal(0, 0.02)),
                            # varies within member -> NOT absorbed by MemberFE
                            "size_band": bands[int(rng.integers(0, len(bands)))],
                            # constant within member -> absorbed by MemberFE
                            "chamber": chamber, "party": party,
                            "seniority_terms": int(rng.integers(0, 6)),
                            "bioguide_id": member, "year": year, "industry": industry,
                        }
                    )
    return pl.DataFrame(rows)


def _car_sample(**overrides) -> pl.DataFrame:
    """A single-row CAR-attached sample of the shape build_model2_frame consumes."""
    cols = {
        "ticker": ["AAPL"], "bioguide_id": ["A1"], "transaction": ["Sale"],
        "report_date": [date(2020, 6, 1)], "is_routine": [False], "committee_match": [True],
        "amount_range": ["$1,001 - $15,000"], "chamber": ["Representatives"], "party": ["R"],
        "car": [-0.05], "industry": ["Business Equipment"], "prior_12mo_return": [0.12],
    }
    cols.update(overrides)
    return pl.DataFrame(cols)


def test_run_model2_returns_all_expected_coefficient_keys():
    df = _regression_frame()
    result = model2.run_model2(df)
    expected = {
        "sale", "opportunistic", "sale_x_opportunistic", "committee_match",
        "sale_x_committee_match", "log_size", "prior_12mo_return", "seniority_terms",
    }
    assert expected.issubset(result["params"].keys())
    assert expected.issubset(result["se"].keys())
    assert expected.issubset(result["pvalues"].keys())
    assert result["n_obs"] == df.height


def test_run_model2_sale_coefficient_is_positive_on_constructed_data():
    df = _regression_frame()
    result = model2.run_model2(df)
    assert result["params"]["sale"] > 0


def test_run_model2_pvalues_are_valid_probabilities():
    # Section 8's Benjamini-Hochberg correction consumes these directly, so
    # they must be genuine p-values, not raw t-stats or something malformed.
    df = _regression_frame()
    result = model2.run_model2(df)
    for p in result["pvalues"].values():
        assert 0.0 <= p <= 1.0


def test_run_model2_absorb_year_false_fits_on_a_single_year_subset():
    # Section 9 item 2 / F7's whole reason for existing: a single-year
    # subset makes `year` constant, which the default absorb_year=True
    # raises on (YearFE has exactly one level). absorb_year=False drops
    # YearFE and must fit cleanly on exactly that subset.
    df = _panel_with_chamber_and_party_variation().filter(pl.col("year") == 2019)
    assert df["year"].n_unique() == 1
    with pytest.raises(ValueError):
        model2.run_model2(df)  # confirms the subset really is degenerate under the default
    result = model2.run_model2(df, absorb_year=False)
    assert result["n_obs"] == df.height
    assert "sale" in result["params"]
    assert all(se > 0 for se in result["se"].values())


def test_run_model2_fits_when_chamber_and_party_vary_across_members():
    # THE regression test for this fix. Before the fix, run_model2 built its
    # exog as pd.get_dummies(pdf[["size_band", "chamber", "party"]]) while
    # also absorbing MemberFE. chamber/party are member-invariant, so on any
    # panel with real House/Senate and R/D variation across members those
    # dummies are perfectly collinear with the absorbed member effect and
    # AbsorbingLS raised:
    #
    #   linearmodels.panel.utility.AbsorbingEffectError: ... The following
    #   variables or variable combinations have been fully absorbed or have
    #   become perfectly collinear after effects are removed:
    #       chamber_Senate, party_R
    #
    # i.e. the PRIMARY specification could not be fit on essentially any
    # realistic screened sample. The fix drops chamber/party from exog (they
    # are mechanically subsumed by MemberFE, which the pre-registered spec
    # requires); this test proves the fit now succeeds.
    df = _panel_with_chamber_and_party_variation()
    assert df["chamber"].n_unique() == 2 and df["party"].n_unique() == 2
    assert df["bioguide_id"].n_unique() == 4

    result = model2.run_model2(df)

    assert result["n_obs"] == df.height
    assert result["n_absorbed_member"] == 4
    # No chamber/party dummy ever reaches the regressor set.
    assert not [k for k in result["params"] if k.startswith(("chamber", "party"))]
    # ...but size_band varies WITHIN a member, so it is NOT absorbed and must
    # still be estimated. This guards against "fixing" the bug by stripping
    # every categorical control.
    assert [k for k in result["params"] if k.startswith("size_band")]
    core = {
        "sale", "opportunistic", "sale_x_opportunistic", "committee_match",
        "sale_x_committee_match", "log_size", "prior_12mo_return", "seniority_terms",
    }
    assert core.issubset(result["params"].keys())
    assert all(se > 0 for se in result["se"].values())


def test_build_model2_frame_computes_seniority_from_prior_terms():
    out = model2.build_model2_frame(
        _car_sample(), size_proxies={("AAPL", date(2020, 6, 1)): 100_000.0}, terms=_terms(), car_col="car"
    )
    assert out["seniority_terms"][0] == 3  # all 3 prior terms started before the report_date
    assert out["sale"][0] == 1
    assert out["opportunistic"][0] == 1


def test_build_model2_frame_reads_industry_and_prior_return_from_the_sample():
    # Real values must flow through untouched -- no silent default.
    out = model2.build_model2_frame(
        _car_sample(industry=["Energy"], prior_12mo_return=[-0.33]),
        size_proxies={("AAPL", date(2020, 6, 1)): 100_000.0}, terms=_terms(), car_col="car",
    )
    assert out["industry"][0] == "Energy"
    assert out["prior_12mo_return"][0] == pytest.approx(-0.33)


@pytest.mark.parametrize("missing", ["industry", "prior_12mo_return"])
def test_build_model2_frame_raises_when_required_car_columns_are_missing(missing):
    # These two columns are produced by events.attach.attach_car_bhar (Task 22).
    # A caller who skips that step must get a loud, actionable error rather
    # than a silently degenerate regression (the old code did
    # row.get("industry", "Other"), collapsing every ticker to one industry,
    # and row.get("prior_12mo_return") -> all-null control).
    sample = _car_sample().drop(missing)
    with pytest.raises(ValueError) as excinfo:
        model2.build_model2_frame(
            sample, size_proxies={("AAPL", date(2020, 6, 1)): 100_000.0}, terms=_terms(), car_col="car"
        )
    message = str(excinfo.value)
    assert missing in message
    assert "attach_car_bhar" in message


def test_build_model2_frame_drops_rows_with_null_prior_12mo_return():
    # Regression: a null prior_12mo_return (e.g. a ticker lacking ~252
    # sessions of trailing price history -- a recent IPO or thinly covered
    # instrument) must be dropped here, at frame-construction time, not left
    # to reach AbsorbingLS. AbsorbingLS silently drops null-containing rows
    # internally but the externally-passed `clusters` vector does not
    # shrink to match, which previously crashed run_model2 with "ValueError:
    # operands could not be broadcast together with shapes (48,1) (47,1)".
    sample = pl.concat(
        [
            _car_sample(),
            _car_sample(
                ticker=["MSFT"], bioguide_id=["A2"], report_date=[date(2020, 7, 1)],
                car=[0.02], prior_12mo_return=[None],
            ),
        ]
    )
    out = model2.build_model2_frame(
        sample,
        size_proxies={
            ("AAPL", date(2020, 6, 1)): 100_000.0,
            ("MSFT", date(2020, 7, 1)): 50_000.0,
        },
        terms=_terms(),
        car_col="car",
    )
    assert out.height == 1
    assert out["bioguide_id"][0] == "A1"


@pytest.mark.parametrize("bad_value", ["Sale (Partial)", "Exchange", "sale", ""])
def test_build_model2_frame_raises_on_unrecognized_transaction_value(bad_value):
    # Whole-branch review finding: the original code did
    # `1 if row["transaction"] == "Sale" else 0`, which silently coded
    # ANY non-"Sale" value -- including real Quiver Sale variants like
    # "Sale (Partial)" that sample.funnel.build_sample is now responsible
    # for normalizing before a frame ever reaches here -- as a purchase,
    # contaminating the primary test's comparison group. A caller that
    # bypasses the funnel (as this test deliberately does) must get a
    # loud, actionable error instead.
    sample = _car_sample(transaction=[bad_value])
    with pytest.raises(ValueError, match="Unrecognized transaction value"):
        model2.build_model2_frame(
            sample, size_proxies={("AAPL", date(2020, 6, 1)): 100_000.0}, terms=_terms(), car_col="car"
        )


def _terms() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "bioguide_id": ["A1", "A1", "A1"], "full_name": ["x"] * 3, "chamber": ["rep"] * 3,
            "term_start": [date(2015, 1, 1), date(2017, 1, 1), date(2019, 1, 1)],
            "term_end": [date(2017, 1, 1), date(2019, 1, 1), date(2021, 1, 1)],
            "state": ["XX"] * 3, "party": ["R"] * 3,
        }
    )
