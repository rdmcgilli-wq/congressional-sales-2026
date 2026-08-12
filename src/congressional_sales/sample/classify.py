"""Screen 4 (routine vs. opportunistic, H3) and committee-jurisdiction
matching (H4), PRE_ANALYSIS_PLAN.md Section 5 / Section 7."""

from __future__ import annotations

import re

import polars as pl

from .industry import ff12_industry


def is_routine_trader(sample: pl.DataFrame) -> pl.DataFrame:
    df = sample
    months = df.select("bioguide_id", pl.col("transaction_date").dt.year().alias("y"), pl.col("transaction_date").dt.month().alias("m")).unique()
    active_year_months = set(months.iter_rows())

    def _routine(bioguide: str, y: int, m: int) -> bool:
        return all((bioguide, y - k, m) in active_year_months for k in (1, 2, 3))

    flags = [
        _routine(row["bioguide_id"], row["transaction_date"].year, row["transaction_date"].month)
        for row in df.iter_rows(named=True)
    ]
    return df.with_columns(pl.Series("is_routine", flags))


# Committee subject-area keyword -> FF12 industry it most plausibly has
# jurisdiction over. A research judgment, not a fact -- reviewed as code,
# shown verbatim in the paper's methodology section.
_COMMITTEE_KEYWORDS: list[tuple[str, str]] = [
    ("Agriculture", "Consumer NonDurables"),
    ("Energy", "Energy"),
    ("Natural Resources", "Energy"),
    ("Financial Services", "Money"),
    ("Banking", "Money"),
    ("Armed Services", "Manufacturing"),
    ("Commerce", "Business Equipment"),
    ("Science", "Business Equipment"),
    ("Technology", "Business Equipment"),
    ("Communications", "Telephone and Television Transmission"),
    ("Health", "Healthcare"),
    ("Transportation", "Other"),
    ("Homeland Security", "Other"),
]


def _committee_sectors(committee_name: str) -> list[str]:
    # Returns ALL sectors whose keyword appears in the committee name, not
    # just the first hit. A first-match-wins version of this function was
    # shipped originally and found, on review against Task 6's real
    # committee_assignments table, to silently collapse large committees
    # with multi-word jurisdictions -- e.g. "House Committee on Energy and
    # Commerce" (54 current members) matches both "Energy" and "Commerce"
    # keywords, but a first-match version only ever returned "Energy" and
    # lost the committee's real jurisdiction over Business Equipment
    # (Commerce/Science/Tech) matters. Same issue for "Senate Committee on
    # Commerce, Science, and Transportation" (28 members). See
    # test_committee_sectors_returns_all_matching_sectors_not_just_first.
    return list({sector for keyword, sector in _COMMITTEE_KEYWORDS if keyword.lower() in committee_name.lower()})


