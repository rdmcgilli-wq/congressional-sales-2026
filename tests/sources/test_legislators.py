from __future__ import annotations

from datetime import date

import pandas as pd
import polars as pl
import pytest
import yaml

from congressional_sales.sources import legislators

LEGISLATOR_YAML = """
- id:
    bioguide: C000127
  name:
    first: Maria
    last: Cantwell
    official_full: Maria Cantwell
  terms:
  - type: rep
    start: '1993-01-05'
    end: '1995-01-03'
    state: WA
    district: 1
    party: Democrat
  - type: sen
    start: '2001-01-03'
    end: '2007-01-03'
    state: WA
    class: 1
    party: Democrat
"""

COMMITTEE_MEMBERSHIP_YAML = """
SSAF:
- name: John Boozman
  party: majority
  rank: 1
  title: Chairman
  bioguide: B001236
- name: Amy Klobuchar
  party: minority
  rank: 1
  bioguide: K000367
"""

COMMITTEES_YAML = """
- type: senate
  name: Senate Committee on Agriculture, Nutrition, and Forestry
  thomas_id: SSAF
"""

COMMITTEE_MEMBERSHIP_SUBCOMMITTEE_YAML = """
HSAG15:
- name: Some Member
  party: majority
  rank: 1
  bioguide: X000001
"""

COMMITTEES_WITH_SUBCOMMITTEE_YAML = """
- type: house
  name: House Committee on Agriculture
  thomas_id: HSAG
  subcommittees:
  - name: Forestry and Horticulture
    thomas_id: '15'
"""


def test_parse_legislator_terms_produces_one_row_per_term():
    docs = yaml.safe_load(LEGISLATOR_YAML)
    df = legislators.parse_legislator_terms(docs)
    assert df.height == 2
    assert df["bioguide_id"][0] == "C000127"
    assert df["chamber"][0] == "rep"
    assert df["term_start"][0] == date(1993, 1, 5)
    assert df["term_end"][0] == date(1995, 1, 3)
    assert df["chamber"][1] == "sen"
    assert df["party"][1] == "Democrat"


def test_parse_committee_assignments_maps_code_to_name():
    membership = yaml.safe_load(COMMITTEE_MEMBERSHIP_YAML)
    committees = yaml.safe_load(COMMITTEES_YAML)
    df = legislators.parse_committee_assignments(membership, committees)
    assert df.height == 2
    boozman = df.filter(df["bioguide_id"] == "B001236")
    assert boozman["committee_name"][0] == "Senate Committee on Agriculture, Nutrition, and Forestry"
    assert boozman["chamber"][0] == "senate"


def test_parse_committee_assignments_resolves_subcommittee_codes():
    membership = yaml.safe_load(COMMITTEE_MEMBERSHIP_SUBCOMMITTEE_YAML)
    committees = yaml.safe_load(COMMITTEES_WITH_SUBCOMMITTEE_YAML)
    df = legislators.parse_committee_assignments(membership, committees)
    assert df.height == 1
    row = df.filter(df["bioguide_id"] == "X000001")
    assert row["committee_name"][0] == "House Committee on Agriculture - Forestry and Horticulture"
    assert row["chamber"][0] == "house"


def test_ingest_legislator_terms_writes_both_current_and_historical(monkeypatch):
    monkeypatch.setattr(
        legislators, "get_text",
        lambda url, *a, **k: LEGISLATOR_YAML if "current" in url or "historical" in url else "",
    )
    n = legislators.ingest_legislator_terms()
    assert n == 2  # same fixture used for both current+historical -> deduped by (bioguide,chamber,term_start)
    from congressional_sales import storage
    got = storage.read("legislator_terms")
    assert got.height == 2


def test_ingest_committee_assignments_writes_table(monkeypatch):
    monkeypatch.setattr(
        legislators, "get_text",
        lambda url, *a, **k: COMMITTEE_MEMBERSHIP_YAML if "membership" in url else COMMITTEES_YAML,
    )
    n = legislators.ingest_committee_assignments()
    assert n == 2
    from congressional_sales import storage
    got = storage.read("committee_assignments")
    assert got.height == 2


LEGISLATOR_WITH_ICPSR_YAML = """
- id:
    bioguide: B001236
    icpsr: 29701
  name:
    official_full: John Boozman
- id:
    bioguide: K000367
    icpsr: 40305
  name:
    official_full: Amy Klobuchar
- id:
    bioguide: Z999999
  name:
    official_full: No ICPSR On File
"""


