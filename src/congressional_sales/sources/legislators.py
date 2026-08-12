"""Legislator terms and committee assignments, from the public-domain
unitedstates/congress-legislators project (no auth, no rate-limit concern
at our volume -- a handful of large YAML files fetched once and cached in
the warehouse), plus a second, historical committee-assignment source
(see below) that partially closes what was previously a current-only-
snapshot limitation.

Committee membership from unitedstates/congress-legislators is a
CURRENT-ONLY snapshot -- that upstream project does not publish historical
per-congress committee membership. `ingest_committee_assignments` /
`parse_committee_assignments` below are exactly this current-only source,
kept as the fallback `sample.classify.committee_match` uses whenever no
historical assignment is available for a given member/date (see the
historical source's own coverage boundary, documented next).

**Historical (session-level) committee assignments.** Charles Stewart III
and Jonathan Woon's "Congressional Committee Assignments" data (MIT, no
auth) is the one free, structured, per-member, per-Congress committee
roster this project could find -- live-verified 2026-08-12: real
Congress/member/committee/date rows, keyed on each member's ICPSR ID (not
bioguide_id, hence the crosswalk built below from the SAME
unitedstates/congress-legislators YAML this module already fetches, which
carries an `icpsr` field on ~98% of legislators). Its real, load-bearing
limitation: coverage runs from the 103rd Congress (1993) through the very
start of the 115th (assignment dates in the raw file end 2017-01-24, no
termination date yet recorded for that Congress at the time the dataset
was last updated) -- effectively through early 2019 by the 115th
Congress's own term boundary. No free source for the 116th Congress
onward (2019-) was found. `HISTORICAL_COMMITTEE_ASSIGNMENTS_COVERAGE_END`
below is that boundary, stated explicitly rather than left implicit, and
`sample.classify.committee_match` falls back to the current-only snapshot
for any transaction on or after it -- a real, permanent, documented gap
for roughly the second half of this study's 2014-2025 sample period, not
a full fix. See PRE_ANALYSIS_PLAN.md's Global Constraints for the
citation and the addendum recording this decision.
"""

from __future__ import annotations

import io
from datetime import date

import yaml
import polars as pl

from .. import storage
from ..http import get_bytes, get_text

LEGISLATORS_CURRENT_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-current.yaml"
LEGISLATORS_HISTORICAL_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-historical.yaml"
COMMITTEE_MEMBERSHIP_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/committee-membership-current.yaml"
COMMITTEES_CURRENT_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/committees-current.yaml"

# Charles Stewart III & Jonathan Woon, "Congressional Committee Assignments,
# 103rd to 115th Congresses," https://web.mit.edu/cstewart/www/data/ --
# see module docstring for coverage and the crosswalk this data needs.
HOUSE_HISTORICAL_ASSIGNMENTS_URL = "https://web.mit.edu/cstewart/www/data/house_assignments_103-115-1.xls"
SENATE_HISTORICAL_ASSIGNMENTS_URL = "https://web.mit.edu/cstewart/www/data/senate_assignments_103-115-1.xls"
# The 115th Congress's term ran 2017-01-03..2019-01-03; the raw file's
# assignment dates for that Congress stop at 2017-01-24 with no
# termination date recorded (dataset last updated mid-115th-Congress), so
# this project treats the whole 115th Congress term as covered and draws
# the boundary at its constitutional end, not at the dataset's own last
# recorded row.
HISTORICAL_COMMITTEE_ASSIGNMENTS_COVERAGE_END = date(2019, 1, 3)

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


ICPSR_CROSSWALK_SCHEMA = {"bioguide_id": pl.Utf8, "icpsr_id": pl.Int64}


def parse_icpsr_crosswalk(docs: list[dict]) -> pl.DataFrame:
    """bioguide_id <-> ICPSR ID, from the SAME legislator YAML docs
    `parse_legislator_terms` reads -- each person's `id:` block carries
    both (`~98%` of `legislators-historical.yaml`, confirmed live). This is
    the join key `parse_historical_committee_assignments` needs: Stewart
    and Woon's data identifies members by ICPSR ID, not bioguide_id."""
    rows = []
    for person in docs:
        bioguide = person.get("id", {}).get("bioguide")
        icpsr = person.get("id", {}).get("icpsr")
        if not bioguide or icpsr is None:
            continue
        rows.append({"bioguide_id": bioguide, "icpsr_id": icpsr})
    if not rows:
        return pl.DataFrame(schema=ICPSR_CROSSWALK_SCHEMA)
    return (
        pl.DataFrame(rows)
        .unique(subset=["bioguide_id"])
        .select(list(ICPSR_CROSSWALK_SCHEMA))
        .cast(ICPSR_CROSSWALK_SCHEMA)  # type: ignore[arg-type]
    )


