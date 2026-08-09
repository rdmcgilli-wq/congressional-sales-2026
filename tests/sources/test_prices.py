from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from congressional_sales.sources import prices


def test_fetch_tiingo_parses_and_keeps_adjusted_close(monkeypatch):
    monkeypatch.setenv("TIINGO_API_TOKEN", "tok")
    rows = [
        {
            "date": "2024-01-02T00:00:00.000Z",
            "open": 10.0, "high": 11.0, "low": 9.5, "close": 10.5,
            "volume": 1000, "adjClose": 10.4,
        },
        {
            "date": "2024-01-03T00:00:00.000Z",
            "open": 10.5, "high": 12.0, "low": 10.4, "close": 11.8,
            "volume": 1500, "adjClose": 11.7,
        },
    ]
    monkeypatch.setattr(prices, "get_json", lambda *a, **k: rows)
    df = prices.fetch_tiingo("AAPL")
    assert df.height == 2
    assert df["date"][0] == date(2024, 1, 2)
    assert df["close"][0] == 10.5
    assert df["close_adj"][0] == 10.4
    assert df["ticker"][0] == "AAPL"


def test_fetch_tiingo_without_token_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("TIINGO_API_TOKEN", raising=False)
    with pytest.raises(prices.ProviderUnavailable, match="tiingo.com"):
        prices.fetch_tiingo("AAPL")


def test_ingest_prices_writes_to_warehouse(monkeypatch):
    monkeypatch.setenv("TIINGO_API_TOKEN", "tok")
    rows = [
        {"date": "2024-01-02T00:00:00.000Z", "open": 10.0, "high": 11.0, "low": 9.5, "close": 10.5, "volume": 1000, "adjClose": 10.4},
    ]
    monkeypatch.setattr(prices, "get_json", lambda *a, **k: rows)
    n = prices.ingest_prices("AAPL")
    assert n == 1
    from congressional_sales import storage
    got = storage.read("equity_eod")
    assert got.height == 1
    assert got["ticker"][0] == "AAPL"
