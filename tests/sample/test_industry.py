from __future__ import annotations

from congressional_sales.sample import industry

# Fixture mirrors the REAL Siccodes12.txt layout confirmed live against
# Ken French's data library (see task-7-report.md): CRLF line endings,
# range lines carrying ONLY "SSSS-EEEE" with no trailing description text,
# and a final "Other" block with no range lines at all (it's the catch-all).
_REAL_FORMAT_FIXTURE = (
    " 1 NoDur  Consumer Nondurables -- Food, Tobacco, Textiles, Apparel, Leather, Toys\r\n"
    "          0100-0999\r\n"
    "          2000-2399\r\n"
    "\r\n"
    " 6 BusEq  Business Equipment -- Computers, Software, and Electronic Equipment\r\n"
    "          3570-3579\r\n"
    "          3600-3699\r\n"
    "          7370-7379\r\n"
    "\r\n"
    "12 Other  Other -- Mines, Constr, BldMt, Trans, Hotels, Bus Serv, Entertainment\r\n"
)


def test_parse_ranges_handles_real_crlf_layout_with_no_trailing_text():
    ranges = industry._parse_ranges(_REAL_FORMAT_FIXTURE)
    assert (100, 999, "Consumer NonDurables") in ranges
    assert (7370, 7379, "Business Equipment") in ranges
    # "Other" is the catch-all in the real file and has no range lines.
    assert not any(name == "Other" for _, _, name in ranges)


def test_ff12_industry_classifies_a_known_tech_sic_code():
    """SIC 7372 (Prepackaged Software) is canonically Business Equipment
    in the Fama-French 12-industry scheme."""
    assert industry.ff12_industry("7372") == "Business Equipment"


def test_ff12_industry_unknown_code_returns_other():
    assert industry.ff12_industry("9999") == "Other"


def test_ff12_industry_handles_none_and_empty():
    assert industry.ff12_industry(None) == "Other"
    assert industry.ff12_industry("") == "Other"
