from __future__ import annotations

from datetime import date

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
