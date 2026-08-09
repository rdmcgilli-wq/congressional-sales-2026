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


def _committee_sector(committee_name: str) -> str | None:
    for keyword, sector in _COMMITTEE_KEYWORDS:
        if keyword.lower() in committee_name.lower():
            return sector
    return None


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
    df = sample.join(sic.select("ticker", "sic_code"), on="ticker", how="left").with_columns(
        pl.col("sic_code").map_elements(ff12_industry, return_dtype=pl.Utf8, skip_nulls=False).alias("_sector")
    )
    member_sectors = (
        assignments.with_columns(
            pl.col("committee_name").map_elements(_committee_sector, return_dtype=pl.Utf8).alias("_committee_sector")
        )
        .filter(pl.col("_committee_sector").is_not_null())
        .group_by("bioguide_id")
        .agg(pl.col("_committee_sector").unique().alias("_member_sectors"))
    )
    # maintain_order="left" is required here too: `matched` is built by
    # iterating joined's rows in whatever order the join produces, then
    # attached back to df positionally via pl.Series(...) below -- a
    # different frame's row order. Same bug class as Task 10/12's fix;
    # see those tasks' notes for the full explanation (polars' own docs
    # explicitly do not guarantee left-join output order without this
    # parameter).
    joined = df.join(member_sectors, on="bioguide_id", how="left", maintain_order="left")
    matched = [
        row["_sector"] in (row["_member_sectors"] or [])
        for row in joined.select("_sector", "_member_sectors").iter_rows(named=True)
    ]
    return df.with_columns(pl.Series("committee_match", matched))
