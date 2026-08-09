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


def committee_match(sample: pl.DataFrame, assignments: pl.DataFrame, sic: pl.DataFrame) -> pl.DataFrame:
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
    # maintain_order="left" is required on THIS join too (not just the
    # member_sectors join below): `matched` further down is built by
    # iterating a joined frame's rows positionally and attaching the result
    # back onto `sample` via pl.Series(...), so every join in this function
    # must preserve `sample`'s original row order. Same bug class as Task
    # 10/12's fix; polars' own docs do not guarantee left-join row order
    # without this parameter.
    df = sample.join(sic.select("ticker", "sic_code"), on="ticker", how="left", maintain_order="left").with_columns(
        pl.col("sic_code").map_elements(ff12_industry, return_dtype=pl.Utf8, skip_nulls=False).alias("_sector")
    )
    member_sectors = (
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
    joined = df.join(member_sectors, on="bioguide_id", how="left", maintain_order="left")
    matched = [
        row["_sector"] in (row["_member_sectors"] or [])
        for row in joined.select("_sector", "_member_sectors").iter_rows(named=True)
    ]
    # Attach the flag to the ORIGINAL `sample` frame, not `df` -- `df`
    # carries this function's own join-intermediate helper columns
    # (sic_code, _sector), and leaking those into the return value would
    # break this module's convention (matching is_routine_trader above and
    # every screen in screens.py: add exactly one new column, nothing
    # else). This is safe only because every join above uses
    # maintain_order="left", so `matched`'s positions line up with
    # `sample`'s original row order.
    return sample.with_columns(pl.Series("committee_match", matched))
