from __future__ import annotations

from datetime import date

import polars as pl

from congressional_sales.sources import primary_portals
from congressional_sales.verification import hand_check


def test_select_worksheet_sample_is_deterministic_with_the_same_seed():
    sample = pl.DataFrame({"ticker": [f"T{i}" for i in range(100)], "car_market_90": [0.01 * i for i in range(100)]})
    a = hand_check.select_worksheet_sample(sample, n=20, seed=42)
    b = hand_check.select_worksheet_sample(sample, n=20, seed=42)
    assert a["ticker"].to_list() == b["ticker"].to_list()
    assert a.height == 20


def test_build_worksheet_adds_blank_manual_columns():
    rows = pl.DataFrame(
        {
            "ticker": ["AAPL"], "transaction": ["Sale"], "transaction_date": [date(2020, 6, 1)],
            "report_date": [date(2020, 6, 15)], "car_market_90": [-0.02],
        }
    )
    ws = hand_check.build_worksheet(rows)
    assert "manual_car_market_90" in ws.columns
    assert "matches_pipeline" in ws.columns
    assert ws["manual_car_market_90"][0] is None


def test_house_disclosure_url_is_well_formed():
    url = primary_portals.house_disclosure_url("AAPL", date(2020, 6, 15))
    assert url.startswith("https://disclosures-clerk.house.gov/")


def test_senate_efd_search_url_is_well_formed():
    assert primary_portals.senate_efd_search_url().startswith("https://efdsearch.senate.gov/")
