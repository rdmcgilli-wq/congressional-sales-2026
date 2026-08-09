"""Idempotent parquet storage with a DuckDB view over every table.

write() upserts on key_cols: rows sharing a key are replaced by the newest
write, so re-ingesting an overlapping window is always safe. Mirrors the
marketlab platform's storage.py exactly (that design was reviewed
extensively during this session's earlier platform build); reimplemented
standalone here since this repo must not import the private Investment repo.
"""

from __future__ import annotations

import re

import duckdb
import polars as pl

from .config import paths


def _safe_partition(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


def write(table: str, df: pl.DataFrame, key_cols: list[str], partition: str | None = None) -> None:
    if df.is_empty():
        raise ValueError(f"write({table!r}): refusing to write an empty frame")
    missing = [c for c in key_cols if c not in df.columns]
    if missing:
        raise ValueError(f"write({table!r}): key_cols not in frame: {missing}")

    p = paths()
    p.ensure()
    table_dir = p.table(table) if hasattr(p, "table") else p.parquet / table
    table_dir.mkdir(parents=True, exist_ok=True)
    part_name = _safe_partition(partition) if partition else "_all"
    part_path = table_dir / f"{part_name}.parquet"

    if part_path.exists():
        existing = pl.read_parquet(part_path)
        combined = pl.concat([existing, df], how="diagonal_relaxed")
        merged = combined.unique(subset=key_cols, keep="last", maintain_order=False)
    else:
        merged = df.unique(subset=key_cols, keep="last", maintain_order=False)

    merged.write_parquet(part_path)


def read(table: str) -> pl.DataFrame:
    p = paths()
    table_dir = p.parquet / table
    if not table_dir.exists():
        return pl.DataFrame()
    files = sorted(table_dir.glob("*.parquet"))
    if not files:
        return pl.DataFrame()
    return pl.concat([pl.read_parquet(f) for f in files], how="diagonal_relaxed")


def tables() -> list[str]:
    p = paths()
    if not p.parquet.exists():
        return []
    return sorted(d.name for d in p.parquet.iterdir() if d.is_dir())


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(paths().db))
    for t in tables():
        table_dir = paths().parquet / t
        con.execute(f"CREATE OR REPLACE VIEW {t} AS SELECT * FROM read_parquet('{table_dir}/*.parquet')")
    return con
