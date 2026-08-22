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


def test_fetch_eodhd_returns_empty_frame_for_200_with_error_body(monkeypatch):
    # One EODHD "not found" shape: a 200 status with a plain error body
    # (not a list) -- must come back as a typed-empty frame, not raise.
    monkeypatch.setenv("EODHD_API_TOKEN", "tok")
    monkeypatch.setattr(eodhd, "get_json", lambda *a, **k: {"error": "Ticker Not Found."})
    df = eodhd.fetch_eodhd("NOSUCHTICKERQ.US", canonical_ticker="NOSUCHTICKER")
    assert df.is_empty()
    assert df.schema["date"] == pl.Date


def test_fetch_eodhd_returns_empty_frame_for_a_real_404_status(monkeypatch):
    # THE regression test for the real crash: EODHD's OTHER "not found"
    # shape is an actual HTTP 404 status, which reaches get_json as a
    # raised httpx.HTTPStatusError, not a parseable 200 body. Confirmed
    # live the hard way -- the first full-universe ingestion run crashed
    # here outright on a malformed "ticker" from the bulk feed's own
    # ~4% garbage rate (a bond CUSIP with a leading space). Must come back
    # as the same typed-empty frame the 200-with-error-body case produces,
    # not propagate.
    import httpx

    monkeypatch.setenv("EODHD_API_TOKEN", "tok")

    def raise_404(*a, **k):
        request = httpx.Request("GET", "https://eodhd.com/api/eod/BADQ.US")
        response = httpx.Response(404, request=request)
        raise httpx.HTTPStatusError("404 Not Found", request=request, response=response)

    monkeypatch.setattr(eodhd, "get_json", raise_404)
    df = eodhd.fetch_eodhd("BADQ.US", canonical_ticker="BAD")
    assert df.is_empty()
    assert df.schema["date"] == pl.Date


def test_fetch_eodhd_reraises_non_404_http_errors(monkeypatch):
    # A 404 specifically means "no such ticker" and is swallowed; any
    # other status is a genuine infrastructure problem (e.g. a persistent
    # 5xx that survived http.py's own retries) and must NOT be silently
    # treated as "no data" -- that would hide a real outage as a clean
    # empty result.
    import httpx

    monkeypatch.setenv("EODHD_API_TOKEN", "tok")

    def raise_500(*a, **k):
        request = httpx.Request("GET", "https://eodhd.com/api/eod/AAPL.US")
        response = httpx.Response(500, request=request)
        raise httpx.HTTPStatusError("500 Server Error", request=request, response=response)

    monkeypatch.setattr(eodhd, "get_json", raise_500)
    with pytest.raises(httpx.HTTPStatusError):
        eodhd.fetch_eodhd("AAPL.US", canonical_ticker="AAPL")


def test_find_stale_tickers_flags_tickers_past_the_gap():
    prices = pl.concat(
        [
            _existing("FRESH", [date(2024, 5, 15)]),  # 17 days before as_of -- within the 90-day gap
            _existing("STALE", [date(2023, 1, 1)]),  # far more than 90 days before as_of
        ]
    )
    stale = eodhd.find_stale_tickers(["FRESH", "STALE"], prices, as_of=date(2024, 6, 1), gap_days=90)
    assert stale == ["STALE"]


def test_find_stale_tickers_flags_tickers_with_zero_price_rows():
    # Regression: a ticker Tiingo never covered at all (confirmed live --
    # BBBY returns zero rows, not a partial history) has no row in
    # `prices` to group on, so it must be caught via the universe list
    # itself, not inferred from prices' own contents.
    prices = _existing("HASDATA", [date(2024, 5, 15)])
    stale = eodhd.find_stale_tickers(["HASDATA", "NODATA"], prices, as_of=date(2024, 6, 1), gap_days=90)
    assert stale == ["NODATA"]


def test_find_stale_tickers_empty_universe_returns_empty_list():
    assert eodhd.find_stale_tickers([], pl.DataFrame(schema=PRICE_SCHEMA), as_of=date(2024, 1, 1)) == []


def test_find_stale_tickers_empty_prices_flags_the_whole_universe():
    assert eodhd.find_stale_tickers(["A", "B"], pl.DataFrame(schema=PRICE_SCHEMA), as_of=date(2024, 1, 1)) == ["A", "B"]


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


def test_patch_delisted_ticker_handles_a_genuinely_columnless_existing_prices_frame(monkeypatch):
    # storage.read returns a bare pl.DataFrame() (no columns at all, not
    # just zero rows) for a table that has never been written -- filtering
    # that on pl.col("ticker") raises ColumnNotFoundError rather than
    # behaving like an empty result. Never happens in the real pipeline
    # (Tiingo ingestion always populates equity_eod first), but must not
    # crash if called before any ingestion at all.
    monkeypatch.setenv("EODHD_API_TOKEN", "tok")
    monkeypatch.setattr(
        eodhd, "get_json",
        lambda *a, **k: [{"date": "2023-09-01", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "adjusted_close": 1.0, "volume": 1.0}],
    )
    n = eodhd.patch_delisted_ticker("NEW", pl.DataFrame())
    assert n == 1


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
    # NODATA is in the universe but has never been written to equity_eod at
    # all -- proves the zero-coverage case (find_stale_tickers' own
    # regression above) actually reaches this orchestration function too.
    result = eodhd.patch_all_stale_tickers(
        universe=["FRESH", "STALEQ", "NODATA"], as_of=date(2024, 6, 1), gap_days=90
    )

    assert set(result.keys()) == {"STALEQ", "NODATA"}  # FRESH is within the gap and never touched
    assert result["STALEQ"] == 1
    assert result["NODATA"] == 0
    assert not any("FRESH" in c for c in calls)


def test_patch_all_stale_tickers_does_not_abort_the_run_on_one_ticker_raising(monkeypatch):
    # THE regression test for the real crash: the first full-universe
    # ingestion run's delisting-patch step died outright on the first
    # malformed ticker it tried (an unhandled exception from
    # patch_delisted_ticker), leaving every legitimate patch behind it in
    # the loop unprocessed. A single bad ticker must be logged as an
    # unresolved (0) result and the loop must continue to the rest.
    from congressional_sales import storage

    monkeypatch.setenv("EODHD_API_TOKEN", "tok")
    # Seed equity_eod with a properly-typed (if unrelated) row so
    # existing_prices has real columns -- isolates THIS test's failure
    # mode (get_json raising) from the separate columnless-frame case its
    # own dedicated test above covers.
    storage.write("equity_eod", _existing("UNRELATED", [date(2020, 1, 1)]), key_cols=["ticker", "date"])

    def fake_get_json(url, params=None, **kwargs):
        if "BADQ.US" in url:
            raise RuntimeError("simulated unexpected failure")
        if "GOODQ.US" in url:
            return [{"date": "2023-02-01", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "adjusted_close": 1.0, "volume": 1.0}]
        return []

    monkeypatch.setattr(eodhd, "get_json", fake_get_json)
    # Sorted order (find_stale_tickers' own contract) puts "BAD" before
    # "GOOD" alphabetically, so this also proves the loop keeps going
    # PAST a failure, not just that a failure is caught in isolation.
    result = eodhd.patch_all_stale_tickers(universe=["BAD", "GOOD"], as_of=date(2024, 6, 1), gap_days=90)

    assert result["BAD"] == 0
    assert result["GOOD"] == 1
