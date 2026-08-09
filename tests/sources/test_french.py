from __future__ import annotations

from datetime import date

from congressional_sales.sources import french

FF3_FIXTURE = """This file was created by CMPT_ME_BEME_RETS using the 202412 CRSP database.

,Mkt-RF,SMB,HML,RF
20240102,1.02,-0.15,0.30,0.01
20240103,-0.55,0.10,-0.05,0.01

Copyright 2024 Fama and French
"""

MOM_FIXTURE = """This file was created by CMPT_ME_RESID_RETS using the 202412 CRSP database.

,Mom
20240102,0.44
20240103,-0.21

Copyright 2024 Fama and French
"""


def test_parse_ff3_csv_converts_percent_to_decimal():
    df = french.parse_ff3_csv(FF3_FIXTURE)
    assert df.height == 2
    assert df["date"][0] == date(2024, 1, 2)
    assert df["mkt_rf"][0] == 0.0102
    assert df["smb"][0] == -0.0015
    assert df["hml"][0] == 0.0030
    assert df["rf"][0] == 0.0001


def test_parse_momentum_csv_converts_percent_to_decimal():
    df = french.parse_momentum_csv(MOM_FIXTURE)
    assert df.height == 2
    assert df["date"][0] == date(2024, 1, 2)
    assert df["mom"][0] == 0.0044


def test_ingest_factors_joins_ff3_and_momentum(monkeypatch):
    def fake_get_bytes(url, *a, **k):
        return (FF3_FIXTURE if "F-F_Research_Data_Factors" in url else MOM_FIXTURE).encode()

    import zipfile
    import io

    def fake_fetch_zip_member(url):
        # ingest_factors is expected to call a helper that unzips a single
        # CSV member from the downloaded bytes -- for the test, monkeypatch
        # that helper directly rather than constructing a real zip.
        return FF3_FIXTURE if "F-F_Research_Data_Factors" in url else MOM_FIXTURE

    monkeypatch.setattr(french, "_fetch_zip_member_text", fake_fetch_zip_member)
    n = french.ingest_factors()
    assert n == 2
    from congressional_sales import storage
    got = storage.read("ff_factors").sort("date")
    assert got["date"].to_list() == [date(2024, 1, 2), date(2024, 1, 3)]
    assert got["mom"][0] == 0.0044
    assert got["mkt_rf"][0] == 0.0102
