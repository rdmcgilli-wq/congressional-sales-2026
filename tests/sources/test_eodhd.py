from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from congressional_sales.sources import eodhd

PRICE_SCHEMA = {
    "ticker": pl.Utf8, "date": pl.Date, "open": pl.Float64, "high": pl.Float64,
    "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64, "close_adj": pl.Float64,
}


def _existing(ticker: str, dates: list[date]) -> pl.DataFrame:
    n = len(dates)
    return pl.DataFrame(
        {
            "ticker": [ticker] * n, "date": dates, "open": [1.0] * n, "high": [1.0] * n,
            "low": [1.0] * n, "close": [1.0] * n, "volume": [1.0] * n, "close_adj": [1.0] * n,
        },
        schema=PRICE_SCHEMA,
    )


def test_fetch_eodhd_parses_and_keeps_adjusted_close(monkeypatch):
    monkeypatch.setenv("EODHD_API_TOKEN", "tok")
    rows = [
        {"date": "2023-09-01", "open": 0.21, "high": 0.27, "low": 0.21, "close": 0.26, "adjusted_close": 0.26, "volume": 13946100},
    ]
    monkeypatch.setattr(eodhd, "get_json", lambda *a, **k: rows)
    df = eodhd.fetch_eodhd("BBBYQ.US", canonical_ticker="BBBY")
    assert df.height == 1
    assert df["ticker"][0] == "BBBY"  # canonical, not the raw "BBBYQ" symbol string
    assert df["date"][0] == date(2023, 9, 1)
    assert df["close_adj"][0] == 0.26


def test_fetch_eodhd_without_token_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("EODHD_API_TOKEN", raising=False)
    with pytest.raises(eodhd.ProviderUnavailable, match="eodhd.com"):
        eodhd.fetch_eodhd("AAPL.US", canonical_ticker="AAPL")


def test_fetch_eodhd_returns_empty_frame_for_404_style_response(monkeypatch):
    # EODHD returns a plain error body (not a list) for "Ticker Not Found" --
    # must come back as a typed-empty frame, not raise or return garbage.
    monkeypatch.setenv("EODHD_API_TOKEN", "tok")
    monkeypatch.setattr(eodhd, "get_json", lambda *a, **k: {"error": "Ticker Not Found."})
    df = eodhd.fetch_eodhd("NOSUCHTICKERQ.US", canonical_ticker="NOSUCHTICKER")
    assert df.is_empty()
    assert df.schema["date"] == pl.Date


def test_find_stale_tickers_flags_tickers_past_the_gap():
    prices = pl.concat(
        [
            _existing("FRESH", [date(2024, 5, 15)]),  # 17 days before as_of -- within the 90-day gap
            _existing("STALE", [date(2023, 1, 1)]),  # far more than 90 days before as_of
        ]
    )
    stale = eodhd.find_stale_tickers(prices, as_of=date(2024, 6, 1), gap_days=90)
    assert stale == ["STALE"]


def test_find_stale_tickers_empty_prices_returns_empty_list():
    assert eodhd.find_stale_tickers(pl.DataFrame(schema=PRICE_SCHEMA), as_of=date(2024, 1, 1)) == []


def test_patch_delisted_ticker_prefers_q_suffix_when_it_has_data(monkeypatch):
    # The core safety behavior: even if the bare ticker ALSO has data
    # available (e.g. a reused symbol trading normally), the Q-suffix
    # variant -- which can only belong to the same entity that filed
    # Chapter 11 -- must win.
    monkeypatch.setenv("EODHD_API_TOKEN", "tok")

    def fake_get_json(url, params=None, **kwargs):
        if "BBBYQ.US" in url:
            return [{"date": "2023-09-01", "open": 0.26, "high": 0.27, "low": 0.21, "close": 0.26, "adjusted_close": 0.26, "volume": 100}]
        if "BBBY.US" in url:
            return [{"date": "2023-08-15", "open": 22.0, "high": 22.5, "low": 21.5, "close": 22.0, "adjusted_close": 22.0, "volume": 100}]
        return []

    monkeypatch.setattr(eodhd, "get_json", fake_get_json)
    existing = _existing("BBBY", [date(2023, 4, 20)])
    n = eodhd.patch_delisted_ticker("BBBY", existing)
    assert n == 1

    from congressional_sales import storage

    got = storage.read("equity_eod").filter(pl.col("ticker") == "BBBY")
    patched = got.filter(pl.col("date") == date(2023, 9, 1))
    assert patched.height == 1
    assert patched["close_adj"][0] == pytest.approx(0.26)  # the Q-suffix (bankrupt) price, not the bare-ticker one


