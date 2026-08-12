from __future__ import annotations

from datetime import date

import polars as pl

from congressional_sales.sample import classify

SAMPLE_SCHEMA = {
    "ticker": pl.Utf8, "politician": pl.Utf8, "bioguide_id": pl.Utf8, "chamber": pl.Utf8,
    "party": pl.Utf8, "transaction": pl.Utf8, "transaction_date": pl.Date, "report_date": pl.Date,
    "amount_low": pl.Float64, "amount_range": pl.Utf8, "ticker_type": pl.Utf8, "description": pl.Utf8,
    "excess_return": pl.Float64, "price_change": pl.Float64, "spy_change": pl.Float64,
}


def _row(ticker, bioguide, tdate, transaction="Purchase"):
    return {
        "ticker": ticker, "politician": bioguide, "bioguide_id": bioguide, "chamber": "Representatives",
        "party": "R", "transaction": transaction, "transaction_date": tdate, "report_date": tdate,
        "amount_low": 1001.0, "amount_range": "$1,001 - $15,000", "ticker_type": "ST", "description": None,
        "excess_return": None, "price_change": None, "spy_change": None,
    }


def test_is_routine_trader_flags_same_month_three_years_running():
    rows = pl.DataFrame(
        [
            _row("AAPL", "A1", date(2020, 3, 10)),
            _row("MSFT", "A1", date(2019, 3, 5)),
            _row("NVDA", "A1", date(2018, 3, 20)),
            _row("XOM", "A1", date(2017, 3, 1)),
        ],
        schema=SAMPLE_SCHEMA,
    )
    out = classify.is_routine_trader(rows)
    row2020 = out.filter(pl.col("transaction_date") == date(2020, 3, 10))
    assert row2020["is_routine"][0] is True


def test_is_routine_trader_does_not_flag_a_one_off_trade():
    rows = pl.DataFrame([_row("AAPL", "A1", date(2020, 3, 10))], schema=SAMPLE_SCHEMA)
    out = classify.is_routine_trader(rows)
    assert out["is_routine"][0] is False