def test_parse_icpsr_crosswalk_extracts_bioguide_and_icpsr_pairs():
    docs = yaml.safe_load(LEGISLATOR_WITH_ICPSR_YAML)
    df = legislators.parse_icpsr_crosswalk(docs)
    assert df.height == 2  # the third person, with no icpsr id, is dropped
    row = df.filter(pl.col("bioguide_id") == "B001236")
    assert row["icpsr_id"][0] == 29701


def test_parse_icpsr_crosswalk_on_empty_docs_returns_typed_empty_frame():
    df = legislators.parse_icpsr_crosswalk([])
    assert df.is_empty()
    assert df.schema["icpsr_id"] == pl.Int64


def test_ingest_icpsr_crosswalk_writes_table(monkeypatch):
    monkeypatch.setattr(legislators, "get_text", lambda url, *a, **k: LEGISLATOR_WITH_ICPSR_YAML)
    n = legislators.ingest_icpsr_crosswalk()
    assert n == 2
    from congressional_sales import storage
    got = storage.read("icpsr_crosswalk")
    assert got.height == 2


def _stewart_woon_fixture(rows: list[dict]) -> pd.DataFrame:
    """A pandas DataFrame shaped like Stewart & Woon's real file, already
    past the header=1 read (see parse_historical_committee_assignments's
    docstring) -- confirmed live against the real
    house_assignments_103-115-1.xls column names before this was written."""
    base = {
        "Congress": 115, "Committee code": 102, "ID #": 20531, "Name": "Test Member",
        "Maj/Min": 1, "Rank Within Party Status": 1, "Party": 200,
        "Date of Assignment": pd.Timestamp("2017-01-03"), "Date of Termination": pd.NaT,
        "Senior Party Member": 0, "Committee Seniority": 1, "Committee Period of Service": 1,
        "Committee status at end of this Congress": None, "Committee continuity of assignment in next Congress": None,
        "Appointment Citation": None, "Committee Name": "Agriculture",
        "State": 49.0, "CD": 11.0, "State Name": "TX", "Notes": None,
    }
    full_rows = []
    for overrides in rows:
        row = dict(base)
        row.update(overrides)
        full_rows.append(row)
    return pd.DataFrame(full_rows)


def _stewart_woon_senate_fixture(rows: list[dict]) -> pd.DataFrame:
    """Senate-shaped variant of _stewart_woon_fixture -- confirmed live
    against the real senate_assignments_103-115-1.xls column names, which
    are NOT identical to the House file's: "Date of Appointment" (not
    "Date of Assignment"), "Committee Code" (not "Committee code"),
    "Rank Within Party" (not "Rank Within Party Status"), "Party Code"
    (not "Party"). Only the columns parse_historical_committee_assignments
    actually reads need to be exactly right for this fixture's purpose;
    the rest are carried over from the House base for convenience since
    they're never inspected."""
    base = {
        "Congress": 115, "Committee Code": 305, "ID #": 20531, "Name": "Test Member",
        "Maj/Min": 1, "Rank Within Party": 1, "Party Code": 100,
        "Date of Appointment": pd.Timestamp("2017-01-03"), "Date of Termination": pd.NaT,
        "Senior Party Member": 0, "Committee Seniority": 1, "Committee Period of Service": 1,
        "Committee status at end of this Congress": None, "Committee continuity of assignment in next Congress": None,
        "Appointment Citation": None, "Committee Name": "Agriculture, Nutrition, and Forestry",
        "State Code": 6, "District": 83, "State Name": "VT", "Notes": None,
    }
    full_rows = []
    for overrides in rows:
        row = dict(base)
        row.update(overrides)
        full_rows.append(row)
    return pd.DataFrame(full_rows)


def _crosswalk(pairs: dict) -> pl.DataFrame:
    return pl.DataFrame(
        {"bioguide_id": list(pairs.keys()), "icpsr_id": list(pairs.values())},
        schema={"bioguide_id": pl.Utf8, "icpsr_id": pl.Int64},
    )


def test_parse_historical_committee_assignments_resolves_via_crosswalk():
    raw = _stewart_woon_fixture([{"ID #": 20531, "Committee Name": "Agriculture"}])
    crosswalk = _crosswalk({"C000001": 20531})
    df = legislators.parse_historical_committee_assignments(raw, "house", crosswalk)
    assert df.height == 1
    assert df["bioguide_id"][0] == "C000001"
    assert df["committee_name"][0] == "Agriculture"
    assert df["chamber"][0] == "house"
    assert df["assignment_start"][0] == date(2017, 1, 3)


