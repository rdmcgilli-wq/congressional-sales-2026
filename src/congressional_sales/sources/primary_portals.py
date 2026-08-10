"""URL builders (not automated pullers -- see this task's plan notes) for
the two primary disclosure portals, used only to support the Section 11
20-transaction hand-check. Never bulk-scraped -- see Global Constraints."""

from __future__ import annotations

from datetime import date

HOUSE_DISCLOSURE_BASE = "https://disclosures-clerk.house.gov/PublicDisclosure/FinancialDisclosure"
SENATE_EFD_SEARCH_BASE = "https://efdsearch.senate.gov/search/"


def house_disclosure_url(ticker: str, report_date: date) -> str:
    return f"{HOUSE_DISCLOSURE_BASE}?ticker={ticker.upper()}&year={report_date.year}"


def senate_efd_search_url() -> str:
    return SENATE_EFD_SEARCH_BASE