def test_committee_match_flags_matching_sector():
    rows = pl.DataFrame([_row("XOM", "A1", date(2020, 3, 10))], schema=SAMPLE_SCHEMA)
    assignments = pl.DataFrame(
        {
            "bioguide_id": ["A1"], "committee_code": ["SSEG"], "chamber": ["senate"],
            "committee_name": ["Senate Committee on Energy and Natural Resources"],
        }
    )
    sic = pl.DataFrame(
        {"ticker": ["XOM"], "cik": [34088], "sic_code": ["2911"], "sic_description": ["Petroleum Refining"]},
        schema={"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8},
    )
    out = classify.committee_match(rows, assignments, sic)
    assert out["committee_match"][0] is True


def test_committee_match_false_for_unrelated_sector():
    rows = pl.DataFrame([_row("XOM", "A1", date(2020, 3, 10))], schema=SAMPLE_SCHEMA)
    assignments = pl.DataFrame(
        {
            "bioguide_id": ["A1"], "committee_code": ["SSAF"], "chamber": ["senate"],
            "committee_name": ["Senate Committee on Agriculture, Nutrition, and Forestry"],
        }
    )
    sic = pl.DataFrame(
        {"ticker": ["XOM"], "cik": [34088], "sic_code": ["2911"], "sic_description": ["Petroleum Refining"]},
        schema={"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8},
    )
    out = classify.committee_match(rows, assignments, sic)
    assert out["committee_match"][0] is False


def test_committee_sectors_returns_all_matching_sectors_not_just_first():
    # "Energy and Commerce" matches BOTH the "Energy" keyword (-> Energy
    # sector) and the "Commerce" keyword (-> Business Equipment sector). A
    # first-match-wins classifier only ever returns "Energy" and silently
    # drops "Business Equipment" -- this is the exact bug the fix covers.
    sectors = classify._committee_sectors("House Committee on Energy and Commerce")
    assert set(sectors) == {"Energy", "Business Equipment"}


def test_committee_match_flags_second_keyword_sector_for_multi_keyword_committee():
    # Same "Energy and Commerce" committee as above, but exercised end to
    # end through committee_match: the traded ticker's FF12 sector (Business
    # Equipment, from SIC 7372) is only reachable via the SECOND keyword
    # ("Commerce") that matches this committee's name. Under the old
    # first-match-wins _committee_sector, this committee only ever resolved
    # to "Energy", so this trade was never flagged -- proving the bug.
    rows = pl.DataFrame([_row("IBM", "A1", date(2020, 3, 10))], schema=SAMPLE_SCHEMA)
    assignments = pl.DataFrame(
        {
            "bioguide_id": ["A1"], "committee_code": ["HSIF"], "chamber": ["house"],
            "committee_name": ["House Committee on Energy and Commerce"],
        }
    )
    sic = pl.DataFrame(
        {"ticker": ["IBM"], "cik": [51143], "sic_code": ["7372"], "sic_description": ["Prepackaged Software"]},
        schema={"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8},
    )
    out = classify.committee_match(rows, assignments, sic)
    assert out["committee_match"][0] is True


def test_committee_match_adds_only_the_flag_column():
    # committee_match must follow this module's own convention (and
    # screens.py's): add exactly one new boolean column to the input,
    # nothing else -- no leaked join-intermediate columns like sic_code
    # or _sector.
    rows = pl.DataFrame([_row("XOM", "A1", date(2020, 3, 10))], schema=SAMPLE_SCHEMA)
    assignments = pl.DataFrame(
        {
            "bioguide_id": ["A1"], "committee_code": ["SSEG"], "chamber": ["senate"],
            "committee_name": ["Senate Committee on Energy and Natural Resources"],
        }
    )
    sic = pl.DataFrame(
        {"ticker": ["XOM"], "cik": [34088], "sic_code": ["2911"], "sic_description": ["Petroleum Refining"]},
        schema={"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8},
    )
    out = classify.committee_match(rows, assignments, sic)
    assert set(out.columns) - set(rows.columns) == {"committee_match"}


def _xom_sic():
    return pl.DataFrame(
        {"ticker": ["XOM"], "cik": [34088], "sic_code": ["2911"], "sic_description": ["Petroleum Refining"]},
        schema={"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8},
    )


def _historical(bioguide, committee_name, start, end=None, chamber="senate"):
    return pl.DataFrame(
        {
            "bioguide_id": [bioguide], "committee_name": [committee_name], "chamber": [chamber],
            "assignment_start": [start], "assignment_end": [end],
        },
        schema={
            "bioguide_id": pl.Utf8, "committee_name": pl.Utf8, "chamber": pl.Utf8,
            "assignment_start": pl.Date, "assignment_end": pl.Date,
        },
    )


def test_committee_match_uses_historical_assignment_as_of_transaction_date():
    # Member's CURRENT committee (Banking -> Money) does NOT match XOM's
    # Energy sector, but their HISTORICAL committee, in force on the
    # transaction's own date, does -- confirms the historical lookup is
    # actually consulted, not silently bypassed in favor of current.
    rows = pl.DataFrame([_row("XOM", "A1", date(2016, 3, 10))], schema=SAMPLE_SCHEMA)
    current_assignments = pl.DataFrame(
        {
            "bioguide_id": ["A1"], "committee_code": ["SSBK"], "chamber": ["senate"],
            "committee_name": ["Senate Committee on Banking, Housing, and Urban Affairs"],
        }
    )
    historical = _historical("A1", "Senate Committee on Energy and Natural Resources", date(2015, 1, 6), date(2017, 1, 3))
    out = classify.committee_match(rows, current_assignments, _xom_sic(), historical_assignments=historical)
    assert out["committee_match"][0] is True


def test_committee_match_falls_back_to_current_snapshot_after_coverage_end():
    # Same historical row as above, but the transaction postdates the
    # historical source's own documented coverage boundary -- must fall
    # back to the current (non-matching) snapshot rather than using a
    # historical row the source can't actually vouch for at that date.
    rows = pl.DataFrame([_row("XOM", "A1", date(2022, 3, 10))], schema=SAMPLE_SCHEMA)
    current_assignments = pl.DataFrame(
        {
            "bioguide_id": ["A1"], "committee_code": ["SSBK"], "chamber": ["senate"],
            "committee_name": ["Senate Committee on Banking, Housing, and Urban Affairs"],
        }
    )
    historical = _historical("A1", "Senate Committee on Energy and Natural Resources", date(2015, 1, 6), None)
    out = classify.committee_match(rows, current_assignments, _xom_sic(), historical_assignments=historical)
    assert out["committee_match"][0] is False


def test_committee_match_falls_back_to_current_snapshot_when_no_historical_row_covers_the_date():
    # transaction_date predates this member's earliest historical
    # assignment entirely -- no historical row covers it, so this must
    # fall back to the (matching) current snapshot rather than reporting
    # no match at all.
    rows = pl.DataFrame([_row("XOM", "A1", date(2013, 3, 10))], schema=SAMPLE_SCHEMA)
    current_assignments = pl.DataFrame(
        {
            "bioguide_id": ["A1"], "committee_code": ["SSEG"], "chamber": ["senate"],
            "committee_name": ["Senate Committee on Energy and Natural Resources"],
        }
    )
    historical = _historical("A1", "Senate Committee on Banking, Housing, and Urban Affairs", date(2015, 1, 6), date(2017, 1, 3))
    out = classify.committee_match(rows, current_assignments, _xom_sic(), historical_assignments=historical)
    assert out["committee_match"][0] is True


def test_committee_match_treats_null_assignment_end_as_an_open_still_active_assignment():
    rows = pl.DataFrame([_row("XOM", "A1", date(2016, 6, 1))], schema=SAMPLE_SCHEMA)
    current_assignments = pl.DataFrame(
        {"bioguide_id": [], "committee_code": [], "chamber": [], "committee_name": []},
        schema={"bioguide_id": pl.Utf8, "committee_code": pl.Utf8, "chamber": pl.Utf8, "committee_name": pl.Utf8},
    )
    historical = _historical("A1", "Senate Committee on Energy and Natural Resources", date(2015, 1, 6), None)
    out = classify.committee_match(rows, current_assignments, _xom_sic(), historical_assignments=historical)
    assert out["committee_match"][0] is True
