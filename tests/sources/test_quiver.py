from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from congressional_sales.sources import quiver

ROWS = [
    {
        "Representative": "David J. Taylor", "BioGuideID": "T000490",
        "ReportDate": "2026-08-06", "TransactionDate": "2026-07-24",
        "Ticker": "MSFT", "Transaction": "Purchase", "Range": "$1,001 - $15,000",
        "House": "Representatives", "Amount": "1001.0", "Party": "R",
        "last_modified": "2026-08-07", "TickerType": "ST", "Description": None,
        "ExcessReturn": 26.34, "PriceChange": 30.99, "SPYChange": 4.65,
    },
]


def test_parse_congress_trades_maps_fields_and_types():
    df = quiver.parse_congress_trades(ROWS)
    assert df.height == 1
    assert df["ticker"][0] == "MSFT"
    assert df["politician"][0] == "David J. Taylor"
    assert df["bioguide_id"][0] == "T000490"
    assert df["transaction_date"][0] == date(2026, 7, 24)
    assert df["report_date"][0] == date(2026, 8, 6)
    assert df["amount_low"][0] == 1001.0
    assert df["ticker_type"][0] == "ST"


def test_parse_congress_trades_on_empty_list_returns_typed_empty_frame():
    df = quiver.parse_congress_trades([])
    assert df.is_empty()
    assert df.schema["report_date"] == pl.Date


BULK_ROWS = [
    # Real bulk-endpoint field names, confirmed live -- NOT the same as
    # ROWS above (the per-ticker endpoint's shape). No "Range"/"Amount".
    {
        "Ticker": "IBP", "TickerType": "ST", "Name": "David J. Taylor",
        "BioGuideID": "T000490", "Filed": "2026-08-20", "Traded": "2026-08-14",
        "Party": "Republican", "Chamber": "Representatives", "Transaction": "Purchase",
        "Trade_Size_USD": "1001.0", "excess_return": "4.12",
    },
    {
        # same ticker, filed outside the period -- must be excluded
        "Ticker": "IBP", "TickerType": "ST", "Name": "David J. Taylor",
        "BioGuideID": "T000490", "Filed": "2010-01-01", "Traded": "2009-12-20",
        "Party": "Republican", "Chamber": "Representatives", "Transaction": "Sale",
        "Trade_Size_USD": "1001.0", "excess_return": None,
    },
    {
        "Ticker": "MSFT", "TickerType": "ST", "Name": "Someone Else",
        "BioGuideID": "X000001", "Filed": "2020-05-01", "Traded": "2020-04-20",
        "Party": "Democratic", "Chamber": "Senate", "Transaction": "Purchase",
        "Trade_Size_USD": "5001.0", "excess_return": None,
    },
]


def test_parse_bulk_tickers_uses_filed_date_not_traded_date():
    tickers = quiver.parse_bulk_tickers(BULK_ROWS, date(2014, 1, 1), date(2025, 12, 31))
    # IBP's in-period row (Filed 2026 is outside this window too -- picked
    # deliberately to prove the filter is real, not a no-op) and its
    # out-of-period row are both excluded; only MSFT (Filed 2020) survives.
    assert tickers == ["MSFT"]


def test_parse_bulk_tickers_deduplicates_repeated_tickers():
    rows = [
        {"Ticker": "AAPL", "Filed": "2020-01-01"},
        {"Ticker": "AAPL", "Filed": "2021-06-01"},
    ]
    tickers = quiver.parse_bulk_tickers(rows, date(2014, 1, 1), date(2025, 12, 31))
    assert tickers == ["AAPL"]


def test_parse_bulk_tickers_on_empty_list_returns_empty():
    assert quiver.parse_bulk_tickers([], date(2014, 1, 1), date(2025, 12, 31)) == []


def test_parse_bulk_tickers_does_not_reuse_the_per_ticker_parser_field_names():
    # Regression: parse_congress_trades' _RENAME map has no entry for
    # "Filed" -- confirmed live that reusing it on a bulk-shaped row
    # silently produces an all-null report_date and therefore zero
    # tickers, rather than raising. parse_bulk_tickers must read "Filed"
    # directly and actually find the ticker.
    rows = [{"Ticker": "ZZZ", "Filed": "2020-01-01"}]
    assert quiver.parse_bulk_tickers(rows, date(2014, 1, 1), date(2025, 12, 31)) == ["ZZZ"]


def test_discover_ticker_universe_without_token_is_a_clear_error(monkeypatch):
    monkeypatch.setattr(quiver, "QUIVER_API_TOKEN", "")
    with pytest.raises(quiver.MissingTokenError, match="quiverquant.com"):
        quiver.discover_ticker_universe(date(2014, 1, 1), date(2025, 12, 31))


def test_discover_ticker_universe_calls_bulk_endpoint_and_filters(monkeypatch):
    monkeypatch.setattr(quiver, "QUIVER_API_TOKEN", "tok")
    captured = {}

    def fake_get_json(url, headers=None, **kwargs):
        captured["url"] = url
        return BULK_ROWS

    monkeypatch.setattr(quiver, "get_json", fake_get_json)
    tickers = quiver.discover_ticker_universe(date(2014, 1, 1), date(2025, 12, 31))
    assert captured["url"] == quiver.BULK_CONGRESS_TRADES_URL
    assert tickers == ["MSFT"]


def test_ingest_congress_trades_without_token_is_a_clear_error(monkeypatch):
    monkeypatch.setattr(quiver, "QUIVER_API_TOKEN", "")
    with pytest.raises(quiver.MissingTokenError, match="quiverquant.com"):
        quiver.ingest_congress_trades("MSFT")


def test_ingest_congress_trades_writes_report_date_and_transaction_date_both(monkeypatch):
    """Both dates must survive ingestion -- the whole PIT discipline this
    module documents depends on report_date being queryable downstream."""
    monkeypatch.setattr(quiver, "QUIVER_API_TOKEN", "tok")
    monkeypatch.setattr(quiver, "get_json", lambda *a, **k: ROWS)
    n = quiver.ingest_congress_trades("MSFT")
    assert n == 1
    from congressional_sales import storage
    got = storage.read("congress_trades")
    assert got["report_date"][0] == date(2026, 8, 6)
    assert got["transaction_date"][0] == date(2026, 7, 24)
