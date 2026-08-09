from __future__ import annotations

from congressional_sales.sources import sic


def test_resolve_cik_matches_on_uppercase_ticker(monkeypatch):
    payload = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    monkeypatch.setattr(sic, "get_json", lambda *a, **k: payload)
    assert sic.resolve_cik("aapl") == 320193


def test_resolve_cik_unknown_ticker_returns_none(monkeypatch):
    monkeypatch.setattr(sic, "get_json", lambda *a, **k: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "x"}})
    assert sic.resolve_cik("ZZZZZZ") is None


def test_fetch_sic_reads_code_and_description(monkeypatch):
    monkeypatch.setattr(sic, "get_json", lambda *a, **k: {"sic": "3674", "sicDescription": "Semiconductors & Related Devices"})
    assert sic.fetch_sic(320193) == ("3674", "Semiconductors & Related Devices")


def test_ingest_sic_codes_writes_table(monkeypatch):
    tickers_payload = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    sic_payload = {"sic": "3674", "sicDescription": "Semiconductors & Related Devices"}

    def fake_get_json(url, *a, **k):
        return tickers_payload if "company_tickers" in url else sic_payload

    monkeypatch.setattr(sic, "get_json", fake_get_json)
    n = sic.ingest_sic_codes(["AAPL"])
    assert n == 1
    from congressional_sales import storage
    got = storage.read("sic_codes")
    assert got["sic_code"][0] == "3674"
