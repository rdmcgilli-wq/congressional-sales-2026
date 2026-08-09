"""Ken French data library: Fama-French 3 factors + momentum.

Source: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
Both files ship as a zip containing one CSV with a multi-line text header
and a text footer -- find the data block by locating the first line
starting with an 8-digit date and stopping at the first non-digit-prefixed
line after that.
"""

from __future__ import annotations

import io
import re
import zipfile

import polars as pl

from .. import storage
from ..http import get_bytes

FF3_ZIP_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip"
MOM_ZIP_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip"

_DATE_LINE = re.compile(r"^\d{8},")


def _data_block(text: str) -> str:
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if _DATE_LINE.match(ln)), None)
    if start is None:
        return ""
    end = start
    while end < len(lines) and _DATE_LINE.match(lines[end]):
        end += 1
    return "\n".join(lines[start:end])


def _fetch_zip_member_text(url: str) -> str:
    raw = get_bytes(url)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = zf.namelist()[0]
        return zf.read(name).decode("latin-1")


def parse_ff3_csv(text: str) -> pl.DataFrame:
    block = _data_block(text)
    if not block:
        return pl.DataFrame(schema={"date": pl.Date, "mkt_rf": pl.Float64, "smb": pl.Float64, "hml": pl.Float64, "rf": pl.Float64})
    rows = []
    for line in block.splitlines():
        parts = [p.strip() for p in line.split(",")]
        rows.append({"date": parts[0], "mkt_rf": parts[1], "smb": parts[2], "hml": parts[3], "rf": parts[4]})
    df = pl.DataFrame(rows)
    return df.with_columns(
        pl.col("date").str.to_date("%Y%m%d"),
        (pl.col("mkt_rf").cast(pl.Float64) / 100.0).alias("mkt_rf"),
        (pl.col("smb").cast(pl.Float64) / 100.0).alias("smb"),
        (pl.col("hml").cast(pl.Float64) / 100.0).alias("hml"),
        (pl.col("rf").cast(pl.Float64) / 100.0).alias("rf"),
    )


def parse_momentum_csv(text: str) -> pl.DataFrame:
    block = _data_block(text)
    if not block:
        return pl.DataFrame(schema={"date": pl.Date, "mom": pl.Float64})
    rows = []
    for line in block.splitlines():
        parts = [p.strip() for p in line.split(",")]
        rows.append({"date": parts[0], "mom": parts[1]})
    df = pl.DataFrame(rows)
    return df.with_columns(
        pl.col("date").str.to_date("%Y%m%d"),
        (pl.col("mom").cast(pl.Float64) / 100.0).alias("mom"),
    )


def ingest_factors() -> int:
    ff3 = parse_ff3_csv(_fetch_zip_member_text(FF3_ZIP_URL))
    mom = parse_momentum_csv(_fetch_zip_member_text(MOM_ZIP_URL))
    joined = ff3.join(mom, on="date", how="inner")
    if joined.is_empty():
        return 0
    storage.write("ff_factors", joined, key_cols=["date"])
    return joined.height