def ingest_icpsr_crosswalk() -> int:
    current = yaml.safe_load(get_text(LEGISLATORS_CURRENT_URL)) or []
    historical = yaml.safe_load(get_text(LEGISLATORS_HISTORICAL_URL)) or []
    df = parse_icpsr_crosswalk(current + historical)
    if df.is_empty():
        return 0
    storage.write("icpsr_crosswalk", df, key_cols=["bioguide_id"])
    return df.height


HISTORICAL_ASSIGNMENTS_SCHEMA = {
    "bioguide_id": pl.Utf8, "committee_name": pl.Utf8, "chamber": pl.Utf8,
    "assignment_start": pl.Date, "assignment_end": pl.Date,
}


def parse_historical_committee_assignments(raw, chamber: str, icpsr_crosswalk: pl.DataFrame) -> pl.DataFrame:
    """`raw` is a pandas DataFrame already shaped like Stewart & Woon's own
    file layout (i.e. `pandas.read_excel(..., header=1)`'s output -- row 0
    of the raw sheet is a "Date of dataset: ..." title, not data; the real
    header is row 1). Resolves each row's ICPSR `ID #` to a bioguide_id via
    `icpsr_crosswalk` (parse_icpsr_crosswalk's output); a row whose ICPSR ID
    has no crosswalk match is dropped, not defaulted -- there is no
    meaningful fallback bioguide_id for an unresolvable member.
    `assignment_end` is null for a still-open assignment (no termination
    date yet recorded as of the dataset's own last update) -- this is a
    real, meaningful null carried through, not an ingestion failure; see
    HISTORICAL_COMMITTEE_ASSIGNMENTS_COVERAGE_END for how the caller
    (sample.classify.committee_match) is expected to treat it.
    """
    if raw.empty:
        return pl.DataFrame(schema=HISTORICAL_ASSIGNMENTS_SCHEMA)
    cols = raw[["ID #", "Committee Name", "Date of Assignment", "Date of Termination"]].copy()
    cols.columns = ["icpsr_id", "committee_name", "assignment_start", "assignment_end"]
    df = (
        pl.from_pandas(cols)
        .with_columns(
            pl.col("icpsr_id").cast(pl.Int64, strict=False),
            pl.col("assignment_start").cast(pl.Date, strict=False),
            pl.col("assignment_end").cast(pl.Date, strict=False),
            pl.lit(chamber).alias("chamber"),
        )
        .drop_nulls(["icpsr_id", "committee_name", "assignment_start"])
    )
    joined = df.join(icpsr_crosswalk, on="icpsr_id", how="inner")
    if joined.is_empty():
        return pl.DataFrame(schema=HISTORICAL_ASSIGNMENTS_SCHEMA)
    return joined.select(list(HISTORICAL_ASSIGNMENTS_SCHEMA)).cast(HISTORICAL_ASSIGNMENTS_SCHEMA)  # type: ignore[arg-type]


def ingest_historical_committee_assignments() -> int:
    import pandas as pd

    crosswalk = storage.read("icpsr_crosswalk")
    if crosswalk.is_empty():
        raise RuntimeError(
            "icpsr_crosswalk is empty -- run ingest_icpsr_crosswalk() before "
            "ingest_historical_committee_assignments(); the historical data is keyed on "
            "ICPSR ID and has no other way to resolve a bioguide_id."
        )
    frames = []
    for url, chamber in ((HOUSE_HISTORICAL_ASSIGNMENTS_URL, "house"), (SENATE_HISTORICAL_ASSIGNMENTS_URL, "senate")):
        raw_bytes = get_bytes(url)
        raw_df = pd.read_excel(io.BytesIO(raw_bytes), engine="xlrd", header=1)
        frames.append(parse_historical_committee_assignments(raw_df, chamber, crosswalk))
    combined = pl.concat(frames, how="vertical_relaxed")
    if combined.is_empty():
        return 0
    storage.write(
        "committee_assignments_historical", combined,
        key_cols=["bioguide_id", "committee_name", "assignment_start"],
    )
    return combined.height