def test_parse_historical_committee_assignments_keeps_open_assignment_as_null_end():
    # Date of Termination is NaT in the base fixture -- a still-open
    # assignment as of the dataset's own last update, a real value to carry
    # through, not a parsing failure.
    raw = _stewart_woon_fixture([{"ID #": 20531}])
    crosswalk = _crosswalk({"C000001": 20531})
    df = legislators.parse_historical_committee_assignments(raw, "house", crosswalk)
    assert df["assignment_end"][0] is None


def test_parse_historical_committee_assignments_drops_unresolvable_icpsr():
    raw = _stewart_woon_fixture([{"ID #": 99999}])  # not in the crosswalk
    crosswalk = _crosswalk({"C000001": 20531})
    df = legislators.parse_historical_committee_assignments(raw, "house", crosswalk)
    assert df.is_empty()


def test_parse_historical_committee_assignments_accepts_the_senate_column_name():
    # THE regression test for the real bug this fix covers: the Senate
    # file's start-date column is "Date of Appointment", not "Date of
    # Assignment" -- confirmed live, and the original implementation
    # raised a bare KeyError on this shape.
    raw = _stewart_woon_senate_fixture([{"ID #": 20531, "Committee Name": "Agriculture, Nutrition, and Forestry"}])
    crosswalk = _crosswalk({"C000001": 20531})
    df = legislators.parse_historical_committee_assignments(raw, "senate", crosswalk)
    assert df.height == 1
    assert df["bioguide_id"][0] == "C000001"
    assert df["chamber"][0] == "senate"
    assert df["assignment_start"][0] == date(2017, 1, 3)


def test_parse_historical_committee_assignments_raises_clearly_when_neither_column_exists():
    raw = _stewart_woon_fixture([{"ID #": 20531}]).drop(columns=["Date of Assignment"])
    crosswalk = _crosswalk({"C000001": 20531})
    with pytest.raises(ValueError, match="Date of Assignment.*Date of Appointment"):
        legislators.parse_historical_committee_assignments(raw, "house", crosswalk)


def test_parse_historical_committee_assignments_on_empty_input_returns_typed_empty_frame():
    df = legislators.parse_historical_committee_assignments(pd.DataFrame(), "house", _crosswalk({}))
    assert df.is_empty()
    assert df.schema["assignment_start"] == pl.Date


def test_ingest_historical_committee_assignments_raises_without_a_crosswalk():
    # icpsr_crosswalk must be ingested first -- there is no other way to
    # resolve Stewart & Woon's ICPSR-keyed rows to a bioguide_id.
    with pytest.raises(RuntimeError, match="icpsr_crosswalk"):
        legislators.ingest_historical_committee_assignments()


def test_ingest_historical_committee_assignments_writes_table(monkeypatch):
    from congressional_sales import storage

    crosswalk = _crosswalk({"C000001": 20531, "C000002": 20999})
    storage.write("icpsr_crosswalk", crosswalk, key_cols=["bioguide_id"])

    house_raw = _stewart_woon_fixture([{"ID #": 20531, "Committee Name": "Agriculture"}])
    # Genuinely Senate-shaped, not an empty House-column frame: the whole
    # point of this orchestration test is that BOTH real column layouts
    # get exercised through the real ingest_historical_committee_assignments
    # entry point, since an earlier version of this fixture used House
    # columns for the "senate" case and never would have caught the real
    # "Date of Appointment" vs "Date of Assignment" mismatch this file's
    # own regression test (above) now covers at the parse layer.
    senate_raw = _stewart_woon_senate_fixture([{"ID #": 20999, "Committee Name": "Finance"}])

    # The real xlrd/.xls round trip against MIT's actual files was verified
    # live during research, not re-tested here -- this test isolates the
    # ORCHESTRATION (both URLs fetched, both parsed, results combined and
    # written), which parse_historical_committee_assignments' own tests
    # above don't exercise. get_bytes is monkeypatched to a URL-tagged
    # marker; pandas.read_excel is monkeypatched to resolve that marker
    # back to the house or the senate fixture frame.
    def fake_get_bytes(url, *a, **k):
        return b"house" if "house" in url else b"senate"

    def fake_read_excel(buf, engine=None, header=None):
        return house_raw if buf.getvalue() == b"house" else senate_raw

    monkeypatch.setattr(legislators, "get_bytes", fake_get_bytes)
    monkeypatch.setattr("pandas.read_excel", fake_read_excel)

    n = legislators.ingest_historical_committee_assignments()
    assert n == 2
    got = storage.read("committee_assignments_historical").sort("bioguide_id")
    assert got.height == 2
    assert got["bioguide_id"].to_list() == ["C000001", "C000002"]
    assert got.filter(pl.col("bioguide_id") == "C000002")["chamber"][0] == "senate"
