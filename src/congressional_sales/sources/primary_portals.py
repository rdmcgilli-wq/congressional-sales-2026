"""URL builders (not automated pullers -- see this task's plan notes) for
the two primary disclosure portals, used only to support the Section 11
20-transaction hand-check. Never bulk-scraped -- see Global Constraints.

UNVERIFIED: neither site was confirmed against a live session during
planning. Both are HTML-form/search-driven, not documented JSON APIs.
house_disclosure_url's `?ticker=...&year=...` query string is a
plausible guess, not a confirmed working deep link -- it may land on a
generic search page rather than pre-filtered results. Navigate the
portal manually and confirm the actual path before relying on either
URL for a real hand-check."""

from __future__ import annotations

from datetime import date

HOUSE_DISCLOSURE_BASE = "https://disclosures-clerk.house.gov/PublicDisclosure/FinancialDisclosure"
SENATE_EFD_SEARCH_BASE = "https://efdsearch.senate.gov/search/"


def house_disclosure_url(ticker: str, report_date: date) -> str:
    # Unverified query format -- see module docstring. May not pre-filter
    # results; confirm the real navigation path manually before use.
    return f"{HOUSE_DISCLOSURE_BASE}?ticker={ticker.upper()}&year={report_date.year}"


def senate_efd_search_url() -> str:
    # Senate eFD requires session-based form interaction that can't be
    # captured in a URL -- this deliberately returns only the base search
    # page, not an (impossible) pre-filled query URL.
    return SENATE_EFD_SEARCH_BASE