def committee_match(
    sample: pl.DataFrame,
    assignments: pl.DataFrame,
    sic: pl.DataFrame,
    historical_assignments: pl.DataFrame | None = None,
    historical_coverage_end=None,
) -> pl.DataFrame:
    """`historical_assignments` (optional, additive) is
    sources.legislators.parse_historical_committee_assignments' output
    shape -- bioguide_id, committee_name, chamber, assignment_start,
    assignment_end. When supplied, a sample row's committee membership is
    looked up AS OF its own transaction_date from this table first, for
    any transaction_date strictly before `historical_coverage_end`
    (defaults to sources.legislators.
    HISTORICAL_COMMITTEE_ASSIGNMENTS_COVERAGE_END -- the real,
    documented boundary of the one free historical source this project
    found; see that module's docstring). `assignment_end` null means a
    still-open assignment as of the historical dataset's own last update
    -- treated as covering the transaction_date, not as missing data.

    A row with no historical match at all (no `historical_assignments`
    passed, transaction_date at or after the coverage boundary, or no
    historical row exists for that member/date -- e.g. the source's own
    103rd-Congress start predates it) falls back to the CURRENT-only
    `assignments` snapshot, exactly as this function has always behaved.
    This makes historical support strictly additive: every existing
    caller that doesn't pass the two new parameters gets the identical
    current-snapshot-only result as before.
    """
    if historical_coverage_end is None:
        from ..sources.legislators import HISTORICAL_COMMITTEE_ASSIGNMENTS_COVERAGE_END

        historical_coverage_end = HISTORICAL_COMMITTEE_ASSIGNMENTS_COVERAGE_END

    # skip_nulls=False is required here, not optional: this left join can
    # produce a null sic_code for any sample ticker with no SIC match, and
    # polars' map_elements defaults to skip_nulls=True -- which means the
    # null bypasses ff12_industry() entirely (leaving _sector null) rather
    # than calling it with None, even though ff12_industry(None) is
    # explicitly coded to return "Other". This exact bug was found live
    # during Task 9's implementation (same join-then-map_elements pattern,
    # different consumer) -- row counts were never wrong, only the label
    # (unmatched rows got a silent null sector instead of "Other"). Fixed
    # here pre-emptively rather than left for Task 13 to rediscover.
    #
    # maintain_order="left" is required here: the per-row loop below reads
    # `df` positionally and attaches its result back onto `sample` via
    # pl.Series(...), so this join must preserve `sample`'s original row
    # order. Same bug class as Task 10/12's fix; polars' own docs do not
    # guarantee left-join row order without this parameter.
    df = sample.join(sic.select("ticker", "sic_code"), on="ticker", how="left", maintain_order="left").with_columns(
        pl.col("sic_code").map_elements(ff12_industry, return_dtype=pl.Utf8, skip_nulls=False).alias("_sector")
    )

    # Current-snapshot member -> sectors, unchanged from before this
    # function took historical_assignments: the fallback path for any row
    # the historical lookup below doesn't resolve.
    member_sectors_current = (
        assignments.with_columns(
            pl.col("committee_name")
            .map_elements(_committee_sectors, return_dtype=pl.List(pl.Utf8))
            .alias("_committee_sectors")
        )
        .filter(pl.col("_committee_sectors").list.len() > 0)
        # empty_as_null is pinned explicitly (not left to polars' default)
        # because the default is changing in polars 2.0 and this call would
        # otherwise emit a DeprecationWarning on every invocation. It is
        # functionally moot either way -- the filter directly above already
        # removes every empty-list row before this explode runs, so there
        # is nothing left for empty_as_null to affect.
        .explode("_committee_sectors", empty_as_null=True)
        .group_by("bioguide_id")
        .agg(pl.col("_committee_sectors").unique().alias("_member_sectors"))
    )
    current_lookup: dict[str, list[str]] = dict(
        zip(member_sectors_current["bioguide_id"].to_list(), member_sectors_current["_member_sectors"].to_list())
    )

    # As-of historical assignments, grouped by member once up front rather
    # than re-filtering the whole historical_assignments frame per sample
    # row.
    historical_by_member: dict[str, list[tuple]] = {}
    if historical_assignments is not None and not historical_assignments.is_empty():
        for row in historical_assignments.iter_rows(named=True):
            historical_by_member.setdefault(row["bioguide_id"], []).append(
                (row["assignment_start"], row["assignment_end"], row["committee_name"])
            )

    matched = []
    for row in df.select("bioguide_id", "transaction_date", "_sector").iter_rows(named=True):
        bioguide, txn_date, sector = row["bioguide_id"], row["transaction_date"], row["_sector"]
        member_sectors: list[str] | None = None
        if txn_date is not None and txn_date < historical_coverage_end and bioguide in historical_by_member:
            as_of_committees = [
                name
                for start, end, name in historical_by_member[bioguide]
                if start <= txn_date and (end is None or txn_date <= end)
            ]
            if as_of_committees:
                sectors: set[str] = set()
                for name in as_of_committees:
                    sectors.update(_committee_sectors(name))
                member_sectors = sorted(sectors)
        if member_sectors is None:
            member_sectors = current_lookup.get(bioguide, [])
        matched.append(sector in member_sectors)

    # Attach the flag to the ORIGINAL `sample` frame, not `df` -- `df`
    # carries this function's own join-intermediate helper columns
    # (sic_code, _sector), and leaking those into the return value would
    # break this module's convention (matching is_routine_trader above and
    # every screen in screens.py: add exactly one new column, nothing
    # else). This is safe only because the join above uses
    # maintain_order="left", so `matched`'s positions line up with
    # `sample`'s original row order.
    return sample.with_columns(pl.Series("committee_match", matched))
