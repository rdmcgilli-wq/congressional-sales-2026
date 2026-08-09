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
