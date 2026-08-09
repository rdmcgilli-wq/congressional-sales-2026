from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def warehouse(tmp_path, monkeypatch):
    """Redirect the whole warehouse at a tmp dir so tests never touch real data."""
    monkeypatch.setenv("CONGRESS_SALES_HOME", str(tmp_path / "wh"))
    from congressional_sales.config import paths

    paths().ensure()
    return tmp_path / "wh"
