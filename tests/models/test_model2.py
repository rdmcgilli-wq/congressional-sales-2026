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
                            "chamber": "Representatives", "party": "R",
                            "seniority_terms": int(rng.integers(0, 6)),
                            "bioguide_id": member, "year": year, "industry": industry,
                        }
                    )
    return pl.DataFrame(rows)


def test_run_model2_returns_all_expected_coefficient_keys():
    df = _regression_frame()
    result = model2.run_model2(df)
    expected = {
        "sale", "opportunistic", "sale_x_opportunistic", "committee_match",
        "sale_x_committee_match", "log_size", "prior_12mo_return", "seniority_terms",
    }
    assert expected.issubset(result["params"].keys())
    assert expected.issubset(result["se"].keys())
    assert result["n_obs"] == df.height


def test_run_model2_sale_coefficient_is_positive_on_constructed_data():
    df = _regression_frame()
    result = model2.run_model2(df)
    assert result["params"]["sale"] > 0


def test_build_model2_frame_computes_seniority_from_prior_terms():
    sample = pl.DataFrame(
        {
            "ticker": ["AAPL"], "bioguide_id": ["A1"], "transaction": ["Sale"],
            "report_date": [date(2020, 6, 1)], "is_routine": [False], "committee_match": [True],
            "amount_range": ["$1,001 - $15,000"], "chamber": ["Representatives"], "party": ["R"],
            "car": [-0.05],
        }
    )
    terms = pl.DataFrame(
        {
            "bioguide_id": ["A1", "A1", "A1"], "full_name": ["x"] * 3, "chamber": ["rep"] * 3,
            "term_start": [date(2015, 1, 1), date(2017, 1, 1), date(2019, 1, 1)],
            "term_end": [date(2017, 1, 1), date(2019, 1, 1), date(2021, 1, 1)],
            "state": ["XX"] * 3, "party": ["R"] * 3,
        }
    )
    out = model2.build_model2_frame(sample, size_proxies={("AAPL", date(2020, 6, 1)): 100_000.0}, terms=terms, car_col="car")
    assert out["seniority_terms"][0] == 3  # all 3 prior terms started before the report_date
    assert out["sale"][0] == 1
    assert out["opportunistic"][0] == 1
