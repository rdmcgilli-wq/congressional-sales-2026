"""Legislator terms and committee assignments, from the public-domain
unitedstates/congress-legislators project (no auth, no rate-limit concern
at our volume -- a handful of large YAML files fetched once and cached in
the warehouse).

Committee membership is a CURRENT-ONLY snapshot -- the upstream project
does not publish historical per-congress committee membership. H4's
CommitteeMatch therefore uses each member's most recent known committee
assignment, not their true assignment at the historical transaction date.
This is a documented limitation (see PRE_ANALYSIS_PLAN.md Global
Constraints), implemented exactly this way on purpose, not silently.
"""

from __future__ import annotations

import yaml
import polars as pl

from .. import storage
from ..http import get_text

LEGISLATORS_CURRENT_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-current.yaml"
LEGISLATORS_HISTORICAL_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-historical.yaml"
COMMITTEE_MEMBERSHIP_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/committee-membership-current.yaml"
COMMITTEES_CURRENT_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/committees-current.yaml"

TERMS_SCHEMA = {
    "bioguide_id": pl.Utf8, "full_name": pl.Utf8, "chamber": pl.Utf8,
    "term_start": pl.Date, "term_end": pl.Date, "state": pl.Utf8, "party": pl.Utf8,
}


def parse_legislator_terms(docs: list[dict]) -> pl.DataFrame:
    rows = []
    for person in docs:
        bioguide = person.get("id", {}).get("bioguide")
        if not bioguide:
            continue
        full_name = person.get("name", {}).get("official_full", "")
        for term in person.get("terms", []):
            rows.append(
                {
                    "bioguide_id": bioguide,
                    "full_name": full_name,
                    "chamber": term.get("type"),
                    "term_start": term.get("start"),
                    "term_end": term.get("end"),
                    "state": term.get("state"),
                    "party": term.get("party"),
                }
            )
    if not rows:
        return pl.DataFrame(schema=TERMS_SCHEMA)
    return (
        pl.DataFrame(rows)
        .with_columns(pl.col("term_start").str.to_date("%Y-%m-%d"), pl.col("term_end").str.to_date("%Y-%m-%d"))
        .select(list(TERMS_SCHEMA))
        .cast(TERMS_SCHEMA)  # type: ignore[arg-type]
    )


ASSIGNMENTS_SCHEMA = {"bioguide_id": pl.Utf8, "committee_code": pl.Utf8, "committee_name": pl.Utf8, "chamber": pl.Utf8}


def parse_committee_assignments(membership: dict, committees: list[dict]) -> pl.DataFrame:
    name_and_chamber = {c["thomas_id"]: (c["name"], c["type"]) for c in committees if "thomas_id" in c}
    for c in committees:
        parent_id = c.get("thomas_id")
        if not parent_id:
            continue
        for sub in c.get("subcommittees", []) or []:
            sub_id = sub.get("thomas_id")
            if not sub_id:
                continue
            # Subcommittee entries don't carry their own `type` -- inherit the parent's chamber.
            name_and_chamber[parent_id + sub_id] = (f"{c['name']} - {sub['name']}", c["type"])
    rows = []
    for code, members in membership.items():
        name, chamber = name_and_chamber.get(code, (code, "unknown"))
        for m in members:
            bioguide = m.get("bioguide")
            if not bioguide:
                continue
            rows.append({"bioguide_id": bioguide, "committee_code": code, "committee_name": name, "chamber": chamber})
    if not rows:
        return pl.DataFrame(schema=ASSIGNMENTS_SCHEMA)
    return pl.DataFrame(rows).select(list(ASSIGNMENTS_SCHEMA)).cast(ASSIGNMENTS_SCHEMA)  # type: ignore[arg-type]


def ingest_legislator_terms() -> int:
    current = yaml.safe_load(get_text(LEGISLATORS_CURRENT_URL)) or []
    historical = yaml.safe_load(get_text(LEGISLATORS_HISTORICAL_URL)) or []
    df = parse_legislator_terms(current + historical)
    if df.is_empty():
        return 0
    storage.write("legislator_terms", df, key_cols=["bioguide_id", "chamber", "term_start"])
    return storage.read("legislator_terms").height


def ingest_committee_assignments() -> int:
    membership = yaml.safe_load(get_text(COMMITTEE_MEMBERSHIP_URL)) or {}
    committees = yaml.safe_load(get_text(COMMITTEES_CURRENT_URL)) or []
    df = parse_committee_assignments(membership, committees)
    if df.is_empty():
        return 0
    storage.write("committee_assignments", df, key_cols=["bioguide_id", "committee_code"])
    return df.height
