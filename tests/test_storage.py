from __future__ import annotations

import polars as pl
import pytest

from congressional_sales import storage


def test_write_then_read_roundtrip():
    df = pl.DataFrame({"ticker": ["AAPL", "MSFT"], "value": [1.0, 2.0]})
    storage.write("t1", df, key_cols=["ticker"])
    got = storage.read("t1")
    assert got.sort("ticker").to_dicts() == df.sort("ticker").to_dicts()


def test_reingest_is_idempotent():
    df = pl.DataFrame({"ticker": ["AAPL"], "value": [1.0]})
    storage.write("t2", df, key_cols=["ticker"])
    storage.write("t2", df, key_cols=["ticker"])
    assert storage.read("t2").height == 1


def test_later_write_wins_on_key_collision():
    storage.write("t3", pl.DataFrame({"ticker": ["AAPL"], "value": [1.0]}), key_cols=["ticker"])
    storage.write("t3", pl.DataFrame({"ticker": ["AAPL"], "value": [2.0]}), key_cols=["ticker"])
    got = storage.read("t3")
    assert got.height == 1
    assert got["value"][0] == 2.0


def test_empty_frame_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        storage.write("t4", pl.DataFrame(schema={"ticker": pl.Utf8}), key_cols=["ticker"])


def test_read_missing_table_is_empty_not_error():
    assert storage.read("nonexistent").is_empty()
