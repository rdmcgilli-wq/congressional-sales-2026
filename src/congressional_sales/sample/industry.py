"""Fama-French 12-industry classification from a 4-digit SIC code.

Uses Ken French's own published SIC-range definition
(https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html,
"Industry Portfolios" section, 12-industry definitions file) rather than a
hand-transcribed copy of the ranges -- SIC-range tables like this are long
and easy to get subtly wrong by memory, so this module fetches the
authoritative source and parses it, the same discipline used for the
factor files in sources/french.py.

Format (confirmed live against the real Siccodes12.zip -- see
tests/sample/test_industry.py and task-7-report.md for the verification):
each industry's block starts with a line like
" 1 NoDur  Consumer Nondurables -- Food, Tobacco, Textiles, Apparel, Leather,
Toys" (industry number, short code, full name), followed by indented
SIC-range lines like "          0100-0999" with NO trailing description
text on the range line itself and CRLF line endings. Blocks are separated
by a blank line. The "Other" industry (12) is the catch-all and has no
explicit range lines in the file at all -- everything not covered by
industries 1-11 falls through to "Other" via ff12_industry's default.
"""

from __future__ import annotations

import re
from functools import lru_cache

FF12_DEFINITIONS_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Siccodes12.zip"

_INDUSTRY_HEADER = re.compile(r"^\s*(\d{1,2})\s+(\S+)\s+(.+)$")
# Range lines carry only "SSSS-EEEE" with nothing after it on the real file
# (no trailing description), so the line must end right after the second
# 4-digit code -- do not require trailing whitespace there.
_RANGE_LINE = re.compile(r"^\s*(\d{4})-(\d{4})(?:\s|$)")

# Canonical short-code -> full industry name, per Ken French's own labels.
_NAMES = {
    "NoDur": "Consumer NonDurables", "Durbl": "Consumer Durables", "Manuf": "Manufacturing",
    "Enrgy": "Energy", "Chems": "Chemicals", "BusEq": "Business Equipment",
    "Telcm": "Telephone and Television Transmission", "Utils": "Utilities",
    "Shops": "Shops", "Hlth": "Healthcare", "Money": "Money", "Other": "Other",
}


def _parse_ranges(text: str) -> list[tuple[int, int, str]]:
    ranges: list[tuple[int, int, str]] = []
    current_name = "Other"
    for line in text.splitlines():
        header = _INDUSTRY_HEADER.match(line)
        rng = _RANGE_LINE.match(line)
        if header and not rng:
            short_code = header.group(2)
            current_name = _NAMES.get(short_code, short_code)
        elif rng:
            ranges.append((int(rng.group(1)), int(rng.group(2)), current_name))
    return ranges


@lru_cache(maxsize=1)
def load_ff12_ranges() -> list[tuple[int, int, str]]:
    import io
    import zipfile

    from ..http import get_bytes

    zbytes = get_bytes(FF12_DEFINITIONS_URL)
    with zipfile.ZipFile(io.BytesIO(zbytes)) as zf:
        name = zf.namelist()[0]
        text = zf.read(name).decode("latin-1")
    return _parse_ranges(text)


def ff12_industry(sic_code: str | None) -> str:
    if not sic_code:
        return "Other"
    try:
        code = int(sic_code)
    except ValueError:
        return "Other"
    for lo, hi, name in load_ff12_ranges():
        if lo <= code <= hi:
            return name
    return "Other"