def test_patch_delisted_ticker_uses_bare_ticker_when_it_resumes_within_the_window(monkeypatch):
    monkeypatch.setenv("EODHD_API_TOKEN", "tok")

    def fake_get_json(url, params=None, **kwargs):
        if "XYZQ.US" in url:
            return []
        if "XYZ.US" in url:
            # resumes 10 days after the last known Tiingo date -- well
            # within BARE_TICKER_RESUME_WINDOW_DAYS
            return [{"date": "2023-05-01", "open": 5.0, "high": 5.5, "low": 4.5, "close": 5.0, "adjusted_close": 5.0, "volume": 100}]
        return []

    monkeypatch.setattr(eodhd, "get_json", fake_get_json)
    existing = _existing("XYZ", [date(2023, 4, 21)])
    n = eodhd.patch_delisted_ticker("XYZ", existing)
    assert n == 1


def test_patch_delisted_ticker_ignores_bare_ticker_data_resuming_far_later(monkeypatch):
    # THE regression test for the failure mode this module exists to
    # prevent: BBBY delisted in ~May 2023, and the bare "BBBY" symbol was
    # reused by an unrelated company (the rebranded Overstock.com) later
    # that year. A bare-ticker resumption months after the last known date
    # must NOT be patched in as if it were the same security.
    monkeypatch.setenv("EODHD_API_TOKEN", "tok")

    def fake_get_json(url, params=None, **kwargs):
        if "BBBYQ.US" in url:
            return []  # no Chapter 11 data available under this variant either
        if "BBBY.US" in url:
            # resumes ~3 months later -- a plausible unrelated reissue, not a lag
            return [{"date": "2023-08-15", "open": 22.0, "high": 22.5, "low": 21.5, "close": 22.0, "adjusted_close": 22.0, "volume": 100}]
        return []

    monkeypatch.setattr(eodhd, "get_json", fake_get_json)
    existing = _existing("BBBY", [date(2023, 4, 20)])
    n = eodhd.patch_delisted_ticker("BBBY", existing)
    # n == 0 already proves nothing was written -- patch_delisted_ticker
    # only calls storage.write on a branch that returns a nonzero count.
    assert n == 0


def test_patch_delisted_ticker_returns_zero_when_neither_variant_has_data(monkeypatch):
    monkeypatch.setenv("EODHD_API_TOKEN", "tok")
    monkeypatch.setattr(eodhd, "get_json", lambda *a, **k: [])
    existing = _existing("GHOST", [date(2023, 1, 1)])
    assert eodhd.patch_delisted_ticker("GHOST", existing) == 0


def test_patch_all_stale_tickers_only_touches_stale_ones(monkeypatch):
    from congressional_sales import storage

    monkeypatch.setenv("EODHD_API_TOKEN", "tok")
    storage.write(
        "equity_eod",
        pl.concat([_existing("FRESH", [date(2024, 5, 15)]), _existing("STALEQ", [date(2023, 1, 1)])]),
        key_cols=["ticker", "date"],
    )

    calls = []

    def fake_get_json(url, params=None, **kwargs):
        calls.append(url)
        if "STALEQQ.US" in url:
            return [{"date": "2023-02-01", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "adjusted_close": 1.0, "volume": 1.0}]
        return []

    monkeypatch.setattr(eodhd, "get_json", fake_get_json)
    result = eodhd.patch_all_stale_tickers(as_of=date(2024, 6, 1), gap_days=90)

    assert set(result.keys()) == {"STALEQ"}  # FRESH is within the gap and never touched
    assert result["STALEQ"] == 1
    assert not any("FRESH" in c for c in calls)
