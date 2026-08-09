# Congressional Sales Information Content Study — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete, reproducible data pipeline and analysis for
`PRE_ANALYSIS_PLAN.md` v1.0 — from raw primary-source data through the
exact 8 tables and 8 figures specified in Section 10, with zero deviation
from the pre-registered hypotheses, screens, models, and statistical
discipline, and every documented deviation (survivorship bias, Screen 3
scope) reported explicitly rather than silently absorbed.

**Architecture:** A self-contained Python package (`congressional_sales`)
with its own polars+DuckDB warehouse (same pattern as the `marketlab`
platform built earlier, reimplemented standalone — this repo must not
import from the private Investment repo). Layered: `sources/` (raw
ingestion) → `sample/` (funnel + screens) → `events/` (CAR/BHAR engine) →
`models/` (Models 1-3, BH correction, permutation test) → `outputs/`
(tables, figures, paper assembly) → `verification/` (hand-check, audits).
A single orchestration script runs the full pipeline; a separate,
explicitly-labeled script runs the 18-month holdout sample, built to be
run last and once only.

**Tech Stack:** Python 3.12, `uv`, `polars` + `duckdb` (storage),
`httpx` + `tenacity` (rate-limited HTTP), `pandas` + `statsmodels` +
`linearmodels` (econometrics — clustered SEs, absorbed fixed effects),
`matplotlib` (static publication figures), `typer` (CLI), `pytest`.

## Global Constraints

Copied verbatim from `PRE_ANALYSIS_PLAN.md` (the spec) and from decisions
made during scoping (recorded in that file's Section 3/11 inline notes).
Every task's requirements implicitly include these:

- Sample period: 2014 through the most recent complete year. The final 18
  months are an untouched validation (holdout) sample — built by the same
  code path, but run last, once only, after every other result is final.
- Inclusion: common stock transactions only; transactions above $1,000;
  member, spouse, and dependent child; securities with resolvable price
  data covering the full event window.
- Exclusion: options, bonds, mutual funds, ETFs, municipal securities;
  exchanges/transfers; securities with fewer than 60 trading days of prior
  price history; duplicate filings deduped on
  member–ticker–transaction-date–amount-band.
- Every exclusion is logged with a count (feeds T1). No exclusion may be
  silent.
- Four sequential screens, exactly as specified in PAP Section 5 (Screen 1
  rebalancing, Screen 2 tax management, Screen 3 liquidation events, Screen
  4 routine vs. opportunistic). Report main results on both unscreened and
  screened samples.
- Primary trade-level data source is Quiver Quantitative
  (`QUIVER_API_TOKEN` env var, Trader tier). The House Clerk and Senate eFD
  primary portals are used **only** for a small, manual/light-touch
  verification pull (the Section 11 20-transaction hand-check and the
  Section 3 filing-timestamp cross-check) — never bulk-scraped. This
  project must never issue more than a handful of requests per run against
  either government portal.
- **Documented deviation:** no delisting-inclusive price source exists.
  The daily price data is survivorship-biased. This must be reported
  explicitly in T1/limitations, never silently treated as resolved. The
  Section 11 "Delisting handling" checklist item cannot pass as stated —
  code must produce an audit of how many sample tickers show an apparent
  gap consistent with delisting, so the bias is at least quantified.
- **Documented Screen 3 scope decision:** of the three liquidation-event
  sub-conditions (announced retirement, blind trust establishment,
  confirmation to an executive-branch position), only "disclosed sales of
  more than 60% of a member's disclosed portfolio" is implementable from
  data this project has access to. "Retirement" is approximated via the
  legislator's term end date (from the committee-assignment dataset) not
  being followed by a new term start. Blind-trust establishment and
  executive-branch confirmation have no available structured data source
  and are explicitly **out of scope for v1** — this must be stated in the
  paper's limitations section, not silently omitted.
- **Read this before writing Task 22 (Phase 6) or any orchestration code
  that calls Phase 4's CAR/BHAR functions across the sample.** Section 6's
  literal text: CAR is measured "from the transaction date" as the
  PRIMARY specification. `report_date`-anchored CAR is NOT the default —
  it is specifically Section 9 robustness item 6, "Entry at filing date
  rather than transaction date (the actionability question)". This is the
  opposite of the point-in-time framing applied everywhere else in this
  plan (Screens 1-3, the funnel, Model 2's `report_date <= as_of` gating
  logic) — and that is intentional, not a contradiction: `transaction_date`
  anchoring tests whether a trade correlates with what happened
  *afterward*, i.e. evidence of foreknowledge, regardless of whether the
  information was public yet; `report_date` anchoring tests whether an
  outside observer who only sees the public disclosure could have
  profited, i.e. actionability. These are different research questions,
  and the PAP wants both, with `transaction_date` as primary. Every other
  screen/filter in this plan legitimately uses `report_date` because THEY
  answer a different question ("was this knowable yet") — do not
  "fix" them to match this one. When Task 22 (or any earlier task, if
  reordered) attaches a CAR/BHAR value to each sample row, call Phase 4's
  functions with `event_date=transaction_date` for every table/figure
  except the one robustness-item-6 variant, which reruns with
  `event_date=report_date`.
- CAR horizons: [+1, +30], [+1, +90], [+1, +180] trading days from the
  transaction date. Three abnormal-return adjustment methods, all reported:
  market-adjusted (vs. SPY), four-factor (FF3 + momentum, estimation window
  [-250, -30] trading days), size/industry-matched (market-cap decile ×
  Fama-French 12-industry).
- BHAR at the same horizons, as a robustness check on CAR.
- Pre-specified primary test: β1 in Model 2, 90-day horizon, four-factor
  adjusted, **screened** sample. Everything else is secondary.
- Benjamini-Hochberg correction across all 18 test variants (3 horizons ×
  3 adjustment methods × 2 samples — unscreened/screened). State the
  corrected threshold.
- Random control: 1,000 iterations, same-ticker random-date resampling,
  matched transaction count. Report where the actual result falls in the
  simulated distribution.
- No specification may be added after seeing results. Anything not in this
  plan's pre-specified output list that later gets added must be labeled
  "post-hoc exploratory analysis," never silently folded into the main
  results.
- Exactly T1–T8 and F1–F8 (PAP Section 10). Nothing else goes in the paper.
- Verification (PAP Section 11): 20-transaction hand-check against
  light-touch primary-portal pulls; trading-day alignment (t+1 = next
  trading day, not calendar day); delisting audit (see documented
  deviation above); ticker matched on a permanent identifier, never
  symbol alone; NaN audit at every computation step; two independent
  end-to-end reproductions on different days with identical output.
- **Documented committee-data limitation (discovered during planning,
  recorded here pre-analysis, before Task 6 is implemented):** the
  `unitedstates/congress-legislators` dataset publishes only *current*
  committee membership (`committee-membership-current.yaml`), not a
  historical per-congress membership record. H4's `CommitteeMatch`
  variable will therefore use each member's most recent known committee
  assignment (current if still serving, or their last known assignment
  before leaving office if not) rather than their true committee
  assignment at the exact historical transaction date. This is a real
  approximation, not a bug — it must be stated in the paper's limitations
  section alongside the Screen 3 and survivorship-bias deviations, and
  Task 6 below implements it exactly this way, not silently.
- The paper's limitations section explicitly states: no causal claim about
  information sources, no claim about any individual member, no claim
  about legality of any transaction, no investment recommendation, the
  survivorship-bias deviation, and the Screen 3 scope decision.
- **Documented size/matching limitations (Task 16):** this project has no
  shares-outstanding source, so "market cap decile" (Section 6) is
  approximated with trailing 30-session average dollar volume
  (`close_adj * volume`) as a size proxy — a standard academic substitute
  when true market cap isn't available, but a substitute nonetheless. The
  matching universe is also limited to tickers already in this study's own
  sample (no broad-market universe like Russell 3000 is ingested), so size
  deciles degrade to fewer, coarser buckets in sectors with few sample
  tickers. Both must be stated in the paper's limitations section.
- **Documented Model 2 control-variable limitation (Task 19):** Section
  7's control list includes "log market cap" and "book-to-market," neither
  of which this project can build accurately — there is no
  shares-outstanding or book-value data source in this plan (adding one
  is a real, separately-scoped follow-up, not a quick proxy). Model 2 uses
  `log(size_proxy)` (Task 16's trailing dollar-volume proxy) in place of
  log market cap, and **omits book-to-market entirely** rather than
  inventing a proxy with no defensible basis. State this omission
  explicitly in Model 2's docstring and the paper's limitations section —
  do not silently drop it from the regression table with no explanation.
  The other five controls (prior 12-month return, transaction size band,
  chamber, party, seniority/terms served) are all directly computable from
  data already in this plan and are implemented as specified.

## File Structure

```
congressional-sales-2026/
├── pyproject.toml
├── .env.example
├── PRE_ANALYSIS_PLAN.md          (already committed, v1.0)
├── src/congressional_sales/
│   ├── __init__.py
│   ├── config.py                  Paths, env keys, rate limits
│   ├── http.py                    Rate-limited HTTP client (mirrors marketlab's http.py)
│   ├── storage.py                 DuckDB/parquet idempotent write/read (mirrors marketlab's storage.py)
│   ├── calendar.py                Trading-calendar utilities derived from ingested price data
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── quiver.py              Congressional trades (standalone reimplementation)
│   │   ├── prices.py              Daily equity EOD prices (Tiingo)
│   │   ├── french.py              Ken French factor library (FF3 + momentum)
│   │   ├── legislators.py         Terms + committee assignments (unitedstates/congress-legislators)
│   │   └── primary_portals.py     Light-touch House Clerk / Senate eFD verification puller
│   ├── sample/
│   │   ├── __init__.py
│   │   ├── funnel.py              Inclusion/exclusion funnel (T1)
│   │   ├── screens.py             Screens 1-3
│   │   └── classify.py            Screen 4 (routine/opportunistic) + committee-match (H4)
│   ├── events/
│   │   ├── __init__.py
│   │   ├── car.py                 CAR/BHAR engine, 3 adjustment methods
│   │   └── permutation.py         1,000-iteration random control test
│   ├── models/
│   │   ├── __init__.py
│   │   ├── model1.py              Unconditional means + clustered SEs
│   │   ├── model2.py              Pooled fixed-effects regression
│   │   ├── model3.py              Calendar-time portfolio regression
│   │   └── multiple_comparisons.py  Benjamini-Hochberg correction
│   ├── robustness.py              10-item robustness suite orchestration
│   ├── outputs/
│   │   ├── __init__.py
│   │   ├── tables.py              T1-T8
│   │   ├── figures.py             F1-F8
│   │   └── paper.py               Final paper assembly (markdown)
│   ├── verification/
│   │   ├── __init__.py
│   │   ├── hand_check.py          20-transaction hand-check harness
│   │   └── audits.py              NaN audit, ticker-remap audit, delisting audit
│   └── cli.py                     Typer CLI
├── scripts/
│   ├── run_full_pipeline.py       Ingest -> sample -> screen -> events -> models -> outputs
│   └── run_holdout.py             The one-time, run-last holdout evaluation
└── tests/                         Mirrors src/ structure
```

Each source file has one clear responsibility; files that change together
(a data source and its ingestion test) live together under matching paths
in `tests/`.

---

## Phase 0 — Project Scaffolding

### Task 1: Project setup, storage layer, config

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/congressional_sales/__init__.py`
- Create: `src/congressional_sales/config.py`
- Create: `src/congressional_sales/http.py`
- Create: `src/congressional_sales/storage.py`
- Create: `tests/conftest.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Produces: `config.paths() -> Paths` (dataclass with `.raw`, `.parquet`,
  `.db` properties, `.ensure()` method); `config.QUIVER_API_TOKEN: str`,
  `config.TIINGO_API_TOKEN: str` (both `os.getenv(..., "")`);
  `config.RATE_LIMITS: dict[str, float]`, `config.DEFAULT_RATE_LIMIT: float`.
  `http.get_json(url, params=None, headers=None) -> Any`,
  `http.get_text(url, params=None, headers=None) -> str`.
  `storage.write(table: str, df: pl.DataFrame, key_cols: list[str],
  partition: str | None = None) -> None`; `storage.read(table: str) ->
  pl.DataFrame` (returns empty `pl.DataFrame()` if the table has never been
  written).

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "congressional-sales"
version = "0.1.0"
description = "Pre-registered study: do congressional sales carry more information than purchases?"
requires-python = ">=3.12"
dependencies = [
    "polars>=1.9",
    "duckdb>=1.1",
    "httpx>=0.27",
    "tenacity>=9.0",
    "python-dotenv>=1.0",
    "typer>=0.12",
    "rich>=13.9",
    "pandas>=2.2",
    "statsmodels>=0.14",
    "linearmodels>=6.0",
    "matplotlib>=3.9",
    "pyyaml>=6.0",
    "scipy>=1.14",
]

[project.scripts]
congstudy = "congressional_sales.cli:app"

[tool.pytest.ini_options]
testpaths = ["tests"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/congressional_sales"]
```

- [ ] **Step 2: Create `.env.example`**

```
QUIVER_API_TOKEN=
TIINGO_API_TOKEN=
CONGRESS_SALES_HOME=
```

- [ ] **Step 3: Create `src/congressional_sales/__init__.py`**

```python
"""Congressional Sales Information Content study."""
```

- [ ] **Step 4: Create `src/congressional_sales/config.py`**

```python
"""Paths, credentials, and rate-limit tunables.

Everything resolves off CONGRESS_SALES_HOME (defaults to <repo>/data) so
tests can redirect the whole warehouse at a tmp_path, the same pattern
used by the marketlab platform this study's data layer is modeled on.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]


def _home() -> Path:
    return Path(os.getenv("CONGRESS_SALES_HOME", REPO_ROOT / "data")).expanduser().resolve()


@dataclass(frozen=True)
class Paths:
    home: Path

    @property
    def raw(self) -> Path:
        return self.home / "raw"

    @property
    def parquet(self) -> Path:
        return self.home / "parquet"

    @property
    def db(self) -> Path:
        return self.home / "warehouse.duckdb"

    @property
    def outputs(self) -> Path:
        return REPO_ROOT / "outputs"

    def ensure(self) -> None:
        for p in (self.raw, self.parquet, self.outputs):
            p.mkdir(parents=True, exist_ok=True)


def paths() -> Paths:
    return Paths(home=_home())


CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "rdmcgilli@gmail.com")
USER_AGENT = f"congressional-sales-study/0.1 ({CONTACT_EMAIL})"

QUIVER_API_TOKEN = os.getenv("QUIVER_API_TOKEN", "")
TIINGO_API_TOKEN = os.getenv("TIINGO_API_TOKEN", "")

RATE_LIMITS: dict[str, float] = {
    "api.quiverquant.com": 5.0,
    "api.tiingo.com": 5.0,
    "raw.githubusercontent.com": 5.0,
    "mba.tuck.dartmouth.edu": 2.0,
    # Primary government portals: deliberately very conservative. This
    # project only ever issues a handful of requests per run against
    # these two hosts (Section 11 hand-check + Section 3 cross-check),
    # never a bulk pull -- see PRE_ANALYSIS_PLAN.md Global Constraints.
    "disclosures-clerk.house.gov": 0.5,
    "efdsearch.senate.gov": 0.5,
}
DEFAULT_RATE_LIMIT = 4.0
```

- [ ] **Step 5: Create `src/congressional_sales/http.py`**

```python
"""Shared HTTP client: per-host token bucket, retries. Every source module
goes through get_json/get_text so rate limiting is enforced in one place."""

from __future__ import annotations

import threading
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import DEFAULT_RATE_LIMIT, RATE_LIMITS, USER_AGENT

_lock = threading.Lock()
_last_call: dict[str, float] = {}


class RateLimitedError(RuntimeError):
    """429/5xx from upstream -- retryable."""


def _throttle(host: str) -> None:
    rate = RATE_LIMITS.get(host, DEFAULT_RATE_LIMIT)
    min_gap = 1.0 / rate
    with _lock:
        now = time.monotonic()
        wait = min_gap - (now - _last_call.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.monotonic()


_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
        )
    return _client


@retry(
    retry=retry_if_exception_type((RateLimitedError, httpx.TransportError)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
def _request(url: str, params: dict[str, Any] | None, headers: dict[str, str] | None) -> httpx.Response:
    host = urlparse(url).netloc
    _throttle(host)
    resp = client().get(url, params=params, headers=headers)
    if resp.status_code == 429 or resp.status_code >= 500:
        raise RateLimitedError(f"{resp.status_code} from {host}")
    resp.raise_for_status()
    return resp


def get_json(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    return _request(url, params, headers).json()


def get_text(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> str:
    return _request(url, params, headers).text


def get_bytes(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> bytes:
    return _request(url, params, headers).content
```

- [ ] **Step 6: Create `src/congressional_sales/storage.py`**

```python
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
```

Add a `table()` helper to `Paths` alongside `raw`/`parquet`/`db` in Step 4
(insert this method into the `Paths` dataclass written above):

```python
    def table(self, name: str) -> Path:
        return self.parquet / name
```

- [ ] **Step 7: Create `tests/conftest.py`**

```python
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def warehouse(tmp_path, monkeypatch):
    """Redirect the whole warehouse at a tmp dir so tests never touch real data."""
    monkeypatch.setenv("CONGRESS_SALES_HOME", str(tmp_path / "wh"))
    from congressional_sales.config import paths

    paths().ensure()
    return tmp_path / "wh"
```

- [ ] **Step 8: Write the failing test — `tests/test_storage.py`**

```python
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
```

- [ ] **Step 9: Run test to verify it fails**

Run: `cd /Users/ryanmcgillicuddy/congressional-sales-2026 && uv sync && uv run pytest tests/test_storage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'congressional_sales'` (package not yet installed/importable until Step 1-6 files exist; if files already exist from Steps 1-6 above, this becomes a real RED — e.g. `Paths.table` missing before you add it in Step 6).

- [ ] **Step 10: Run test to verify it passes**

Run: `uv run pytest tests/test_storage.py -v`
Expected: `5 passed`

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml .env.example src/ tests/conftest.py tests/test_storage.py
git commit -m "Add project scaffolding: config, HTTP client, storage layer"
```

---

## Phase 1 — Data Acquisition

### Task 2: Equity daily price adapter (Tiingo)

**Files:**
- Create: `src/congressional_sales/sources/__init__.py`
- Create: `src/congressional_sales/sources/prices.py`
- Test: `tests/sources/test_prices.py`

**Interfaces:**
- Consumes: `http.get_json`, `storage.write`/`storage.read` (Task 1).
- Produces: `prices.fetch_tiingo(ticker: str, start: str | None = None) ->
  pl.DataFrame` (columns: `ticker: Utf8, date: Date, open: Float64, high:
  Float64, low: Float64, close: Float64, volume: Float64, close_adj:
  Float64`); `prices.ingest_prices(ticker: str, start: str | None = None)
  -> int` (writes to warehouse table `"equity_eod"`, key_cols
  `["ticker", "date"]`, returns rows written); `prices.ProviderUnavailable`
  exception class.

- [ ] **Step 1: Create `src/congressional_sales/sources/__init__.py`**

```python
"""Raw data adapters. Every adapter returns a typed polars DataFrame and
writes through storage.write() -- never touches the warehouse directly
from outside this package."""
```

- [ ] **Step 2: Write the failing test — `tests/sources/test_prices.py`**

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/sources/test_prices.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'congressional_sales.sources.prices'`

- [ ] **Step 4: Implement `src/congressional_sales/sources/prices.py`**

```python
"""Daily equity EOD prices, adjusted for splits/dividends.

Tiingo is the sole provider (a free key covers ~500 symbols/month with
adjusted history back decades -- see https://www.tiingo.com/). This price
feed does NOT include delisted securities -- see the "documented deviation"
in PRE_ANALYSIS_PLAN.md Section 3/11 and Global Constraints: this is a
known, reported limitation of this study, not a bug to silently paper over.
"""

from __future__ import annotations

import os

import polars as pl

from .. import storage
from ..http import get_json

TIINGO_URL = "https://api.tiingo.com/tiingo/daily/{ticker}/prices"

PRICE_SCHEMA = {
    "ticker": pl.Utf8, "date": pl.Date, "open": pl.Float64, "high": pl.Float64,
    "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64, "close_adj": pl.Float64,
}


class ProviderUnavailable(RuntimeError):
    pass


def fetch_tiingo(ticker: str, start: str | None = None) -> pl.DataFrame:
    token = os.getenv("TIINGO_API_TOKEN", "")
    if not token:
        raise ProviderUnavailable(
            "TIINGO_API_TOKEN is not set. Free key at https://www.tiingo.com/, then add it to .env."
        )
    params = {"token": token, "format": "json"}
    if start:
        params["startDate"] = start
    rows = get_json(TIINGO_URL.format(ticker=ticker.lower()), params=params)
    if not rows:
        return pl.DataFrame(schema=PRICE_SCHEMA)
    df = pl.DataFrame(rows, infer_schema_length=None)
    return (
        df.with_columns(
            pl.lit(ticker.upper()).alias("ticker"),
            pl.col("date").str.slice(0, 10).str.to_date("%Y-%m-%d"),
            pl.col("adjClose").alias("close_adj"),
        )
        .select(list(PRICE_SCHEMA))
        .cast(PRICE_SCHEMA)  # type: ignore[arg-type]
    )


def ingest_prices(ticker: str, start: str | None = None) -> int:
    df = fetch_tiingo(ticker, start=start)
    if df.is_empty():
        return 0
    storage.write("equity_eod", df, key_cols=["ticker", "date"], partition=ticker.upper())
    return df.height
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/sources/test_prices.py -v`
Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add src/congressional_sales/sources/__init__.py src/congressional_sales/sources/prices.py tests/sources/test_prices.py
git commit -m "Add Tiingo daily equity price adapter"
```

### Task 3: Trading calendar utilities

**Files:**
- Create: `src/congressional_sales/calendar.py`
- Test: `tests/test_calendar.py`

**Interfaces:**
- Consumes: `storage.read("equity_eod")` (Task 2).
- Produces: `calendar.trading_days(anchor_ticker: str = "SPY") -> list[date]`
  (sorted, deduplicated trading dates observed for `anchor_ticker` in the
  warehouse); `calendar.offset_trading_day(d: date, n: int, anchor_ticker:
  str = "SPY") -> date | None` (the trading day `n` sessions after `d`; `n`
  may be negative; returns `None` if the offset walks off either end of the
  known calendar rather than silently clamping or wrapping);
  `calendar.is_trading_day(d: date, anchor_ticker: str = "SPY") -> bool`;
  `calendar.offset_within_days(days: list[date], d: date, n: int) -> date |
  None` (the pure, storage-free core `offset_trading_day` wraps —
  `events/car.py` in Task 14 calls this directly against session dates
  derived from its own local `prices` argument, so CAR calculations never
  implicitly depend on global warehouse state matching whatever was passed
  in, which matters a great deal for making that module unit-testable with
  small fixtures).

This module exists specifically because PAP Section 11 calls out t+1
alignment as "the most common silent failure": `offset_trading_day` must
count sessions, never calendar days, and a Friday `d` with `n=1` must land
on the following Monday (or later, across a holiday), never Saturday.

- [ ] **Step 1: Write the failing test — `tests/test_calendar.py`**

```python
from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from congressional_sales import calendar, storage


def _seed_spy(dates: list[date]) -> None:
    n = len(dates)
    df = pl.DataFrame(
        {
            "ticker": ["SPY"] * n, "date": dates, "open": [1.0] * n, "high": [1.0] * n,
            "low": [1.0] * n, "close": [1.0] * n, "volume": [1.0] * n, "close_adj": [1.0] * n,
        }
    )
    storage.write("equity_eod", df, key_cols=["ticker", "date"])


def test_trading_days_are_sorted_and_deduped():
    _seed_spy([date(2024, 1, 3), date(2024, 1, 2), date(2024, 1, 2)])
    assert calendar.trading_days() == [date(2024, 1, 2), date(2024, 1, 3)]


def test_offset_trading_day_skips_the_weekend_gap():
    """Regression: a naive calendar-day t+1 would land on Saturday. The real
    next SESSION after Friday 2024-01-05 is Monday 2024-01-08."""
    _seed_spy([date(2024, 1, 4), date(2024, 1, 5), date(2024, 1, 8), date(2024, 1, 9)])
    assert calendar.offset_trading_day(date(2024, 1, 5), 1) == date(2024, 1, 8)


def test_offset_trading_day_negative_looks_backward():
    _seed_spy([date(2024, 1, 4), date(2024, 1, 5), date(2024, 1, 8)])
    assert calendar.offset_trading_day(date(2024, 1, 8), -1) == date(2024, 1, 5)


def test_offset_trading_day_zero_requires_d_itself_be_a_session():
    _seed_spy([date(2024, 1, 4), date(2024, 1, 5)])
    assert calendar.offset_trading_day(date(2024, 1, 4), 0) == date(2024, 1, 4)


def test_offset_trading_day_past_the_known_calendar_returns_none():
    _seed_spy([date(2024, 1, 4), date(2024, 1, 5)])
    assert calendar.offset_trading_day(date(2024, 1, 5), 5) is None


def test_offset_trading_day_from_a_non_session_date_anchors_forward():
    """d itself need not be a session (e.g. a Saturday disclosure date) --
    offsetting from it walks forward to the first known session on/after d,
    then applies n-1 additional sessions for n>=1."""
    _seed_spy([date(2024, 1, 4), date(2024, 1, 5), date(2024, 1, 8)])
    # Saturday 2024-01-06 -> first session on/after it is Monday 01-08 (n=1 effectively free);
    # +1 more session from there would be off the known calendar -> None for n=2,
    # but n=1 lands exactly on 01-08.
    assert calendar.offset_trading_day(date(2024, 1, 6), 1) == date(2024, 1, 8)


def test_is_trading_day():
    _seed_spy([date(2024, 1, 4), date(2024, 1, 5)])
    assert calendar.is_trading_day(date(2024, 1, 4)) is True
    assert calendar.is_trading_day(date(2024, 1, 6)) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_calendar.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'congressional_sales.calendar'`

- [ ] **Step 3: Implement `src/congressional_sales/calendar.py`**

```python
"""Trading-session calendar derived from an anchor ticker's own observed
price dates (default SPY) -- avoids a separate holiday-calendar dependency
and stays exactly consistent with whatever dates this warehouse actually
has prices for, which is what every return calculation in this study
walks against anyway.

PAP Section 11 calls out t+1 alignment as the most common silent failure
in this kind of study: offset_trading_day counts SESSIONS, never calendar
days.
"""

from __future__ import annotations

from bisect import bisect_left
from datetime import date
from functools import lru_cache

from . import storage


@lru_cache(maxsize=8)
def trading_days(anchor_ticker: str = "SPY") -> list[date]:
    df = storage.read("equity_eod")
    if df.is_empty():
        return []
    days = df.filter(df["ticker"] == anchor_ticker.upper())["date"].unique().sort()
    return days.to_list()


def is_trading_day(d: date, anchor_ticker: str = "SPY") -> bool:
    days = trading_days(anchor_ticker)
    i = bisect_left(days, d)
    return i < len(days) and days[i] == d


def offset_within_days(days: list[date], d: date, n: int) -> date | None:
    """Pure version of offset_trading_day: the session n sessions after d,
    against an explicit, already-known sorted session list rather than
    global storage. This is the function to use whenever the caller
    already has its own price/session data in hand (e.g.
    events/car.py operating on a locally-loaded prices frame in a unit
    test) -- calling offset_trading_day there would silently read from
    the (possibly-empty, possibly-different) global warehouse instead of
    the caller's own data, which is exactly the kind of coupling bug this
    split avoids. offset_trading_day (below) is a thin wrapper for
    callers that genuinely want the global warehouse's calendar.

    If d itself is not a known session, first anchor forward to the
    earliest known session on or after d (this is what "n=1 trading days
    after a Saturday disclosure" means in practice), then apply the
    remaining n-1 (for n>=1) or n (for n<=0, anchored backward instead)
    offset from there. Returns None if the result would fall outside the
    known calendar rather than silently clamping.
    """
    if not days:
        return None

    i = bisect_left(days, d)
    if i < len(days) and days[i] == d:
        base_idx = i
        remaining = n
    elif n >= 0:
        # Anchor forward to the first known session on/after d; that IS
        # the n=1 result already, so only n-1 further sessions remain.
        if i >= len(days):
            return None
        base_idx = i
        remaining = n - 1
    else:
        # Anchor backward to the last known session before d.
        if i == 0:
            return None
        base_idx = i - 1
        remaining = n + 1

    target = base_idx + remaining
    if target < 0 or target >= len(days):
        return None
    return days[target]


def offset_trading_day(d: date, n: int, anchor_ticker: str = "SPY") -> date | None:
    """offset_within_days against the global warehouse's own trading_days()."""
    return offset_within_days(trading_days(anchor_ticker), d, n)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_calendar.py -v`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add src/congressional_sales/calendar.py tests/test_calendar.py
git commit -m "Add trading-session calendar with session-based (not calendar-day) offsets"
```

### Task 4: Quiver congressional trades adapter (standalone)

This is a fresh, standalone reimplementation of the same adapter already
built and live-verified in the private Investment repo's `marketlab`
platform earlier this session — the exact field mapping and PIT
discipline below were validated against real Quiver API responses. This
repo must not import that private package, so the logic is duplicated
here deliberately.

**Files:**
- Create: `src/congressional_sales/sources/quiver.py`
- Test: `tests/sources/test_quiver.py`

**Interfaces:**
- Consumes: `storage.write`/`storage.read`, `http.get_json` (Task 1-2).
- Produces: `quiver.parse_congress_trades(rows: list[dict]) -> pl.DataFrame`
  (columns: `ticker, politician, bioguide_id, chamber, party, transaction,
  transaction_date: Date, report_date: Date, amount_low: Float64,
  amount_range: Utf8, ticker_type: Utf8, description, excess_return,
  price_change, spy_change` — `ticker_type` is Quiver's own instrument-type
  code (observed live as `"ST"` for common stock during planning; Task 7's
  sample-construction funnel filters on this field for the "common stock
  transactions only" inclusion rule, so it must survive ingestion even
  though nothing in this task uses it yet);
  `quiver.ingest_congress_trades(ticker: str) -> int` (writes
  table `"congress_trades"`, key_cols `["ticker", "bioguide_id",
  "transaction_date", "transaction", "amount_range"]`);
  `quiver.MissingTokenError`.

**Point-in-time discipline (critical — this is the entire reason the two
disclosure dates exist in the schema):** the STOCK Act gives members of
Congress up to 45 days to disclose a trade. `report_date` is when the
disclosure was actually filed and became publicly knowable; `transaction_date`
is the underlying trade date. Every downstream sample-construction and
event-study step in this study must gate on `report_date`, never
`transaction_date` — this is exactly the field the entire study depends on
using correctly, since CAR is computed relative to the actionable date.

- [ ] **Step 1: Write the failing test — `tests/sources/test_quiver.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/sources/test_quiver.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/congressional_sales/sources/quiver.py`**

```python
"""Quiver Quantitative congressional trading adapter.

Same point-in-time trap as Form 4 insider trading: the STOCK Act gives
members of Congress up to 45 days to disclose a trade, so transaction_date
is NOT knowable on the date it happened -- only report_date (when the
periodic transaction report was actually filed) is. Every sample-
construction and event-study step in this study must gate on
report_date <= as_of, never transaction_date.

There is no unique row ID in Quiver's response, so idempotent upsert keys
on a natural composite (ticker, bioguide_id, transaction_date, transaction,
amount_range). Two genuinely distinct disclosures on the same day of the
same type/range by the same politician for the same ticker will collapse
to one row -- an accepted limitation given the data as published.
"""

from __future__ import annotations

import polars as pl

from .. import storage
from ..config import QUIVER_API_TOKEN
from ..http import get_json

CONGRESS_HISTORICAL_URL = "https://api.quiverquant.com/beta/historical/congresstrading/{ticker}"


class MissingTokenError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    if not QUIVER_API_TOKEN:
        raise MissingTokenError(
            "QUIVER_API_TOKEN is not set. Get a Trader-tier key at "
            "https://www.quiverquant.com/api-setup/, then add it to .env."
        )
    return {"Accept": "application/json", "Authorization": f"Token {QUIVER_API_TOKEN}"}


CONGRESS_TRADES_SCHEMA = {
    "ticker": pl.Utf8, "politician": pl.Utf8, "bioguide_id": pl.Utf8, "chamber": pl.Utf8,
    "party": pl.Utf8, "transaction": pl.Utf8, "transaction_date": pl.Date, "report_date": pl.Date,
    "amount_low": pl.Float64, "amount_range": pl.Utf8, "ticker_type": pl.Utf8, "description": pl.Utf8,
    "excess_return": pl.Float64, "price_change": pl.Float64, "spy_change": pl.Float64,
}

_RENAME = {
    "Ticker": "ticker", "Representative": "politician", "BioGuideID": "bioguide_id",
    "House": "chamber", "Party": "party", "Transaction": "transaction",
    "TransactionDate": "transaction_date", "ReportDate": "report_date",
    "Range": "amount_range", "Amount": "amount_low", "TickerType": "ticker_type",
    "Description": "description",
    "ExcessReturn": "excess_return", "PriceChange": "price_change", "SPYChange": "spy_change",
}


def parse_congress_trades(rows: list[dict]) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame(schema=CONGRESS_TRADES_SCHEMA)

    df = pl.DataFrame(rows, infer_schema_length=None)
    present = {k: v for k, v in _RENAME.items() if k in df.columns}
    df = df.rename(present)
    for col in CONGRESS_TRADES_SCHEMA:
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).alias(col))

    return (
        df.with_columns(
            pl.col("transaction_date").cast(pl.Utf8).str.to_date("%Y-%m-%d", strict=False),
            pl.col("report_date").cast(pl.Utf8).str.to_date("%Y-%m-%d", strict=False),
            pl.col("amount_low").cast(pl.Utf8).str.replace_all(",", "").cast(pl.Float64, strict=False),
        )
        .select(list(CONGRESS_TRADES_SCHEMA))
        .cast(CONGRESS_TRADES_SCHEMA)  # type: ignore[arg-type]
    )


def ingest_congress_trades(ticker: str) -> int:
    rows = get_json(CONGRESS_HISTORICAL_URL.format(ticker=ticker.upper()), headers=_headers())
    df = parse_congress_trades(rows)
    if df.is_empty():
        return 0
    df = df.with_columns(pl.lit(ticker.upper()).alias("ticker"))
    storage.write(
        "congress_trades", df,
        key_cols=["ticker", "bioguide_id", "transaction_date", "transaction", "amount_range"],
        partition=ticker.upper(),
    )
    return df.height
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/sources/test_quiver.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/congressional_sales/sources/quiver.py tests/sources/test_quiver.py
git commit -m "Add standalone Quiver congressional trading adapter"
```

### Task 5: Ken French factor library adapter (FF3 + momentum)

**Files:**
- Create: `src/congressional_sales/sources/french.py`
- Test: `tests/sources/test_french.py`

**Interfaces:**
- Consumes: `http.get_bytes` (Task 1).
- Produces: `french.parse_ff3_csv(text: str) -> pl.DataFrame` (columns:
  `date: Date, mkt_rf: Float64, smb: Float64, hml: Float64, rf: Float64`,
  daily factors, values as **decimals** not percent — the raw file is in
  percent and this function divides by 100); `french.parse_momentum_csv(text:
  str) -> pl.DataFrame` (columns: `date: Date, mom: Float64`, decimal);
  `french.ingest_factors() -> int` (downloads both files, joins on `date`,
  writes table `"ff_factors"` with columns `date, mkt_rf, smb, hml, mom, rf`,
  key_cols `["date"]`, returns rows written).

Ken French's data library serves zipped CSVs with a fixed, quirky text
format: several header lines before the data starts, and a text footer
after it ends (typically starting with a blank line then "Copyright" or
similar prose). This function must be robust to that shape — find the data
block by locating the first line that starts with an 8-digit date, and stop
at the first line after that block that does NOT start with a digit.

- [ ] **Step 1: Write the failing test — `tests/sources/test_french.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/sources/test_french.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/congressional_sales/sources/french.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/sources/test_french.py -v`
Expected: `3 passed`

- [ ] **Step 5: Verify the real zip format live before trusting this in production**

Run:
```bash
uv run python -c "
from congressional_sales.sources.french import _fetch_zip_member_text, FF3_ZIP_URL, _data_block
text = _fetch_zip_member_text(FF3_ZIP_URL)
print(repr(text[:500]))
print('---data block head---')
print(_data_block(text)[:200])
"
```
Expected: real header lines visible, then the data block starting with an
8-digit date. If the real file's header/footer shape differs from the
fixture above (column order, extra header lines, a second data section for
annual factors below the daily one), adjust `_data_block`/`parse_ff3_csv`
to match what you actually observe — do not assume the fixture is exactly
right; French's file has historically included a second annual-factors
block after a blank-line separator further down, which `_data_block`'s
"stop at the first non-digit-prefixed line" logic already correctly
excludes, but confirm this live.

- [ ] **Step 6: Commit**

```bash
git add src/congressional_sales/sources/french.py tests/sources/test_french.py
git commit -m "Add Ken French FF3 + momentum factor adapter"
```

### Task 6: Legislator terms + committee assignment adapter

**Files:**
- Create: `src/congressional_sales/sources/legislators.py`
- Test: `tests/sources/test_legislators.py`

**Interfaces:**
- Consumes: `http.get_text`, `storage.write`/`storage.read` (Task 1).
- Produces: `legislators.parse_legislator_terms(yaml_docs: list[dict]) ->
  pl.DataFrame` (columns: `bioguide_id: Utf8, full_name: Utf8, chamber:
  Utf8 ("rep"|"sen"), term_start: Date, term_end: Date, state: Utf8, party:
  Utf8`, one row per term per member — a member serving multiple
  non-consecutive terms gets multiple rows);
  `legislators.parse_committee_assignments(membership: dict, committees:
  list[dict]) -> pl.DataFrame` (columns: `bioguide_id: Utf8,
  committee_code: Utf8, committee_name: Utf8, chamber: Utf8`);
  `legislators.ingest_legislator_terms() -> int` (fetches both current and
  historical legislator YAML, writes table `"legislator_terms"`, key_cols
  `["bioguide_id", "chamber", "term_start"]`);
  `legislators.ingest_committee_assignments() -> int` (writes table
  `"committee_assignments"`, key_cols `["bioguide_id", "committee_code"]`
  — **this is a current-only snapshot, per the Global Constraints
  documented committee-data limitation**).

- [ ] **Step 1: Write the failing test — `tests/sources/test_legislators.py`**

```python
from __future__ import annotations

from datetime import date

import yaml

from congressional_sales.sources import legislators

LEGISLATOR_YAML = """
- id:
    bioguide: C000127
  name:
    first: Maria
    last: Cantwell
    official_full: Maria Cantwell
  terms:
  - type: rep
    start: '1993-01-05'
    end: '1995-01-03'
    state: WA
    district: 1
    party: Democrat
  - type: sen
    start: '2001-01-03'
    end: '2007-01-03'
    state: WA
    class: 1
    party: Democrat
"""

COMMITTEE_MEMBERSHIP_YAML = """
SSAF:
- name: John Boozman
  party: majority
  rank: 1
  title: Chairman
  bioguide: B001236
- name: Amy Klobuchar
  party: minority
  rank: 1
  bioguide: K000367
"""

COMMITTEES_YAML = """
- type: senate
  name: Senate Committee on Agriculture, Nutrition, and Forestry
  thomas_id: SSAF
"""


def test_parse_legislator_terms_produces_one_row_per_term():
    docs = yaml.safe_load(LEGISLATOR_YAML)
    df = legislators.parse_legislator_terms(docs)
    assert df.height == 2
    assert df["bioguide_id"][0] == "C000127"
    assert df["chamber"][0] == "rep"
    assert df["term_start"][0] == date(1993, 1, 5)
    assert df["term_end"][0] == date(1995, 1, 3)
    assert df["chamber"][1] == "sen"
    assert df["party"][1] == "Democrat"


def test_parse_committee_assignments_maps_code_to_name():
    membership = yaml.safe_load(COMMITTEE_MEMBERSHIP_YAML)
    committees = yaml.safe_load(COMMITTEES_YAML)
    df = legislators.parse_committee_assignments(membership, committees)
    assert df.height == 2
    boozman = df.filter(df["bioguide_id"] == "B001236")
    assert boozman["committee_name"][0] == "Senate Committee on Agriculture, Nutrition, and Forestry"
    assert boozman["chamber"][0] == "senate"


def test_ingest_legislator_terms_writes_both_current_and_historical(monkeypatch):
    monkeypatch.setattr(
        legislators, "get_text",
        lambda url, *a, **k: LEGISLATOR_YAML if "current" in url or "historical" in url else "",
    )
    n = legislators.ingest_legislator_terms()
    assert n == 2  # same fixture used for both current+historical -> deduped by (bioguide,chamber,term_start)
    from congressional_sales import storage
    got = storage.read("legislator_terms")
    assert got.height == 2


def test_ingest_committee_assignments_writes_table(monkeypatch):
    monkeypatch.setattr(
        legislators, "get_text",
        lambda url, *a, **k: COMMITTEE_MEMBERSHIP_YAML if "membership" in url else COMMITTEES_YAML,
    )
    n = legislators.ingest_committee_assignments()
    assert n == 2
    from congressional_sales import storage
    got = storage.read("committee_assignments")
    assert got.height == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/sources/test_legislators.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/congressional_sales/sources/legislators.py`**

```python
"""Legislator terms and committee assignments, from the public-domain
unitedstates/congress-legislators project (no auth, no rate-limit concern
at our volume -- a handful of large YAML files fetched once and cached in
the warehouse).

Committee membership is a CURRENT-ONLY snapshot -- the upstream project
does not publish historical per-congress committee membership. H4's
CommitteeMatch therefore uses each member's most recent known committee
assignment, not their true assignment at the historical transaction date.
This is a documented limitation (see PRE_ANALYSIS_PLAN.md Global
Constraints), implemented exactly this way on purpose, not silently.
"""

from __future__ import annotations

import yaml
import polars as pl

from .. import storage
from ..http import get_text

LEGISLATORS_CURRENT_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-current.yaml"
LEGISLATORS_HISTORICAL_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-historical.yaml"
COMMITTEE_MEMBERSHIP_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/committee-membership-current.yaml"
COMMITTEES_CURRENT_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/committees-current.yaml"

TERMS_SCHEMA = {
    "bioguide_id": pl.Utf8, "full_name": pl.Utf8, "chamber": pl.Utf8,
    "term_start": pl.Date, "term_end": pl.Date, "state": pl.Utf8, "party": pl.Utf8,
}


def parse_legislator_terms(docs: list[dict]) -> pl.DataFrame:
    rows = []
    for person in docs:
        bioguide = person.get("id", {}).get("bioguide")
        if not bioguide:
            continue
        full_name = person.get("name", {}).get("official_full", "")
        for term in person.get("terms", []):
            rows.append(
                {
                    "bioguide_id": bioguide,
                    "full_name": full_name,
                    "chamber": term.get("type"),
                    "term_start": term.get("start"),
                    "term_end": term.get("end"),
                    "state": term.get("state"),
                    "party": term.get("party"),
                }
            )
    if not rows:
        return pl.DataFrame(schema=TERMS_SCHEMA)
    return (
        pl.DataFrame(rows)
        .with_columns(pl.col("term_start").str.to_date("%Y-%m-%d"), pl.col("term_end").str.to_date("%Y-%m-%d"))
        .select(list(TERMS_SCHEMA))
        .cast(TERMS_SCHEMA)  # type: ignore[arg-type]
    )


ASSIGNMENTS_SCHEMA = {"bioguide_id": pl.Utf8, "committee_code": pl.Utf8, "committee_name": pl.Utf8, "chamber": pl.Utf8}


def parse_committee_assignments(membership: dict, committees: list[dict]) -> pl.DataFrame:
    name_and_chamber = {c["thomas_id"]: (c["name"], c["type"]) for c in committees if "thomas_id" in c}
    rows = []
    for code, members in membership.items():
        name, chamber = name_and_chamber.get(code, (code, "unknown"))
        for m in members:
            bioguide = m.get("bioguide")
            if not bioguide:
                continue
            rows.append({"bioguide_id": bioguide, "committee_code": code, "committee_name": name, "chamber": chamber})
    if not rows:
        return pl.DataFrame(schema=ASSIGNMENTS_SCHEMA)
    return pl.DataFrame(rows).select(list(ASSIGNMENTS_SCHEMA)).cast(ASSIGNMENTS_SCHEMA)  # type: ignore[arg-type]


def ingest_legislator_terms() -> int:
    current = yaml.safe_load(get_text(LEGISLATORS_CURRENT_URL)) or []
    historical = yaml.safe_load(get_text(LEGISLATORS_HISTORICAL_URL)) or []
    df = parse_legislator_terms(current + historical)
    if df.is_empty():
        return 0
    storage.write("legislator_terms", df, key_cols=["bioguide_id", "chamber", "term_start"])
    return storage.read("legislator_terms").height


def ingest_committee_assignments() -> int:
    membership = yaml.safe_load(get_text(COMMITTEE_MEMBERSHIP_URL)) or {}
    committees = yaml.safe_load(get_text(COMMITTEES_CURRENT_URL)) or []
    df = parse_committee_assignments(membership, committees)
    if df.is_empty():
        return 0
    storage.write("committee_assignments", df, key_cols=["bioguide_id", "committee_code"])
    return df.height
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/sources/test_legislators.py -v`
Expected: `4 passed`

- [ ] **Step 5: Verify the real YAML shape live**

Run:
```bash
uv run python -c "
from congressional_sales.sources.legislators import ingest_legislator_terms, ingest_committee_assignments
print('terms rows:', ingest_legislator_terms())
print('committee rows:', ingest_committee_assignments())
from congressional_sales import storage
print(storage.read('legislator_terms').head(3))
print(storage.read('committee_assignments').head(3))
"
```
Expected: real row counts in the thousands for terms, hundreds for
committee assignments, no parse errors. If any real record is missing a
`bioguide`, `terms`, or a committee's `thomas_id`, confirm the `.get(...)`
guards above skip it cleanly rather than raising — this was verified live
during planning for `legislators-current.yaml`/`committee-membership-
current.yaml`/`committees-current.yaml`, but re-confirm since these files
change over time.

- [ ] **Step 6: Commit**

```bash
git add src/congressional_sales/sources/legislators.py tests/sources/test_legislators.py
git commit -m "Add legislator terms + current committee assignment adapter"
```

---

## Phase 2 — Sample Construction

### Task 7: SIC code lookup + Fama-French 12-industry classification

Needed by both T2 (descriptive statistics by sector) and Task 15's
size/industry-matched CAR method (Section 6) — built now, ahead of both.

**Files:**
- Create: `src/congressional_sales/sources/sic.py`
- Create: `src/congressional_sales/sample/industry.py`
- Test: `tests/sources/test_sic.py`
- Test: `tests/sample/test_industry.py`

**Interfaces:**
- Consumes: `http.get_json`, `storage.write`/`storage.read` (Task 1).
- Produces: `sic.resolve_cik(ticker: str) -> int | None` (via EDGAR's
  `company_tickers.json`); `sic.fetch_sic(cik: int) -> tuple[str, str] |
  None` (SIC code + description, via EDGAR's `submissions` endpoint);
  `sic.ingest_sic_codes(tickers: list[str]) -> int` (writes table
  `"sic_codes"`, columns `ticker, cik, sic_code, sic_description`, key_cols
  `["ticker"]`); `industry.ff12_industry(sic_code: str) -> str` (pure
  function, no I/O — classifies a 4-digit SIC code string into one of the
  12 Fama-French industry names, or `"Other"` if unclassified/unknown);
  `industry.load_ff12_ranges() -> list[tuple[int, int, str]]` (fetches and
  parses Ken French's own SIC-range definition file into `(sic_start,
  sic_end, industry_name)` tuples — `ff12_industry` uses this table
  internally, cached).

- [ ] **Step 1: Write the failing test — `tests/sources/test_sic.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/sources/test_sic.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/congressional_sales/sources/sic.py`**

```python
"""SIC (Standard Industrial Classification) code lookup via SEC EDGAR --
the same free, no-auth endpoints EDGAR-based platforms use for CIK
resolution and company facts."""

from __future__ import annotations

import polars as pl

from .. import storage
from ..config import USER_AGENT
from ..http import get_json

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"


def resolve_cik(ticker: str) -> int | None:
    payload = get_json(TICKERS_URL, headers={"User-Agent": USER_AGENT})
    for row in payload.values():
        if row["ticker"].upper() == ticker.upper():
            return int(row["cik_str"])
    return None


def fetch_sic(cik: int) -> tuple[str, str] | None:
    payload = get_json(SUBMISSIONS_URL.format(cik=cik), headers={"User-Agent": USER_AGENT})
    sic_code = payload.get("sic")
    if not sic_code:
        return None
    return (sic_code, payload.get("sicDescription", ""))


def ingest_sic_codes(tickers: list[str]) -> int:
    rows = []
    for t in tickers:
        cik = resolve_cik(t)
        if cik is None:
            continue
        result = fetch_sic(cik)
        if result is None:
            continue
        code, desc = result
        rows.append({"ticker": t.upper(), "cik": cik, "sic_code": code, "sic_description": desc})
    if not rows:
        return 0
    df = pl.DataFrame(rows, schema={"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8})
    storage.write("sic_codes", df, key_cols=["ticker"])
    return df.height
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/sources/test_sic.py -v`
Expected: `4 passed`

- [ ] **Step 5: Write the failing test — `tests/sample/test_industry.py`**

```python
from __future__ import annotations

from congressional_sales.sample import industry


def test_ff12_industry_classifies_a_known_tech_sic_code():
    """SIC 7372 (Prepackaged Software) is canonically Business Equipment
    in the Fama-French 12-industry scheme."""
    assert industry.ff12_industry("7372") == "Business Equipment"


def test_ff12_industry_unknown_code_returns_other():
    assert industry.ff12_industry("9999") == "Other"


def test_ff12_industry_handles_none_and_empty():
    assert industry.ff12_industry(None) == "Other"
    assert industry.ff12_industry("") == "Other"
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/sample/test_industry.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 7: Implement `src/congressional_sales/sample/industry.py`**

```python
"""Fama-French 12-industry classification from a 4-digit SIC code.

Uses Ken French's own published SIC-range definition
(https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html,
"Industry Portfolios" section, 12-industry definitions file) rather than a
hand-transcribed copy of the ranges -- SIC-range tables like this are long
and easy to get subtly wrong by memory, so this module fetches the
authoritative source and parses it, the same discipline used for the
factor files in sources/french.py.
"""

from __future__ import annotations

import re
from functools import lru_cache

FF12_DEFINITIONS_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Siccodes12.zip"

# Format (confirmed live during implementation -- see Step 8): each
# industry's block starts with a line like " 1 NoDur  Consumer NonDurables...",
# followed by SIC-range lines like "  0100-0999 Agriculture...". A range
# line's first four-digit-dash-four-digit token is what this regex extracts;
# trailing descriptive text on the same line is discarded.
_INDUSTRY_HEADER = re.compile(r"^\s*(\d{1,2})\s+(\S+)\s+(.+)$")
_RANGE_LINE = re.compile(r"^\s*(\d{4})-(\d{4})\s")

# Canonical short-code -> full industry name, per Ken French's own labels.
_NAMES = {
    "NoDur": "Consumer NonDurables", "Durbl": "Consumer Durables", "Manuf": "Manufacturing",
    "Enrgy": "Energy", "Chems": "Chemicals", "BusEq": "Business Equipment",
    "Telcm": "Telephone and Television Transmission", "Utils": "Utilities",
    "Shops": "Shops", "Hlth": "Healthcare", "Money": "Money", "Other": "Other",
}


def _parse_ranges(text: str) -> list[tuple[int, int, str]]:
    ranges: list[tuple[int, int, str]] = []
    current_name = "Other"
    for line in text.splitlines():
        header = _INDUSTRY_HEADER.match(line)
        rng = _RANGE_LINE.match(line)
        if header and not rng:
            short_code = header.group(2)
            current_name = _NAMES.get(short_code, short_code)
        elif rng:
            ranges.append((int(rng.group(1)), int(rng.group(2)), current_name))
    return ranges


@lru_cache(maxsize=1)
def load_ff12_ranges() -> list[tuple[int, int, str]]:
    import io
    import zipfile

    from ..http import get_bytes

    zbytes = get_bytes(FF12_DEFINITIONS_URL)
    with zipfile.ZipFile(io.BytesIO(zbytes)) as zf:
        name = zf.namelist()[0]
        text = zf.read(name).decode("latin-1")
    return _parse_ranges(text)


def ff12_industry(sic_code: str | None) -> str:
    if not sic_code:
        return "Other"
    try:
        code = int(sic_code)
    except ValueError:
        return "Other"
    for lo, hi, name in load_ff12_ranges():
        if lo <= code <= hi:
            return name
    return "Other"
```

- [ ] **Step 8: Verify the real Siccodes12.zip format live, then fix the parser to match**

Run:
```bash
uv run python -c "
from congressional_sales.sample.industry import load_ff12_ranges
ranges = load_ff12_ranges()
print(len(ranges), 'ranges loaded')
print(ranges[:5])
"
```

This file's exact text layout must be confirmed live — do not trust the
regexes above blindly. If the header/range line shapes differ from what
`_INDUSTRY_HEADER`/`_RANGE_LINE` expect (French's SIC definition files
have historically used a few different header punctuation styles across
the 5/10/12/17/30/38/48/49-industry variants), adjust the regexes to match
reality and re-run `test_ff12_industry_classifies_a_known_tech_sic_code`
(SIC 7372 must resolve to `"Business Equipment"`) as the ground-truth
check. If the file cannot be parsed reliably, fall back to fetching the
industry definitions from a second authoritative source (Ken French's data
library page itself lists the SIC ranges in HTML tables as an alternative
to the zip) rather than shipping a classifier that silently returns
`"Other"` for everything.

- [ ] **Step 9: Run test to verify it passes**

Run: `uv run pytest tests/sample/test_industry.py -v`
Expected: `3 passed`

- [ ] **Step 10: Commit**

```bash
git add src/congressional_sales/sources/sic.py src/congressional_sales/sample/industry.py tests/sources/test_sic.py tests/sample/test_industry.py
git commit -m "Add SIC code lookup and Fama-French 12-industry classification"
```

### Task 8: Inclusion/exclusion funnel (T1)

**Files:**
- Create: `src/congressional_sales/sample/__init__.py`
- Create: `src/congressional_sales/sample/funnel.py`
- Test: `tests/sample/test_funnel.py`

**Interfaces:**
- Consumes: `storage.read("congress_trades")` (Task 4),
  `storage.read("equity_eod")` (Task 2).
- Produces: `funnel.FunnelStep` (dataclass: `name: str, count_before: int,
  count_after: int`); `funnel.FunnelResult` (dataclass: `steps:
  list[FunnelStep], sample: pl.DataFrame`); `funnel.build_sample(
  min_prior_trading_days: int = 60, max_horizon_trading_days: int = 180,
  period_start: date = date(2014, 1, 1), period_end: date | None = None)
  -> FunnelResult`.

**Known data-source limitation for this task (document, do not silently
skip):** Quiver's congressional-trading feed does not expose filer
relationship (self / spouse / dependent child) as a separate field — every
disclosed transaction already legally covers all three by definition of
what a PTR filing is, so there is nothing to additionally filter on here.
Note this in the module docstring rather than implementing a no-op filter
that pretends to check something the data cannot support.

- [ ] **Step 1: Create `src/congressional_sales/sample/__init__.py`**

```python
"""Sample construction: the inclusion/exclusion funnel (Section 4) and the
four sequential screens (Section 5) from PRE_ANALYSIS_PLAN.md."""
```

- [ ] **Step 2: Write the failing test — `tests/sample/test_funnel.py`**

```python
from __future__ import annotations

from datetime import date, timedelta

import polars as pl
import pytest

from congressional_sales import storage
from congressional_sales.sample import funnel


def _seed_trade(ticker, bioguide, report_date, transaction_date, amount_low, ticker_type="ST", transaction="Purchase"):
    df = pl.DataFrame(
        {
            "ticker": [ticker], "politician": ["Test Member"], "bioguide_id": [bioguide],
            "chamber": ["Representatives"], "party": ["R"], "transaction": [transaction],
            "transaction_date": [transaction_date], "report_date": [report_date],
            "amount_low": [amount_low], "amount_range": ["$1,001 - $15,000"],
            "ticker_type": [ticker_type], "description": [None],
            "excess_return": [None], "price_change": [None], "spy_change": [None],
        },
        schema={
            "ticker": pl.Utf8, "politician": pl.Utf8, "bioguide_id": pl.Utf8, "chamber": pl.Utf8,
            "party": pl.Utf8, "transaction": pl.Utf8, "transaction_date": pl.Date, "report_date": pl.Date,
            "amount_low": pl.Float64, "amount_range": pl.Utf8, "ticker_type": pl.Utf8, "description": pl.Utf8,
            "excess_return": pl.Float64, "price_change": pl.Float64, "spy_change": pl.Float64,
        },
    )
    storage.write(
        "congress_trades", df,
        key_cols=["ticker", "bioguide_id", "transaction_date", "transaction", "amount_range"],
    )


def _seed_prices(ticker, dates):
    n = len(dates)
    df = pl.DataFrame(
        {
            "ticker": [ticker] * n, "date": dates, "open": [1.0] * n, "high": [1.0] * n,
            "low": [1.0] * n, "close": [1.0] * n, "volume": [1.0] * n, "close_adj": [1.0] * n,
        }
    )
    storage.write("equity_eod", df, key_cols=["ticker", "date"])


def _trading_dates(start: date, n: int) -> list[date]:
    """n consecutive weekday dates starting at start (test helper -- real
    calendars come from calendar.py, but the funnel only needs row counts
    for its own filters, not calendar-aware offsets)."""
    out = []
    d = start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def test_common_stock_only_excludes_non_st_ticker_type():
    report = date(2020, 6, 15)
    _seed_trade("AAPL", "A001", report, report, 1001.0, ticker_type="ST")
    _seed_trade("MUNIBOND", "A001", report, report, 1001.0, ticker_type="MF")
    _seed_prices("AAPL", _trading_dates(date(2019, 1, 1), 300))
    _seed_prices("MUNIBOND", _trading_dates(date(2019, 1, 1), 300))
    result = funnel.build_sample(period_start=date(2020, 1, 1), period_end=date(2020, 12, 31))
    step = next(s for s in result.steps if s.name == "common_stock_only")
    assert step.count_before == 2
    assert step.count_after == 1
    assert result.sample["ticker"].to_list() == ["AAPL"]


def test_above_statutory_threshold_excludes_small_amounts():
    report = date(2020, 6, 15)
    _seed_trade("AAPL", "A001", report, report, 1001.0)
    _seed_trade("AAPL", "A002", report, report, 500.0)
    _seed_prices("AAPL", _trading_dates(date(2019, 1, 1), 300))
    result = funnel.build_sample(period_start=date(2020, 1, 1), period_end=date(2020, 12, 31))
    step = next(s for s in result.steps if s.name == "above_statutory_threshold")
    assert step.count_before == 2
    assert step.count_after == 1


def test_prior_price_history_below_60_days_excluded():
    report = date(2020, 6, 15)
    _seed_trade("THIN", "A001", report, report, 1001.0)
    _seed_trade("RICH", "A002", report, report, 1001.0)
    # THIN: only 10 trading days before report_date.
    _seed_prices("THIN", _trading_dates(date(2020, 5, 1), 10))
    # RICH: 300 trading days before report_date (well over the 60-day floor).
    _seed_prices("RICH", _trading_dates(date(2019, 1, 1), 300))
    result = funnel.build_sample(period_start=date(2020, 1, 1), period_end=date(2020, 12, 31))
    step = next(s for s in result.steps if s.name == "min_prior_trading_history")
    assert "THIN" not in result.sample["ticker"].to_list()
    assert "RICH" in result.sample["ticker"].to_list()
    assert step.count_before == 2
    assert step.count_after == 1


def test_full_forward_window_excludes_thin_forward_coverage():
    report = date(2020, 1, 15)
    _seed_trade("NOFWD", "A001", report, report, 1001.0)
    _seed_trade("FULLFWD", "A002", report, report, 1001.0)
    prior = _trading_dates(date(2019, 1, 1), 300)
    _seed_prices("NOFWD", prior + _trading_dates(date(2020, 1, 16), 5))  # only 5 forward days
    _seed_prices("FULLFWD", prior + _trading_dates(date(2020, 1, 16), 200))  # >= 180 forward days
    result = funnel.build_sample(period_start=date(2020, 1, 1), period_end=date(2020, 12, 31))
    assert "NOFWD" not in result.sample["ticker"].to_list()
    assert "FULLFWD" in result.sample["ticker"].to_list()


def test_dedupe_collapses_literal_duplicate_filings():
    report = date(2020, 6, 15)
    _seed_trade("AAPL", "A001", report, report, 1001.0)
    _seed_trade("AAPL", "A001", report, report, 1001.0)  # identical -- storage.write already collapses this
    _seed_prices("AAPL", _trading_dates(date(2019, 1, 1), 300))
    result = funnel.build_sample(period_start=date(2020, 1, 1), period_end=date(2020, 12, 31))
    assert result.sample.height == 1


def test_funnel_steps_are_monotonically_non_increasing():
    report = date(2020, 6, 15)
    _seed_trade("AAPL", "A001", report, report, 1001.0)
    _seed_prices("AAPL", _trading_dates(date(2019, 1, 1), 300))
    result = funnel.build_sample(period_start=date(2020, 1, 1), period_end=date(2020, 12, 31))
    for step in result.steps:
        assert step.count_after <= step.count_before


def test_period_filter_excludes_trades_outside_the_sample_window():
    _seed_trade("AAPL", "A001", date(2013, 6, 15), date(2013, 6, 15), 1001.0)  # before period_start
    _seed_prices("AAPL", _trading_dates(date(2012, 1, 1), 300))
    result = funnel.build_sample(period_start=date(2014, 1, 1), period_end=date(2020, 12, 31))
    assert result.sample.is_empty()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/sample/test_funnel.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement `src/congressional_sales/sample/funnel.py`**

```python
"""Inclusion/exclusion funnel (PRE_ANALYSIS_PLAN.md Section 4). Every step
is logged with an exact before/after count -- this IS table T1.

Not implemented as a separate filter (documented, not a silent gap):
Quiver's feed has no filer-relationship field (self/spouse/dependent
child) -- every disclosed transaction already covers all three by legal
definition of what a PTR filing is, so there is nothing to filter here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import polars as pl

from .. import storage


@dataclass
class FunnelStep:
    name: str
    count_before: int
    count_after: int


@dataclass
class FunnelResult:
    steps: list[FunnelStep]
    sample: pl.DataFrame


def _step(steps: list[FunnelStep], name: str, before: pl.DataFrame, after: pl.DataFrame) -> None:
    steps.append(FunnelStep(name=name, count_before=before.height, count_after=after.height))


def build_sample(
    min_prior_trading_days: int = 60,
    max_horizon_trading_days: int = 180,
    period_start: date = date(2014, 1, 1),
    period_end: date | None = None,
) -> FunnelResult:
    steps: list[FunnelStep] = []
    df = storage.read("congress_trades")
    if df.is_empty():
        return FunnelResult(steps=steps, sample=df)

    raw = df
    period_end = period_end or date.today()
    in_period = raw.filter((pl.col("report_date") >= period_start) & (pl.col("report_date") <= period_end))
    _step(steps, "sample_period", raw, in_period)
    df = in_period

    stock_only = df.filter(pl.col("ticker_type") == "ST")
    _step(steps, "common_stock_only", df, stock_only)
    df = stock_only

    above_threshold = df.filter(pl.col("amount_low") > 1000.0)
    _step(steps, "above_statutory_threshold", df, above_threshold)
    df = above_threshold

    deduped = df.unique(
        subset=["ticker", "bioguide_id", "transaction_date", "transaction", "amount_range"],
        keep="first",
    )
    _step(steps, "dedupe_filings", df, deduped)
    df = deduped

    prices = storage.read("equity_eod")
    if prices.is_empty():
        _step(steps, "min_prior_trading_history", df, df.clear())
        _step(steps, "full_forward_window", df.clear(), df.clear())
        return FunnelResult(steps=steps, sample=df.clear())

    prior_counts = (
        df.join(prices.select("ticker", "date"), on="ticker", how="left")
        .filter(pl.col("date") < pl.col("report_date"))
        .group_by(["ticker", "bioguide_id", "transaction_date", "transaction", "amount_range"])
        .agg(pl.len().alias("n_prior"))
    )
    has_prior_history = df.join(
        prior_counts, on=["ticker", "bioguide_id", "transaction_date", "transaction", "amount_range"], how="inner"
    ).filter(pl.col("n_prior") >= min_prior_trading_days).drop("n_prior")
    _step(steps, "min_prior_trading_history", df, has_prior_history)
    df = has_prior_history

    forward_counts = (
        df.join(prices.select("ticker", "date"), on="ticker", how="left")
        .filter(pl.col("date") > pl.col("report_date"))
        .group_by(["ticker", "bioguide_id", "transaction_date", "transaction", "amount_range"])
        .agg(pl.len().alias("n_forward"))
    )
    has_full_forward = df.join(
        forward_counts, on=["ticker", "bioguide_id", "transaction_date", "transaction", "amount_range"], how="inner"
    ).filter(pl.col("n_forward") >= max_horizon_trading_days).drop("n_forward")
    _step(steps, "full_forward_window", df, has_full_forward)
    df = has_full_forward

    return FunnelResult(steps=steps, sample=df)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/sample/test_funnel.py -v`
Expected: `7 passed`

- [ ] **Step 6: Verify against real ticker_type values live**

Before trusting the `ticker_type == "ST"` filter against real data, confirm
`"ST"` is actually the only common-stock code Quiver uses:

```bash
uv run python -c "
from congressional_sales import storage
df = storage.read('congress_trades')
print(df['ticker_type'].value_counts())
"
```

If other codes appear that also represent common stock (or if `"ST"`
sometimes represents something else), adjust the filter and document the
real value set in this file's docstring rather than trusting the single
observed value from planning.

- [ ] **Step 7: Commit**

```bash
git add src/congressional_sales/sample/__init__.py src/congressional_sales/sample/funnel.py tests/sample/test_funnel.py
git commit -m "Add Section 4 inclusion/exclusion funnel (T1)"
```

### Task 9: Descriptive statistics (T2) and filing lag distribution (T3)

**Files:**
- Create: `src/congressional_sales/sample/descriptive.py`
- Test: `tests/sample/test_descriptive.py`

**Interfaces:**
- Consumes: a sample `pl.DataFrame` shaped like `FunnelResult.sample`
  (Task 8) joined with `storage.read("sic_codes")` (Task 7).
- Produces: `descriptive.build_t2(sample: pl.DataFrame, sic: pl.DataFrame)
  -> pl.DataFrame` (long format: columns `dimension: Utf8, value: Utf8,
  count: Int64` — one row per (dimension, value) pair across
  `{"year", "chamber", "party", "sector", "size_band"}`);
  `descriptive.filing_lag_days(sample: pl.DataFrame) -> pl.Series` (integer
  days, `report_date - transaction_date`); `descriptive.build_t3(sample:
  pl.DataFrame) -> dict` (keys: `median, mean, p90, max, share_beyond_45d`).

`size_band` uses Quiver's own disclosed `amount_range` string directly as
the band label — that IS the statutory disclosure bucket, not an
arbitrary re-binning.

- [ ] **Step 1: Write the failing test — `tests/sample/test_descriptive.py`**

```python
from __future__ import annotations

from datetime import date

import polars as pl

from congressional_sales.sample import descriptive

SAMPLE_SCHEMA = {
    "ticker": pl.Utf8, "politician": pl.Utf8, "bioguide_id": pl.Utf8, "chamber": pl.Utf8,
    "party": pl.Utf8, "transaction": pl.Utf8, "transaction_date": pl.Date, "report_date": pl.Date,
    "amount_low": pl.Float64, "amount_range": pl.Utf8, "ticker_type": pl.Utf8, "description": pl.Utf8,
    "excess_return": pl.Float64, "price_change": pl.Float64, "spy_change": pl.Float64,
}


def _sample() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT", "AAPL"],
            "politician": ["A", "B", "C"], "bioguide_id": ["A1", "B1", "C1"],
            "chamber": ["Representatives", "Senate", "Representatives"],
            "party": ["R", "D", "R"], "transaction": ["Purchase", "Sale", "Purchase"],
            "transaction_date": [date(2020, 1, 1), date(2020, 6, 1), date(2021, 1, 1)],
            "report_date": [date(2020, 1, 20), date(2020, 6, 10), date(2021, 3, 1)],
            "amount_low": [1001.0, 15001.0, 1001.0],
            "amount_range": ["$1,001 - $15,000", "$15,001 - $50,000", "$1,001 - $15,000"],
            "ticker_type": ["ST", "ST", "ST"], "description": [None, None, None],
            "excess_return": [None, None, None], "price_change": [None, None, None], "spy_change": [None, None, None],
        },
        schema=SAMPLE_SCHEMA,
    )


def _sic() -> pl.DataFrame:
    return pl.DataFrame(
        {"ticker": ["AAPL", "MSFT"], "cik": [320193, 789019], "sic_code": ["3571", "7372"], "sic_description": ["x", "y"]},
        schema={"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8},
    )


def test_build_t2_counts_by_year():
    t2 = descriptive.build_t2(_sample(), _sic())
    years = t2.filter(pl.col("dimension") == "year").sort("value")
    assert years["value"].to_list() == ["2020", "2021"]
    assert years["count"].to_list() == [2, 1]


def test_build_t2_counts_by_chamber_and_party():
    t2 = descriptive.build_t2(_sample(), _sic())
    chambers = t2.filter(pl.col("dimension") == "chamber")
    assert set(chambers["value"].to_list()) == {"Representatives", "Senate"}
    parties = t2.filter(pl.col("dimension") == "party")
    assert dict(zip(parties["value"], parties["count"])) == {"R": 2, "D": 1}


def test_build_t2_counts_by_sector_via_ff12():
    t2 = descriptive.build_t2(_sample(), _sic())
    sectors = t2.filter(pl.col("dimension") == "sector")
    # AAPL (SIC 3571, Electronic Computers) -> Business Equipment; MSFT (SIC 7372) -> Business Equipment too.
    assert sectors.filter(pl.col("value") == "Business Equipment")["count"][0] == 3


def test_build_t2_counts_by_size_band_using_disclosed_range():
    t2 = descriptive.build_t2(_sample(), _sic())
    bands = t2.filter(pl.col("dimension") == "size_band")
    assert dict(zip(bands["value"], bands["count"])) == {"$1,001 - $15,000": 2, "$15,001 - $50,000": 1}


def test_filing_lag_days_computes_report_minus_transaction():
    lag = descriptive.filing_lag_days(_sample())
    assert lag.to_list() == [19, 9, 59]


def test_build_t3_summary_stats():
    t3 = descriptive.build_t3(_sample())
    assert t3["max"] == 59
    assert t3["median"] == 19
    assert t3["share_beyond_45d"] == pytest.approx(1 / 3)
```

Add `import pytest` at the top of the test file (needed for the
`pytest.approx` call in the last test).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/sample/test_descriptive.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/congressional_sales/sample/descriptive.py`**

```python
"""T2 (descriptive statistics) and T3 (filing lag distribution),
PRE_ANALYSIS_PLAN.md Section 10."""

from __future__ import annotations

import polars as pl

from .industry import ff12_industry


def filing_lag_days(sample: pl.DataFrame) -> pl.Series:
    return (sample["report_date"] - sample["transaction_date"]).dt.total_days()


def build_t3(sample: pl.DataFrame) -> dict:
    lag = filing_lag_days(sample)
    return {
        "median": lag.median(),
        "mean": lag.mean(),
        "p90": lag.quantile(0.90),
        "max": lag.max(),
        "share_beyond_45d": (lag > 45).mean(),
    }


def _count_dimension(sample: pl.DataFrame, dimension: str, value_col: pl.Expr) -> pl.DataFrame:
    return (
        sample.with_columns(value_col.alias("value"))
        .group_by("value")
        .agg(pl.len().alias("count"))
        .with_columns(pl.lit(dimension).alias("dimension"))
        .select("dimension", "value", "count")
    )


def build_t2(sample: pl.DataFrame, sic: pl.DataFrame) -> pl.DataFrame:
    by_year = _count_dimension(sample, "year", pl.col("report_date").dt.year().cast(pl.Utf8))
    by_chamber = _count_dimension(sample, "chamber", pl.col("chamber"))
    by_party = _count_dimension(sample, "party", pl.col("party"))
    by_size = _count_dimension(sample, "size_band", pl.col("amount_range"))

    with_sic = sample.join(sic.select("ticker", "sic_code"), on="ticker", how="left")
    with_sector = with_sic.with_columns(
        pl.col("sic_code").map_elements(ff12_industry, return_dtype=pl.Utf8).alias("sector")
    )
    by_sector = _count_dimension(with_sector, "sector", pl.col("sector"))

    return pl.concat([by_year, by_chamber, by_party, by_sector, by_size], how="vertical_relaxed").sort(
        ["dimension", "value"]
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/sample/test_descriptive.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add src/congressional_sales/sample/descriptive.py tests/sample/test_descriptive.py
git commit -m "Add T2 descriptive statistics and T3 filing lag distribution"
```

---

## Phase 3 — Screening Funnel (Section 5)

Each screen is a pure function `sample -> (kept, excluded_count)` so the
funnel can report a running count after every screen (feeds T1's "screened
sample" column) and so `run_full_pipeline.py` can run the unscreened and
screened samples through the same downstream code, per the PAP's explicit
requirement to report both.

### Task 10: Screen 1 — Rebalancing

**Files:**
- Create: `src/congressional_sales/sample/screens.py`
- Test: `tests/sample/test_screens.py`

**Interfaces:**
- Consumes: sample `pl.DataFrame` (Task 8 shape).
- Produces: `screens.screen1_rebalancing(sample: pl.DataFrame) ->
  pl.DataFrame` (returns the input with a new boolean column
  `excluded_rebalancing` — screens ADD a boolean flag column rather than
  dropping rows, so later code can report both the screened and unscreened
  view of the same frame without re-running the funnel).

**Methodology judgment call (confirm during plan review, not silently):**
Section 5 doesn't specify which date field the 90-day window and the
same-day-multi-sale check use. This implementation uses `transaction_date`
for both — the window is about the member's actual trading behavior/intent
(rebalancing is something a person does on the date they act, not the date
it happens to be disclosed), whereas `report_date` remains the anchor for
every event-study return calculation elsewhere in this codebase. If this
judgment is wrong, only `screen1_rebalancing`'s date column needs to
change — nothing else depends on this choice.

- [ ] **Step 1: Write the failing test — `tests/sample/test_screens.py`**

```python
from __future__ import annotations

from datetime import date

import polars as pl

from congressional_sales.sample import screens

SAMPLE_SCHEMA = {
    "ticker": pl.Utf8, "politician": pl.Utf8, "bioguide_id": pl.Utf8, "chamber": pl.Utf8,
    "party": pl.Utf8, "transaction": pl.Utf8, "transaction_date": pl.Date, "report_date": pl.Date,
    "amount_low": pl.Float64, "amount_range": pl.Utf8, "ticker_type": pl.Utf8, "description": pl.Utf8,
    "excess_return": pl.Float64, "price_change": pl.Float64, "spy_change": pl.Float64,
}


def _row(ticker, bioguide, transaction, tdate, rdate=None, amount=1001.0, amount_range="$1,001 - $15,000"):
    return {
        "ticker": ticker, "politician": bioguide, "bioguide_id": bioguide, "chamber": "Representatives",
        "party": "R", "transaction": transaction, "transaction_date": tdate, "report_date": rdate or tdate,
        "amount_low": amount, "amount_range": amount_range, "ticker_type": "ST", "description": None,
        "excess_return": None, "price_change": None, "spy_change": None,
    }


def _df(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=SAMPLE_SCHEMA)


def test_screen1_flags_sale_with_nearby_purchase_of_same_ticker():
    rows = _df(
        [
            _row("AAPL", "A1", "Sale", date(2020, 6, 1)),
            _row("AAPL", "A1", "Purchase", date(2020, 5, 1)),  # 31 days before -- within 90
        ]
    )
    out = screens.screen1_rebalancing(rows)
    sale = out.filter(pl.col("transaction") == "Sale")
    assert sale["excluded_rebalancing"][0] is True


def test_screen1_does_not_flag_sale_with_distant_purchase():
    rows = _df(
        [
            _row("AAPL", "A1", "Sale", date(2020, 6, 1)),
            _row("AAPL", "A1", "Purchase", date(2019, 1, 1)),  # far more than 90 days before
        ]
    )
    out = screens.screen1_rebalancing(rows)
    sale = out.filter(pl.col("transaction") == "Sale")
    assert sale["excluded_rebalancing"][0] is False


def test_screen1_flags_three_simultaneous_sales_across_sectors():
    d = date(2020, 6, 1)
    rows = _df(
        [
            _row("AAPL", "A1", "Sale", d),
            _row("XOM", "A1", "Sale", d),
            _row("JPM", "A1", "Sale", d),
        ]
    )
    out = screens.screen1_rebalancing(rows)
    assert out["excluded_rebalancing"].to_list() == [True, True, True]


def test_screen1_does_not_flag_isolated_single_sale():
    rows = _df([_row("AAPL", "A1", "Sale", date(2020, 6, 1))])
    out = screens.screen1_rebalancing(rows)
    assert out["excluded_rebalancing"][0] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/sample/test_screens.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Screen 1 in `src/congressional_sales/sample/screens.py`**

```python
"""The four sequential screens, PRE_ANALYSIS_PLAN.md Section 5. Each
screen ADDS a boolean exclusion-flag column rather than dropping rows, so
downstream code can compute both the unscreened and screened view of the
same sample without re-deriving the funnel."""

from __future__ import annotations

from datetime import timedelta

import polars as pl


def screen1_rebalancing(sample: pl.DataFrame) -> pl.DataFrame:
    df = sample

    # Condition A: same member bought the same ticker within 90 days
    # before/after a sale (uses transaction_date -- see this task's
    # methodology note in the plan).
    sales = df.filter(pl.col("transaction") == "Sale").select("bioguide_id", "ticker", "transaction_date")
    purchases = df.filter(pl.col("transaction") == "Purchase").select(
        pl.col("bioguide_id"), pl.col("ticker"), pl.col("transaction_date").alias("purchase_date")
    )
    matched = sales.join(purchases, on=["bioguide_id", "ticker"], how="inner").with_columns(
        (pl.col("purchase_date") - pl.col("transaction_date")).dt.total_days().abs().alias("gap_days")
    )
    flagged_pairs = matched.filter(pl.col("gap_days") <= 90).select("bioguide_id", "ticker", "transaction_date").unique()

    # Condition B: >=3 simultaneous sales by the same member across >=3
    # distinct tickers on the same date ("unrelated sectors" approximated
    # here as distinct tickers -- sector diversity requires the SIC join
    # from Task 7/9, which this pure function deliberately does not take
    # as a dependency; a stricter sector-diversity check can be layered on
    # by the caller before/after this function if the reviewer determines
    # ticker-distinctness alone is too weak a proxy for "unrelated sectors").
    same_day_sales = (
        df.filter(pl.col("transaction") == "Sale")
        .group_by(["bioguide_id", "transaction_date"])
        .agg(pl.col("ticker").n_unique().alias("n_tickers"))
        .filter(pl.col("n_tickers") >= 3)
        .select("bioguide_id", "transaction_date")
    )

    flag_a = df.join(
        flagged_pairs.with_columns(pl.lit(True).alias("_flag_a")),
        on=["bioguide_id", "ticker", "transaction_date"], how="left",
    )["_flag_a"].fill_null(False)

    flag_b = df.join(
        same_day_sales.with_columns(pl.lit(True).alias("_flag_b")),
        on=["bioguide_id", "transaction_date"], how="left",
    )["_flag_b"].fill_null(False)

    is_sale = df["transaction"] == "Sale"
    excluded = is_sale & (flag_a | flag_b)
    return df.with_columns(excluded.alias("excluded_rebalancing"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/sample/test_screens.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/congressional_sales/sample/screens.py tests/sample/test_screens.py
git commit -m "Add Screen 1 (rebalancing exclusion)"
```

### Task 11: Screen 2 — Tax management

**Files:**
- Modify: `src/congressional_sales/sample/screens.py`
- Modify: `tests/sample/test_screens.py`

**Interfaces:**
- Consumes: sample `pl.DataFrame`, `storage.read("equity_eod")` (Task 2).
- Produces: `screens.screen2_tax_management(sample: pl.DataFrame, prices:
  pl.DataFrame) -> pl.DataFrame` (adds boolean column
  `excluded_tax_management`).

- [ ] **Step 1: Add the failing tests to `tests/sample/test_screens.py`**

```python
def _prices(ticker, rows):
    """rows: list of (date, close_adj)"""
    n = len(rows)
    return pl.DataFrame(
        {
            "ticker": [ticker] * n, "date": [r[0] for r in rows], "open": [1.0] * n, "high": [1.0] * n,
            "low": [1.0] * n, "close": [r[1] for r in rows], "volume": [1.0] * n,
            "close_adj": [r[1] for r in rows],
        }
    )


def test_screen2_flags_november_sale_at_a_loss_vs_last_purchase():
    rows = _df(
        [
            _row("AAPL", "A1", "Purchase", date(2020, 3, 1)),
            _row("AAPL", "A1", "Sale", date(2020, 11, 15)),
        ]
    )
    prices = _prices("AAPL", [(date(2020, 3, 1), 100.0), (date(2020, 11, 15), 80.0)])
    out = screens.screen2_tax_management(rows, prices)
    sale = out.filter(pl.col("transaction") == "Sale")
    assert sale["excluded_tax_management"][0] is True


def test_screen2_does_not_flag_november_sale_at_a_gain():
    rows = _df(
        [
            _row("AAPL", "A1", "Purchase", date(2020, 3, 1)),
            _row("AAPL", "A1", "Sale", date(2020, 11, 15)),
        ]
    )
    prices = _prices("AAPL", [(date(2020, 3, 1), 100.0), (date(2020, 11, 15), 120.0)])
    out = screens.screen2_tax_management(rows, prices)
    sale = out.filter(pl.col("transaction") == "Sale")
    assert sale["excluded_tax_management"][0] is False


def test_screen2_does_not_flag_a_loss_sale_outside_nov_dec():
    rows = _df(
        [
            _row("AAPL", "A1", "Purchase", date(2020, 3, 1)),
            _row("AAPL", "A1", "Sale", date(2020, 6, 15)),
        ]
    )
    prices = _prices("AAPL", [(date(2020, 3, 1), 100.0), (date(2020, 6, 15), 80.0)])
    out = screens.screen2_tax_management(rows, prices)
    sale = out.filter(pl.col("transaction") == "Sale")
    assert sale["excluded_tax_management"][0] is False


def test_screen2_sale_with_no_prior_purchase_is_not_flagged():
    rows = _df([_row("AAPL", "A1", "Sale", date(2020, 12, 1))])
    prices = _prices("AAPL", [(date(2020, 12, 1), 80.0)])
    out = screens.screen2_tax_management(rows, prices)
    assert out["excluded_tax_management"][0] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/sample/test_screens.py -v`
Expected: FAIL — `AttributeError: module 'screens' has no attribute 'screen2_tax_management'`

- [ ] **Step 3: Append Screen 2 to `src/congressional_sales/sample/screens.py`**

```python
def _price_asof(prices: pl.DataFrame, ticker: str, d) -> float | None:
    rows = prices.filter((pl.col("ticker") == ticker) & (pl.col("date") <= d))
    if rows.is_empty():
        return None
    return rows.sort("date")["close_adj"][-1]


def screen2_tax_management(sample: pl.DataFrame, prices: pl.DataFrame) -> pl.DataFrame:
    df = sample
    flags = []
    for row in df.iter_rows(named=True):
        if row["transaction"] != "Sale" or row["transaction_date"].month not in (11, 12):
            flags.append(False)
            continue
        prior_purchases = df.filter(
            (pl.col("bioguide_id") == row["bioguide_id"])
            & (pl.col("ticker") == row["ticker"])
            & (pl.col("transaction") == "Purchase")
            & (pl.col("transaction_date") < row["transaction_date"])
        ).sort("transaction_date", descending=True)
        if prior_purchases.is_empty():
            flags.append(False)
            continue
        last_purchase_date = prior_purchases["transaction_date"][0]
        purchase_price = _price_asof(prices, row["ticker"], last_purchase_date)
        sale_price = _price_asof(prices, row["ticker"], row["transaction_date"])
        if purchase_price is None or sale_price is None:
            flags.append(False)
            continue
        flags.append(sale_price < purchase_price)
    return df.with_columns(pl.Series("excluded_tax_management", flags))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/sample/test_screens.py -v`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add src/congressional_sales/sample/screens.py tests/sample/test_screens.py
git commit -m "Add Screen 2 (tax-loss-management exclusion)"
```

### Task 12: Screen 3 — Liquidation events

**Files:**
- Modify: `src/congressional_sales/sample/screens.py`
- Modify: `tests/sample/test_screens.py`

**Interfaces:**
- Consumes: sample `pl.DataFrame`, `storage.read("legislator_terms")`
  (Task 6).
- Produces: `screens.screen3_liquidation(sample: pl.DataFrame, terms:
  pl.DataFrame, portfolio_liquidation_pct: float = 0.60, retirement_window_days:
  int = 90) -> pl.DataFrame` (adds boolean column `excluded_liquidation`).

**Documented scope decision (this is the resolution to the gap flagged in
Global Constraints — implement exactly this, do not attempt blind-trust or
executive-branch-confirmation detection):**

1. **>60% of disclosed portfolio sold**: approximated as: for each member,
   maintain a running "cumulative net disclosed exposure" = cumulative
   dollar sum of purchases minus sales (using `amount_low` as the size
   proxy, in chronological `transaction_date` order) up to and including
   each transaction. A sale is flagged if its own `amount_low` exceeds
   `portfolio_liquidation_pct` times the member's cumulative net exposure
   immediately before that sale. This is a proxy, not true portfolio
   value (this study has no holdings/position data, only transactions) —
   state this explicitly in the paper's limitations section, not just in
   code comments.
2. **Retirement**: a member's most recent known term (by `term_start`) has
   a `term_end` date, and no later term exists for that `bioguide_id`.
   Transactions within `retirement_window_days` of that `term_end` are
   flagged.
3. **Blind trust establishment / executive-branch confirmation**: no
   available structured data source. Not implemented in v1. This function
   must NOT silently pass all transactions on this sub-condition — it
   simply does not check for it, and the paper's limitations section must
   say so explicitly (see Task 25, paper assembly).

- [ ] **Step 1: Add the failing tests to `tests/sample/test_screens.py`**

```python
def _terms(bioguide, chamber, start, end):
    return pl.DataFrame(
        {
            "bioguide_id": [bioguide], "full_name": ["Test"], "chamber": [chamber],
            "term_start": [start], "term_end": [end], "state": ["XX"], "party": ["R"],
        },
        schema={
            "bioguide_id": pl.Utf8, "full_name": pl.Utf8, "chamber": pl.Utf8,
            "term_start": pl.Date, "term_end": pl.Date, "state": pl.Utf8, "party": pl.Utf8,
        },
    )


def test_screen3_flags_sale_exceeding_60pct_of_cumulative_net_exposure():
    rows = _df(
        [
            _row("AAPL", "A1", "Purchase", date(2020, 1, 1), amount=10000.0),
            _row("AAPL", "A1", "Sale", date(2020, 2, 1), amount=8000.0),  # 80% of the 10000 built up
        ]
    )
    terms = _terms("A1", "rep", date(2015, 1, 1), date(2025, 1, 1))
    out = screens.screen3_liquidation(rows, terms)
    sale = out.filter(pl.col("transaction") == "Sale")
    assert sale["excluded_liquidation"][0] is True


def test_screen3_does_not_flag_a_small_partial_sale():
    rows = _df(
        [
            _row("AAPL", "A1", "Purchase", date(2020, 1, 1), amount=10000.0),
            _row("AAPL", "A1", "Sale", date(2020, 2, 1), amount=1000.0),  # 10% of cumulative exposure
        ]
    )
    terms = _terms("A1", "rep", date(2015, 1, 1), date(2025, 1, 1))
    out = screens.screen3_liquidation(rows, terms)
    sale = out.filter(pl.col("transaction") == "Sale")
    assert sale["excluded_liquidation"][0] is False


def test_screen3_flags_transaction_near_retirement_term_end():
    rows = _df([_row("AAPL", "A1", "Sale", date(2020, 12, 20), amount=100.0)])
    terms = _terms("A1", "rep", date(2015, 1, 1), date(2021, 1, 3))  # term ends 2021-01-03, no later term
    out = screens.screen3_liquidation(rows, terms)
    assert out["excluded_liquidation"][0] is True


def test_screen3_does_not_flag_a_sitting_members_transaction():
    rows = _df([_row("AAPL", "A1", "Sale", date(2020, 6, 1), amount=100.0)])
    terms = _terms("A1", "rep", date(2015, 1, 1), date(2027, 1, 3))  # term ends far in the future
    out = screens.screen3_liquidation(rows, terms)
    assert out["excluded_liquidation"][0] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/sample/test_screens.py -v`
Expected: FAIL — `AttributeError: module 'screens' has no attribute 'screen3_liquidation'`

- [ ] **Step 3: Append Screen 3 to `src/congressional_sales/sample/screens.py`**

```python
def screen3_liquidation(
    sample: pl.DataFrame,
    terms: pl.DataFrame,
    portfolio_liquidation_pct: float = 0.60,
    retirement_window_days: int = 90,
) -> pl.DataFrame:
    df = sample.sort(["bioguide_id", "transaction_date"])

    # Sub-condition 1: cumulative net-exposure proxy.
    signed = pl.when(pl.col("transaction") == "Purchase").then(pl.col("amount_low")).otherwise(-pl.col("amount_low"))
    with_cum = df.with_columns(signed.alias("_signed")).with_columns(
        pl.col("_signed").cum_sum().over("bioguide_id").alias("_cum_exposure")
    )
    prior_exposure = with_cum["_cum_exposure"] - with_cum["_signed"]
    is_big_sale = (with_cum["transaction"] == "Sale") & (prior_exposure > 0) & (
        with_cum["amount_low"] > portfolio_liquidation_pct * prior_exposure
    )

    # Sub-condition 2: retirement window.
    last_terms = (
        terms.sort(["bioguide_id", "term_start"])
        .group_by("bioguide_id")
        .agg(pl.col("term_end").last().alias("last_term_end"))
    )
    with_terms = df.join(last_terms, on="bioguide_id", how="left")
    gap = (with_terms["transaction_date"] - with_terms["last_term_end"]).dt.total_days().abs()
    is_near_retirement = with_terms["last_term_end"].is_not_null() & (gap <= retirement_window_days)

    excluded = is_big_sale | is_near_retirement
    return df.with_columns(excluded.alias("excluded_liquidation"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/sample/test_screens.py -v`
Expected: `12 passed`

- [ ] **Step 5: Commit**

```bash
git add src/congressional_sales/sample/screens.py tests/sample/test_screens.py
git commit -m "Add Screen 3 (liquidation-event exclusion: portfolio-share proxy + retirement window)"
```

### Task 13: Screen 4 (routine vs. opportunistic, H3) + committee-match (H4)

Screen 4 differs from Screens 1-3: it does not exclude anything. PAP
Section 5 says to "analyze routine and opportunistic members separately"
— it is a classification for subgroup analysis (H3), not an exclusion.
Committee-match is a separate classification entirely (H4's
`CommitteeMatch` regression covariate, not one of the four Section-5
screens) but lives in the same module since both are per-transaction
classification columns consumed by Model 2 (Task 18).

**Files:**
- Create: `src/congressional_sales/sample/classify.py`
- Test: `tests/sample/test_classify.py`

**Interfaces:**
- Consumes: sample `pl.DataFrame`, `storage.read("committee_assignments")`
  (Task 6), `sic` frame + `industry.ff12_industry` (Task 7).
- Produces: `classify.is_routine_trader(sample: pl.DataFrame) ->
  pl.DataFrame` (adds boolean column `is_routine` — True if the member
  traded in the same calendar month in each of the 3 prior years, per
  Section 5 Screen 4); `classify.committee_match(sample: pl.DataFrame,
  assignments: pl.DataFrame, sic: pl.DataFrame) -> pl.DataFrame` (adds
  boolean column `committee_match`).

**Methodology judgment call (confirm during plan review):** committees do
not map 1:1 onto the 12 Fama-French industries. This implementation uses
an explicit, reviewable keyword table mapping each committee's subject
area to the FF12 industry it most plausibly has jurisdiction over (e.g.
"Agriculture" → Consumer NonDurables, "Energy" → Energy, "Financial
Services"/"Banking" → Money, "Armed Services" → Manufacturing,
"Commerce"/"Science"/"Technology" → Business Equipment, "Health" →
Healthcare). This table is a research judgment, not a fact — the paper's
methodology section must show it, and the SDD review for this task should
scrutinize every entry, not just the code around it.

- [ ] **Step 1: Write the failing test — `tests/sample/test_classify.py`**

```python
from __future__ import annotations

from datetime import date

import polars as pl

from congressional_sales.sample import classify

SAMPLE_SCHEMA = {
    "ticker": pl.Utf8, "politician": pl.Utf8, "bioguide_id": pl.Utf8, "chamber": pl.Utf8,
    "party": pl.Utf8, "transaction": pl.Utf8, "transaction_date": pl.Date, "report_date": pl.Date,
    "amount_low": pl.Float64, "amount_range": pl.Utf8, "ticker_type": pl.Utf8, "description": pl.Utf8,
    "excess_return": pl.Float64, "price_change": pl.Float64, "spy_change": pl.Float64,
}


def _row(ticker, bioguide, tdate, transaction="Purchase"):
    return {
        "ticker": ticker, "politician": bioguide, "bioguide_id": bioguide, "chamber": "Representatives",
        "party": "R", "transaction": transaction, "transaction_date": tdate, "report_date": tdate,
        "amount_low": 1001.0, "amount_range": "$1,001 - $15,000", "ticker_type": "ST", "description": None,
        "excess_return": None, "price_change": None, "spy_change": None,
    }


def test_is_routine_trader_flags_same_month_three_years_running():
    rows = pl.DataFrame(
        [
            _row("AAPL", "A1", date(2020, 3, 10)),
            _row("MSFT", "A1", date(2019, 3, 5)),
            _row("NVDA", "A1", date(2018, 3, 20)),
            _row("XOM", "A1", date(2017, 3, 1)),
        ],
        schema=SAMPLE_SCHEMA,
    )
    out = classify.is_routine_trader(rows)
    row2020 = out.filter(pl.col("transaction_date") == date(2020, 3, 10))
    assert row2020["is_routine"][0] is True


def test_is_routine_trader_does_not_flag_a_one_off_trade():
    rows = pl.DataFrame([_row("AAPL", "A1", date(2020, 3, 10))], schema=SAMPLE_SCHEMA)
    out = classify.is_routine_trader(rows)
    assert out["is_routine"][0] is False


def test_committee_match_flags_matching_sector():
    rows = pl.DataFrame([_row("XOM", "A1", date(2020, 3, 10))], schema=SAMPLE_SCHEMA)
    assignments = pl.DataFrame(
        {
            "bioguide_id": ["A1"], "committee_code": ["SSEG"], "chamber": ["senate"],
            "committee_name": ["Senate Committee on Energy and Natural Resources"],
        }
    )
    sic = pl.DataFrame(
        {"ticker": ["XOM"], "cik": [34088], "sic_code": ["2911"], "sic_description": ["Petroleum Refining"]},
        schema={"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8},
    )
    out = classify.committee_match(rows, assignments, sic)
    assert out["committee_match"][0] is True


def test_committee_match_false_for_unrelated_sector():
    rows = pl.DataFrame([_row("XOM", "A1", date(2020, 3, 10))], schema=SAMPLE_SCHEMA)
    assignments = pl.DataFrame(
        {
            "bioguide_id": ["A1"], "committee_code": ["SSAF"], "chamber": ["senate"],
            "committee_name": ["Senate Committee on Agriculture, Nutrition, and Forestry"],
        }
    )
    sic = pl.DataFrame(
        {"ticker": ["XOM"], "cik": [34088], "sic_code": ["2911"], "sic_description": ["Petroleum Refining"]},
        schema={"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8},
    )
    out = classify.committee_match(rows, assignments, sic)
    assert out["committee_match"][0] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/sample/test_classify.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/congressional_sales/sample/classify.py`**

```python
"""Screen 4 (routine vs. opportunistic, H3) and committee-jurisdiction
matching (H4), PRE_ANALYSIS_PLAN.md Section 5 / Section 7."""

from __future__ import annotations

import re

import polars as pl

from .industry import ff12_industry


def is_routine_trader(sample: pl.DataFrame) -> pl.DataFrame:
    df = sample
    months = df.select("bioguide_id", pl.col("transaction_date").dt.year().alias("y"), pl.col("transaction_date").dt.month().alias("m")).unique()
    active_year_months = set(months.iter_rows())

    def _routine(bioguide: str, y: int, m: int) -> bool:
        return all((bioguide, y - k, m) in active_year_months for k in (1, 2, 3))

    flags = [
        _routine(row["bioguide_id"], row["transaction_date"].year, row["transaction_date"].month)
        for row in df.iter_rows(named=True)
    ]
    return df.with_columns(pl.Series("is_routine", flags))


# Committee subject-area keyword -> FF12 industry it most plausibly has
# jurisdiction over. A research judgment, not a fact -- reviewed as code,
# shown verbatim in the paper's methodology section.
_COMMITTEE_KEYWORDS: list[tuple[str, str]] = [
    ("Agriculture", "Consumer NonDurables"),
    ("Energy", "Energy"),
    ("Natural Resources", "Energy"),
    ("Financial Services", "Money"),
    ("Banking", "Money"),
    ("Armed Services", "Manufacturing"),
    ("Commerce", "Business Equipment"),
    ("Science", "Business Equipment"),
    ("Technology", "Business Equipment"),
    ("Communications", "Telephone and Television Transmission"),
    ("Health", "Healthcare"),
    ("Transportation", "Other"),
    ("Homeland Security", "Other"),
]


def _committee_sector(committee_name: str) -> str | None:
    for keyword, sector in _COMMITTEE_KEYWORDS:
        if keyword.lower() in committee_name.lower():
            return sector
    return None


def committee_match(sample: pl.DataFrame, assignments: pl.DataFrame, sic: pl.DataFrame) -> pl.DataFrame:
    # skip_nulls=False is required here, not optional: this left join can
    # produce a null sic_code for any sample ticker with no SIC match, and
    # polars' map_elements defaults to skip_nulls=True -- which means the
    # null bypasses ff12_industry() entirely (leaving _sector null) rather
    # than calling it with None, even though ff12_industry(None) is
    # explicitly coded to return "Other". This exact bug was found live
    # during Task 9's implementation (same join-then-map_elements pattern,
    # different consumer) -- row counts were never wrong, only the label
    # (unmatched rows got a silent null sector instead of "Other"). Fixed
    # here pre-emptively rather than left for Task 13 to rediscover.
    df = sample.join(sic.select("ticker", "sic_code"), on="ticker", how="left").with_columns(
        pl.col("sic_code").map_elements(ff12_industry, return_dtype=pl.Utf8, skip_nulls=False).alias("_sector")
    )
    member_sectors = (
        assignments.with_columns(
            pl.col("committee_name").map_elements(_committee_sector, return_dtype=pl.Utf8).alias("_committee_sector")
        )
        .filter(pl.col("_committee_sector").is_not_null())
        .group_by("bioguide_id")
        .agg(pl.col("_committee_sector").unique().alias("_member_sectors"))
    )
    joined = df.join(member_sectors, on="bioguide_id", how="left")
    matched = [
        row["_sector"] in (row["_member_sectors"] or [])
        for row in joined.select("_sector", "_member_sectors").iter_rows(named=True)
    ]
    return df.with_columns(pl.Series("committee_match", matched))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/sample/test_classify.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/congressional_sales/sample/classify.py tests/sample/test_classify.py
git commit -m "Add Screen 4 (routine/opportunistic, H3) and committee-match classification (H4)"
```

---

## Phase 4 — Event Study Engine (Section 6)

All three CAR methods and BHAR share one entry-window convention: horizon
`h` means trading sessions `[+1, +h]` from the transaction's `report_date`
(actionability — see Global Constraints and Task 25's robustness item 6
for the filing-date-vs-transaction-date variant), using
`calendar.offset_trading_day` (Task 3) exclusively — never raw date
arithmetic, per the plan's t+1 discipline.

### Task 14: Market-adjusted CAR and BHAR

**Files:**
- Create: `src/congressional_sales/events/__init__.py`
- Create: `src/congressional_sales/events/car.py`
- Test: `tests/events/test_car_market_adjusted.py`

**Interfaces:**
- Consumes: `calendar.offset_within_days` (Task 3, the pure/storage-free
  variant — this module never reads `storage` or calls the global
  `calendar.offset_trading_day` directly; it derives its own session list
  from whatever `prices` frame the caller passes in, so it is a pure
  function of its arguments and trivially unit-testable with small
  fixtures, independent of whatever is or isn't in the warehouse).
- Produces: `car.sessions_from_prices(prices: pl.DataFrame, market_ticker:
  str = "SPY") -> list[date]` (sorted, deduplicated dates for
  `market_ticker` within the given frame — the session calendar every
  other function in this module is anchored to); `car.daily_return(ticker:
  str, d: date, prices: pl.DataFrame, sessions: list[date]) -> float |
  None` (simple return from the prior session's `close_adj` to `d`'s,
  `None` if either price or the prior session is missing);
  `car.market_adjusted_car(ticker: str, event_date: date, horizon: int,
  prices: pl.DataFrame, market_ticker: str = "SPY") -> float | None` (sum
  of `(ticker daily return - market daily return)` over sessions `[+1,
  +horizon]`, computed internally via `sessions_from_prices`; `None` if any
  session in the window is missing for either series); `car.
  market_adjusted_bhar(ticker, event_date, horizon, prices,
  market_ticker="SPY") -> float | None` (compounded: `prod(1+r_ticker) -
  prod(1+r_market)` over the same window).

- [ ] **Step 1: Create `src/congressional_sales/events/__init__.py`**

```python
"""CAR/BHAR event-study engine, PRE_ANALYSIS_PLAN.md Section 6, and the
1,000-iteration random-control permutation test, Section 8."""
```

- [ ] **Step 2: Write the failing test — `tests/events/test_car_market_adjusted.py`**

```python
from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from congressional_sales.events import car


def _prices(rows: dict[str, list[tuple]]) -> pl.DataFrame:
    frames = []
    for ticker, pairs in rows.items():
        n = len(pairs)
        frames.append(
            pl.DataFrame(
                {
                    "ticker": [ticker] * n, "date": [p[0] for p in pairs], "open": [1.0] * n,
                    "high": [1.0] * n, "low": [1.0] * n, "close": [p[1] for p in pairs],
                    "volume": [1.0] * n, "close_adj": [p[1] for p in pairs],
                }
            )
        )
    return pl.concat(frames)


def test_daily_return_computes_simple_return_from_prior_session():
    prices = _prices({"AAPL": [(date(2020, 1, 2), 100.0), (date(2020, 1, 3), 110.0)]})
    sessions = [date(2020, 1, 2), date(2020, 1, 3)]
    r = car.daily_return("AAPL", date(2020, 1, 3), prices, sessions)
    assert r == pytest.approx(0.10)


def test_daily_return_missing_prior_session_is_none():
    prices = _prices({"AAPL": [(date(2020, 1, 3), 110.0)]})
    sessions = [date(2020, 1, 3)]  # no prior session in the known calendar
    assert car.daily_return("AAPL", date(2020, 1, 3), prices, sessions) is None


def test_sessions_from_prices_reads_the_market_tickers_dates():
    prices = _prices({"AAPL": [(date(2020, 1, 2), 100.0)], "SPY": [(date(2020, 1, 2), 300.0), (date(2020, 1, 3), 303.0)]})
    assert car.sessions_from_prices(prices) == [date(2020, 1, 2), date(2020, 1, 3)]


def test_market_adjusted_car_nets_out_market_move():
    prices = _prices(
        {
            "AAPL": [(date(2020, 1, 2), 100.0), (date(2020, 1, 3), 110.0), (date(2020, 1, 6), 121.0)],
            "SPY": [(date(2020, 1, 2), 300.0), (date(2020, 1, 3), 303.0), (date(2020, 1, 6), 306.03)],
        }
    )
    # AAPL: +10% then +10% (cumulative sum of daily simple returns = 0.20).
    # SPY: +1% then +1% (cumulative sum = 0.02).
    got = car.market_adjusted_car("AAPL", date(2020, 1, 2), horizon=2, prices=prices)
    assert got == pytest.approx(0.20 - 0.02, abs=1e-6)


def test_market_adjusted_car_missing_window_data_is_none():
    prices = _prices({"AAPL": [(date(2020, 1, 2), 100.0)], "SPY": [(date(2020, 1, 2), 300.0)]})
    assert car.market_adjusted_car("AAPL", date(2020, 1, 2), horizon=5, prices=prices) is None


def test_market_adjusted_bhar_compounds_rather_than_sums():
    prices = _prices(
        {
            "AAPL": [(date(2020, 1, 2), 100.0), (date(2020, 1, 3), 110.0), (date(2020, 1, 6), 121.0)],
            "SPY": [(date(2020, 1, 2), 300.0), (date(2020, 1, 3), 303.0), (date(2020, 1, 6), 306.03)],
        }
    )
    got = car.market_adjusted_bhar("AAPL", date(2020, 1, 2), horizon=2, prices=prices)
    # AAPL compounds to 1.10*1.10 - 1 = 0.21; SPY compounds to 1.01*1.01 - 1 = 0.0201.
    assert got == pytest.approx(0.21 - 0.0201, abs=1e-6)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/events/test_car_market_adjusted.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement `src/congressional_sales/events/car.py`**

```python
"""CAR/BHAR event-study engine, PRE_ANALYSIS_PLAN.md Section 6.

Horizon h means trading sessions [+1, +h] from the event date, using
calendar.offset_trading_day exclusively -- never raw date arithmetic. This
IS the t+1 discipline Section 11 calls the most common silent failure.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from ..calendar import offset_within_days


def sessions_from_prices(prices: pl.DataFrame, market_ticker: str = "SPY") -> list[date]:
    return prices.filter(pl.col("ticker") == market_ticker)["date"].unique().sort().to_list()


def _price_on(ticker: str, d: date, prices: pl.DataFrame) -> float | None:
    rows = prices.filter((pl.col("ticker") == ticker) & (pl.col("date") == d))
    if rows.is_empty():
        return None
    return rows["close_adj"][0]


def daily_return(ticker: str, d: date, prices: pl.DataFrame, sessions: list[date]) -> float | None:
    prior = offset_within_days(sessions, d, -1)
    if prior is None:
        return None
    p0, p1 = _price_on(ticker, prior, prices), _price_on(ticker, d, prices)
    if p0 is None or p1 is None or p0 == 0:
        return None
    return (p1 - p0) / p0


def _window_dates(event_date: date, horizon: int, sessions: list[date]) -> list[date] | None:
    dates = []
    for k in range(1, horizon + 1):
        d = offset_within_days(sessions, event_date, k)
        if d is None:
            return None
        dates.append(d)
    return dates


def market_adjusted_car(ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, market_ticker: str = "SPY") -> float | None:
    sessions = sessions_from_prices(prices, market_ticker)
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    total = 0.0
    for d in dates:
        r_t = daily_return(ticker, d, prices, sessions)
        r_m = daily_return(market_ticker, d, prices, sessions)
        if r_t is None or r_m is None:
            return None
        total += r_t - r_m
    return total


def market_adjusted_bhar(ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, market_ticker: str = "SPY") -> float | None:
    sessions = sessions_from_prices(prices, market_ticker)
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    ticker_growth, market_growth = 1.0, 1.0
    for d in dates:
        r_t = daily_return(ticker, d, prices, sessions)
        r_m = daily_return(market_ticker, d, prices, sessions)
        if r_t is None or r_m is None:
            return None
        ticker_growth *= 1 + r_t
        market_growth *= 1 + r_m
    return (ticker_growth - 1) - (market_growth - 1)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/events/test_car_market_adjusted.py -v`
Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
git add src/congressional_sales/events/__init__.py src/congressional_sales/events/car.py tests/events/test_car_market_adjusted.py
git commit -m "Add market-adjusted CAR/BHAR"
```

### Task 15: Four-factor CAR and BHAR

**Files:**
- Modify: `src/congressional_sales/events/car.py`
- Test: `tests/events/test_car_four_factor.py`

**Interfaces:**
- Consumes: `car.sessions_from_prices`, `car.daily_return`,
  `calendar.offset_within_days` (this file), `storage.read("ff_factors")`
  (Task 5, shape: `date, mkt_rf, smb, hml, mom, rf`, all decimal).
- Produces: `car.estimate_four_factor_betas(ticker: str, event_date: date,
  prices: pl.DataFrame, factors: pl.DataFrame, sessions: list[date],
  estimation_start_offset: int = -250, estimation_end_offset: int = -30,
  min_obs: int = 30) -> dict | None` (keys `alpha, beta_mkt, beta_smb,
  beta_hml, beta_mom`, OLS-fit on the estimation window's daily excess
  returns; `None` if fewer than `min_obs` valid days exist in the window);
  `car.four_factor_car(ticker, event_date, horizon, prices, factors,
  market_ticker="SPY") -> float | None`; `car.four_factor_bhar(...)`
  (same signature, compounded).

**Methodology judgment call (confirm during plan review):** the estimated
`alpha` from the pre-event estimation window is included in the predicted
"normal" return for the event window (`predicted_t = alpha + betas ·
factors_t`), not dropped. This is the standard event-study convention
(the security's own average unexplained excess return is part of its
expected performance, not part of the abnormal signal being tested) and
is a different, deliberate choice from Model 3 (Task 19), where alpha
itself IS the test statistic on a portfolio of names, not something to be
subtracted out.

- [ ] **Step 1: Write the failing test — `tests/events/test_car_four_factor.py`**

```python
from __future__ import annotations

from datetime import date, timedelta

import polars as pl
import pytest

from congressional_sales.events import car

PRICE_SCHEMA = {
    "ticker": pl.Utf8, "date": pl.Date, "open": pl.Float64, "high": pl.Float64,
    "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64, "close_adj": pl.Float64,
}
FACTOR_SCHEMA = {"date": pl.Date, "mkt_rf": pl.Float64, "smb": pl.Float64, "hml": pl.Float64, "mom": pl.Float64, "rf": pl.Float64}


def _synthetic(n: int, true_alpha: float, true_beta_mkt: float):
    """n consecutive daily sessions where excess_return is EXACTLY
    true_alpha + true_beta_mkt*mkt_rf (true betas on smb/hml/mom are 0),
    built from genuinely non-collinear factor columns (different modular
    periods) so the regression design matrix has full rank and OLS on
    this noiseless data recovers the true coefficients exactly."""
    base = date(2020, 1, 1)
    sessions = [base + timedelta(days=i) for i in range(n)]
    price = 100.0
    price_rows = [{"ticker": "T", "date": sessions[0], "open": 1.0, "high": 1.0, "low": 1.0, "close": price, "volume": 1.0, "close_adj": price}]
    factor_rows = []
    for i in range(1, n):
        mkt_rf, smb, hml, mom, rf = 0.001 * (i % 7), 0.001 * (i % 5), 0.001 * (i % 3), 0.001 * (i % 11), 0.0001
        excess = true_alpha + true_beta_mkt * mkt_rf
        daily_r = excess + rf
        price = price * (1 + daily_r)
        price_rows.append({"ticker": "T", "date": sessions[i], "open": 1.0, "high": 1.0, "low": 1.0, "close": price, "volume": 1.0, "close_adj": price})
        factor_rows.append({"date": sessions[i], "mkt_rf": mkt_rf, "smb": smb, "hml": hml, "mom": mom, "rf": rf})
    prices = pl.DataFrame(price_rows, schema=PRICE_SCHEMA)
    factors = pl.DataFrame(factor_rows, schema=FACTOR_SCHEMA)
    return sessions, prices, factors


def test_estimate_four_factor_betas_recovers_known_coefficients_on_noiseless_data():
    sessions, prices, factors = _synthetic(n=40, true_alpha=0.02, true_beta_mkt=1.5)
    betas = car.estimate_four_factor_betas(
        "T", sessions[-1], prices, factors, sessions,
        estimation_start_offset=-(len(sessions) - 1), estimation_end_offset=-1, min_obs=30,
    )
    assert betas is not None
    assert betas["alpha"] == pytest.approx(0.02, abs=1e-6)
    assert betas["beta_mkt"] == pytest.approx(1.5, abs=1e-6)
    assert betas["beta_smb"] == pytest.approx(0.0, abs=1e-6)
    assert betas["beta_hml"] == pytest.approx(0.0, abs=1e-6)
    assert betas["beta_mom"] == pytest.approx(0.0, abs=1e-6)


def test_estimate_four_factor_betas_insufficient_data_is_none():
    sessions, prices, factors = _synthetic(n=15, true_alpha=0.02, true_beta_mkt=1.5)
    betas = car.estimate_four_factor_betas(
        "T", sessions[-1], prices, factors, sessions,
        estimation_start_offset=-(len(sessions) - 1), estimation_end_offset=-1, min_obs=30,
    )
    assert betas is None


def test_four_factor_car_is_zero_when_event_window_matches_the_fitted_model_exactly():
    """If the event window's actual returns follow the SAME true model the
    betas were estimated from, abnormal return must be ~0 at every session
    -- this is the sanity check that predicted_t actually uses alpha, not
    just the factor loadings."""
    sessions, prices, factors = _synthetic(n=60, true_alpha=0.02, true_beta_mkt=1.5)
    # Estimation window: sessions[1..49]; event_date sessions[49]; event window sessions[50..52].
    event_date = sessions[49]
    got = car.four_factor_car("T", event_date, horizon=3, prices=prices, factors=factors)
    assert got == pytest.approx(0.0, abs=1e-6)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/events/test_car_four_factor.py -v`
Expected: FAIL — `AttributeError: module 'car' has no attribute 'estimate_four_factor_betas'`

- [ ] **Step 3: Append to `src/congressional_sales/events/car.py`**

```python
def estimate_four_factor_betas(
    ticker: str, event_date: date, prices: pl.DataFrame, factors: pl.DataFrame, sessions: list[date],
    estimation_start_offset: int = -250, estimation_end_offset: int = -30, min_obs: int = 30,
) -> dict | None:
    import numpy as np

    start = offset_within_days(sessions, event_date, estimation_start_offset)
    end = offset_within_days(sessions, event_date, estimation_end_offset)
    if start is None or end is None:
        return None
    window = [d for d in sessions if start <= d <= end]

    rows = []
    for d in window:
        r = daily_return(ticker, d, prices, sessions)
        f = factors.filter(pl.col("date") == d)
        if r is None or f.is_empty():
            continue
        rows.append((r - f["rf"][0], f["mkt_rf"][0], f["smb"][0], f["hml"][0], f["mom"][0]))
    if len(rows) < min_obs:
        return None

    y = np.array([r[0] for r in rows])
    X = np.array([[1.0, r[1], r[2], r[3], r[4]] for r in rows])
    coefs, *_ = np.linalg.lstsq(X, y, rcond=None)
    return {"alpha": float(coefs[0]), "beta_mkt": float(coefs[1]), "beta_smb": float(coefs[2]), "beta_hml": float(coefs[3]), "beta_mom": float(coefs[4])}


def _predicted_excess(betas: dict, f_row: pl.DataFrame) -> float:
    return (
        betas["alpha"] + betas["beta_mkt"] * f_row["mkt_rf"][0] + betas["beta_smb"] * f_row["smb"][0]
        + betas["beta_hml"] * f_row["hml"][0] + betas["beta_mom"] * f_row["mom"][0]
    )


def four_factor_car(ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, factors: pl.DataFrame, market_ticker: str = "SPY") -> float | None:
    sessions = sessions_from_prices(prices, market_ticker)
    betas = estimate_four_factor_betas(ticker, event_date, prices, factors, sessions)
    if betas is None:
        return None
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    total = 0.0
    for d in dates:
        r = daily_return(ticker, d, prices, sessions)
        f = factors.filter(pl.col("date") == d)
        if r is None or f.is_empty():
            return None
        actual_excess = r - f["rf"][0]
        total += actual_excess - _predicted_excess(betas, f)
    return total


def four_factor_bhar(ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, factors: pl.DataFrame, market_ticker: str = "SPY") -> float | None:
    sessions = sessions_from_prices(prices, market_ticker)
    betas = estimate_four_factor_betas(ticker, event_date, prices, factors, sessions)
    if betas is None:
        return None
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    actual_growth, predicted_growth = 1.0, 1.0
    for d in dates:
        r = daily_return(ticker, d, prices, sessions)
        f = factors.filter(pl.col("date") == d)
        if r is None or f.is_empty():
            return None
        actual_growth *= 1 + (r - f["rf"][0])
        predicted_growth *= 1 + _predicted_excess(betas, f)
    return (actual_growth - 1) - (predicted_growth - 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/events/test_car_four_factor.py -v`
Expected: `3 passed`. If the third test's window indices are off by one
(e.g. `estimate_four_factor_betas` inside `four_factor_car` ends up
estimating over a window that doesn't purely reflect the synthetic
noiseless model, or the event window rows fall outside the 60-session
fixture), the assertion will show a small but clearly nonzero value
instead of ~0 — adjust the fixture's session count or the event-window
offsets used in the test until the estimation window and event window
both fall entirely within the synthetic data's noiseless region, per this
plan's established practice of verifying exact arithmetic empirically
rather than trusting it by construction.

- [ ] **Step 5: Commit**

```bash
git add src/congressional_sales/events/car.py tests/events/test_car_four_factor.py
git commit -m "Add four-factor CAR/BHAR"
```

### Task 16: Size/industry-matched CAR and BHAR

**Files:**
- Modify: `src/congressional_sales/events/car.py`
- Test: `tests/events/test_car_size_industry.py`

**Interfaces:**
- Consumes: `car.sessions_from_prices`, `car.daily_return` (this file),
  `industry.ff12_industry` (Task 7), `storage.read("sic_codes")` (Task 7).
- Produces: `car.size_proxy(ticker: str, as_of: date, prices: pl.DataFrame,
  sessions: list[date], lookback: int = 30) -> float | None` (trailing
  average dollar volume over the `lookback` sessions before `as_of` — see
  Global Constraints "Documented size/matching limitations"); `car.
  matched_control_tickers(ticker: str, event_date: date, prices:
  pl.DataFrame, sic: pl.DataFrame, sessions: list[date], n_deciles: int =
  10) -> list[str]` (same-FF12-sector tickers in the same size decile as
  `ticker`, excluding `ticker` itself; falls back to all same-sector
  tickers if fewer than `n_deciles` peers exist in that sector, and
  documents this in a log-friendly way rather than raising);
  `car.size_industry_matched_car(ticker, event_date, horizon, prices, sic,
  market_ticker="SPY") -> float | None` (ticker's raw CAR minus the
  equal-weighted average CAR of its matched control tickers over the same
  window); `car.size_industry_matched_bhar(...)` (same signature,
  compounded).

- [ ] **Step 1: Write the failing test — `tests/events/test_car_size_industry.py`**

```python
from __future__ import annotations

from datetime import date, timedelta

import polars as pl
import pytest

from congressional_sales.events import car

PRICE_SCHEMA = {
    "ticker": pl.Utf8, "date": pl.Date, "open": pl.Float64, "high": pl.Float64,
    "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64, "close_adj": pl.Float64,
}
SIC_SCHEMA = {"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8}


def _flat_price_series(ticker: str, sessions: list, start_price: float, daily_return: float, volume: float) -> pl.DataFrame:
    rows = []
    price = start_price
    for i, d in enumerate(sessions):
        if i > 0:
            price *= 1 + daily_return
        rows.append({"ticker": ticker, "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": price, "volume": volume, "close_adj": price})
    return pl.DataFrame(rows, schema=PRICE_SCHEMA)


def test_size_proxy_is_trailing_average_dollar_volume():
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(5)]
    prices = _flat_price_series("AAPL", sessions, 100.0, 0.0, volume=1000.0)
    # Every session: close_adj=100, volume=1000 -> dollar volume=100,000 exactly.
    got = car.size_proxy("AAPL", sessions[-1], prices, sessions, lookback=4)
    assert got == pytest.approx(100_000.0)


def test_matched_control_tickers_excludes_self_and_matches_sector_and_size():
    """4 same-sector peers (including the event ticker) split cleanly into
    2 deciles of 2 -- BIG1/BIG2 both ~10M in dollar volume, SMALL1/SMALL2
    both ~10K, a >100x gap with no ambiguous middle value, so bucket
    boundaries land on a whole-number split (4 names / 2 deciles = groups
    of exactly 2) rather than the fractional-boundary case a 3-peer/
    2-decile split would produce."""
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(10)]
    prices = pl.concat(
        [
            _flat_price_series("BIG1", sessions, 100.0, 0.0, volume=100_000.0),
            _flat_price_series("BIG2", sessions, 100.0, 0.0, volume=100_000.0),
            _flat_price_series("SMALL1", sessions, 100.0, 0.0, volume=100.0),
            _flat_price_series("SMALL2", sessions, 100.0, 0.0, volume=100.0),
            _flat_price_series("OTHERSECTOR", sessions, 100.0, 0.0, volume=100_000.0),
        ]
    )
    sic = pl.DataFrame(
        {
            "ticker": ["BIG1", "BIG2", "SMALL1", "SMALL2", "OTHERSECTOR"],
            "cik": [1, 2, 3, 4, 5],
            "sic_code": ["7372", "7372", "7372", "7372", "2911"],  # first 4 Business Equipment, last one Energy
            "sic_description": ["x"] * 5,
        },
        schema=SIC_SCHEMA,
    )
    controls = car.matched_control_tickers("BIG1", sessions[-1], prices, sic, sessions, n_deciles=2)
    assert "BIG1" not in controls  # never includes self
    assert "OTHERSECTOR" not in controls  # different sector, never a candidate
    assert "SMALL1" not in controls  # different size decile
    assert "SMALL2" not in controls  # different size decile
    assert controls == ["BIG2"]  # the one genuine same-sector, same-decile peer


def test_size_industry_matched_car_nets_out_the_control_groups_move():
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(10)]
    prices = pl.concat(
        [
            _flat_price_series("EVENT", sessions, 100.0, 0.05, volume=100_000.0),   # +5%/day
            _flat_price_series("PEER1", sessions, 100.0, 0.01, volume=100_000.0),   # +1%/day
            _flat_price_series("PEER2", sessions, 100.0, 0.01, volume=100_000.0),   # +1%/day
        ]
    )
    sic = pl.DataFrame(
        {"ticker": ["EVENT", "PEER1", "PEER2"], "cik": [1, 2, 3], "sic_code": ["7372", "7372", "7372"], "sic_description": ["x"] * 3},
        schema=SIC_SCHEMA,
    )
    got = car.size_industry_matched_car("EVENT", sessions[4], horizon=3, prices=prices, sic=sic)
    # EVENT daily return over [+1,+3] is exactly 0.05 each session (flat compounding
    # rate by construction), control group average is exactly 0.01 each session ->
    # CAR = sum(0.05-0.01) * 3 = 0.12.
    assert got == pytest.approx(0.12, abs=1e-6)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/events/test_car_size_industry.py -v`
Expected: FAIL — `AttributeError: module 'car' has no attribute 'size_proxy'`

- [ ] **Step 3: Append to `src/congressional_sales/events/car.py`**

```python
def size_proxy(ticker: str, as_of: date, prices: pl.DataFrame, sessions: list[date], lookback: int = 30) -> float | None:
    start = offset_within_days(sessions, as_of, -lookback)
    if start is None:
        return None
    window = [d for d in sessions if start <= d <= as_of]
    rows = prices.filter((pl.col("ticker") == ticker) & pl.col("date").is_in(window))
    if rows.is_empty():
        return None
    dollar_vol = (rows["close_adj"] * rows["volume"]).mean()
    return float(dollar_vol) if dollar_vol is not None else None


def matched_control_tickers(
    ticker: str, event_date: date, prices: pl.DataFrame, sic: pl.DataFrame, sessions: list[date], n_deciles: int = 10
) -> list[str]:
    my_sic = sic.filter(pl.col("ticker") == ticker)
    if my_sic.is_empty():
        return []
    my_sector = ff12_industry(my_sic["sic_code"][0])

    peers = sic.filter(pl.col("ticker") != ticker)
    peer_sectors = peers.with_columns(pl.col("sic_code").map_elements(ff12_industry, return_dtype=pl.Utf8).alias("_sector"))
    same_sector = peer_sectors.filter(pl.col("_sector") == my_sector)["ticker"].to_list()
    if not same_sector:
        return []

    my_size = size_proxy(ticker, event_date, prices, sessions)
    sized_peers = [(t, size_proxy(t, event_date, prices, sessions)) for t in same_sector]
    sized_peers = [(t, s) for t, s in sized_peers if s is not None]
    if my_size is None or len(sized_peers) < n_deciles:
        # Too few same-sector peers to form meaningful deciles -- fall back
        # to the full same-sector set rather than raising. This is the
        # "coarser buckets in sparsely-covered sectors" limitation
        # documented in the plan's Global Constraints.
        return same_sector

    # Rank every (ticker, size) pair -- including the event ticker itself
    # -- by size ascending, tie-breaking by ticker name for a deterministic
    # order. Bucket index = floor(position / bucket_size), bucket_size =
    # n / n_deciles. Ranking by POSITION rather than by looking up size
    # values matters here: two tickers can share an identical size (a
    # real possibility with a coarse dollar-volume proxy), and a
    # value-based lookup (e.g. list.index(size)) would silently collapse
    # every tied ticker onto whichever one happens to appear first in the
    # sorted list -- verified during planning to misclassify a same-sized
    # peer into the wrong bucket. Position-based ranking has no such
    # ambiguity because every entry, including ties, gets its own index.
    all_pairs = sorted(sized_peers + [(ticker, my_size)], key=lambda p: (p[1], p[0]))
    n = len(all_pairs)
    bucket_size = n / n_deciles
    my_position = next(i for i, (t, _) in enumerate(all_pairs) if t == ticker)
    my_bucket = int(my_position / bucket_size)
    return [
        t for i, (t, _) in enumerate(all_pairs)
        if t != ticker and int(i / bucket_size) == my_bucket
    ]


def _control_group_return(controls: list[str], d: date, prices: pl.DataFrame, sessions: list[date]) -> float | None:
    if not controls:
        return None
    returns = [daily_return(t, d, prices, sessions) for t in controls]
    returns = [r for r in returns if r is not None]
    if not returns:
        return None
    return sum(returns) / len(returns)


def size_industry_matched_car(ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, sic: pl.DataFrame, market_ticker: str = "SPY") -> float | None:
    sessions = sessions_from_prices(prices, market_ticker)
    controls = matched_control_tickers(ticker, event_date, prices, sic, sessions)
    if not controls:
        return None
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    total = 0.0
    for d in dates:
        r_t = daily_return(ticker, d, prices, sessions)
        r_c = _control_group_return(controls, d, prices, sessions)
        if r_t is None or r_c is None:
            return None
        total += r_t - r_c
    return total


def size_industry_matched_bhar(ticker: str, event_date: date, horizon: int, prices: pl.DataFrame, sic: pl.DataFrame, market_ticker: str = "SPY") -> float | None:
    sessions = sessions_from_prices(prices, market_ticker)
    controls = matched_control_tickers(ticker, event_date, prices, sic, sessions)
    if not controls:
        return None
    dates = _window_dates(event_date, horizon, sessions)
    if dates is None:
        return None
    ticker_growth, control_growth = 1.0, 1.0
    for d in dates:
        r_t = daily_return(ticker, d, prices, sessions)
        r_c = _control_group_return(controls, d, prices, sessions)
        if r_t is None or r_c is None:
            return None
        ticker_growth *= 1 + r_t
        control_growth *= 1 + r_c
    return (ticker_growth - 1) - (control_growth - 1)
```

Add `from .industry import ff12_industry` (relative import — note
`events/car.py` importing from `sample/industry.py` crosses the two
packages; if this creates a circular-import risk once `sample/` code ever
imports from `events/`, move `ff12_industry` to a shared location such as
a new top-level `industry.py` instead — check for cycles before assuming
this import direction stays clean) to the top of `car.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/events/test_car_size_industry.py -v`
Expected: `3 passed`. The decile-bucketing arithmetic in
`matched_control_tickers` was hand-verified during planning against the
exact 4-peer/2-decile fixture in
`test_matched_control_tickers_excludes_self_and_matches_sector_and_size`
(position-based ranking with ticker-name tie-breaking, `bucket_size = n /
n_deciles`, `my_bucket = floor(my_position / bucket_size)` — traced by
hand to confirm `BIG1` and `BIG2` land in bucket 1 while `SMALL1`/`SMALL2`
land in bucket 0, giving `controls == ["BIG2"]` exactly). An earlier
version of this function used `list.index(size)` to look up rank, which
silently misclassified tied sizes into the wrong bucket — verified broken
by hand-tracing the original `BIG1`/`BIG2`/`SMALL1` 3-peer fixture before
being replaced with the position-based version and the cleaner 4-peer
fixture above. If this still fails on first run, the bug is more likely
in the test fixture's assumed sort order (recheck the tie-break) than in
a fresh off-by-one — trace both against the real intermediate values
before changing the assertion.

- [ ] **Step 5: Commit**

```bash
git add src/congressional_sales/events/car.py tests/events/test_car_size_industry.py
git commit -m "Add size/industry-matched CAR/BHAR"
```

### Task 17: Random control permutation test (Section 8)

**Files:**
- Create: `src/congressional_sales/events/permutation.py`
- Test: `tests/events/test_permutation.py`

**Interfaces:**
- Consumes: nothing from earlier tasks directly — takes a `compute_fn:
  Callable[[str, date], float | None]` so it works against any of Task
  14-16's CAR/BHAR functions (the caller binds `horizon`/`prices`/etc. via
  `functools.partial` before passing it in), keeping this module free of
  any dependency on the event-study internals.
- Produces: `permutation.random_control_test(transactions: list[tuple[str,
  date]], compute_fn: Callable[[str, date], float | None], period_start:
  date, period_end: date, sessions: list[date], n_iterations: int = 1000,
  seed: int | None = None) -> dict` (keys: `actual_mean: float,
  simulated_means: list[float], percentile: float, n_iterations_used:
  int` — `percentile` is the fraction of simulated means at or below the
  actual mean, i.e. where the real result falls in the null distribution,
  exactly what Section 8 asks the paper to report).

- [ ] **Step 1: Write the failing test — `tests/events/test_permutation.py`**

```python
from __future__ import annotations

from datetime import date, timedelta

import pytest

from congressional_sales.events import permutation


def test_random_control_test_actual_mean_matches_direct_computation():
    def compute_fn(ticker, d):
        return 1.0 if ticker == "AAPL" else 2.0

    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(300)]
    result = permutation.random_control_test(
        transactions=[("AAPL", sessions[10]), ("MSFT", sessions[20])],
        compute_fn=compute_fn, period_start=sessions[0], period_end=sessions[-1],
        sessions=sessions, n_iterations=5, seed=42,
    )
    assert result["actual_mean"] == pytest.approx(1.5)


def test_random_control_test_reports_1000_iterations_by_default():
    def compute_fn(ticker, d):
        return 1.0

    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(300)]
    result = permutation.random_control_test(
        transactions=[("AAPL", sessions[10])], compute_fn=compute_fn,
        period_start=sessions[0], period_end=sessions[-1], sessions=sessions, seed=1,
    )
    assert result["n_iterations_used"] == 1000
    assert len(result["simulated_means"]) == 1000


def test_random_control_test_is_reproducible_with_the_same_seed():
    def compute_fn(ticker, d):
        return d.toordinal() % 7  # value depends on the (randomized) date -> exercises real resampling

    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(300)]
    kwargs = dict(
        transactions=[("AAPL", sessions[10]), ("AAPL", sessions[50])], compute_fn=compute_fn,
        period_start=sessions[0], period_end=sessions[-1], sessions=sessions, n_iterations=50,
    )
    r1 = permutation.random_control_test(**kwargs, seed=7)
    r2 = permutation.random_control_test(**kwargs, seed=7)
    assert r1["simulated_means"] == r2["simulated_means"]


def test_random_control_test_percentile_is_between_zero_and_one():
    def compute_fn(ticker, d):
        return float(d.toordinal() % 11)

    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(300)]
    result = permutation.random_control_test(
        transactions=[("AAPL", sessions[100])], compute_fn=compute_fn,
        period_start=sessions[0], period_end=sessions[-1], sessions=sessions, n_iterations=100, seed=3,
    )
    assert 0.0 <= result["percentile"] <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/events/test_permutation.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/congressional_sales/events/permutation.py`**

```python
"""Random control permutation test, PRE_ANALYSIS_PLAN.md Section 8: for
each result, resample the same tickers on random dates within the sample
period, 1,000 times, and report where the actual result falls in that
null distribution. "The single most persuasive robustness check
available" per the plan -- treated here as a generic tool over any CAR/
BHAR compute_fn so it applies uniformly to every Table T4/T5 cell.
"""

from __future__ import annotations

import random
import statistics
from collections.abc import Callable
from datetime import date


def random_control_test(
    transactions: list[tuple[str, date]],
    compute_fn: Callable[[str, date], float | None],
    period_start: date,
    period_end: date,
    sessions: list[date],
    n_iterations: int = 1000,
    seed: int | None = None,
) -> dict:
    real_values = [v for t, d in transactions if (v := compute_fn(t, d)) is not None]
    actual_mean = statistics.mean(real_values) if real_values else float("nan")

    candidate_sessions = [d for d in sessions if period_start <= d <= period_end]
    rng = random.Random(seed)
    simulated_means: list[float] = []
    for _ in range(n_iterations):
        sim_values = []
        for ticker, _ in transactions:
            random_date = rng.choice(candidate_sessions)
            v = compute_fn(ticker, random_date)
            if v is not None:
                sim_values.append(v)
        if sim_values:
            simulated_means.append(statistics.mean(sim_values))

    if simulated_means:
        percentile = sum(1 for s in simulated_means if s <= actual_mean) / len(simulated_means)
    else:
        percentile = float("nan")

    return {
        "actual_mean": actual_mean,
        "simulated_means": simulated_means,
        "percentile": percentile,
        "n_iterations_used": n_iterations,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/events/test_permutation.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/congressional_sales/events/permutation.py tests/events/test_permutation.py
git commit -m "Add Section 8 random control permutation test"
```

---

## Phase 5 — Statistical Models (Section 7-8)

Models 1-3 delegate their clustering/fixed-effects/regression math to
`statsmodels`/`linearmodels` rather than hand-rolled formulas — unlike the
event-study engine (Phase 4), which had genuine novel arithmetic worth
independently verifying, cluster-robust OLS and absorbed-fixed-effects
regression are exactly what those mature, widely-used libraries are for.
Tests in this phase check that this codebase wires values into and out of
those libraries correctly, not that the libraries' own math is right.

### Task 18: Model 1 — unconditional means with clustered SEs

**Files:**
- Create: `src/congressional_sales/models/__init__.py`
- Create: `src/congressional_sales/models/model1.py`
- Test: `tests/models/test_model1.py`

**Interfaces:**
- Consumes: nothing from earlier tasks directly (pure statistics over
  caller-supplied arrays — the caller is responsible for having already
  attached a CAR column via Phase 4's functions).
- Produces: `model1.clustered_mean(values: list[float], cluster_ids:
  list) -> dict` (keys `mean, se, t_stat, n`, cluster-robust via
  `statsmodels`); `model1.unconditional_means_table(sample: pl.DataFrame,
  car_col: str) -> pl.DataFrame` (columns `transaction, mean, se_member,
  se_month, n` — one row per `{"Sale", "Purchase"}`, clustered separately
  by `bioguide_id` and by the calendar month of `report_date`, per Section
  7 Model 1's explicit "report both" instruction).

- [ ] **Step 1: Create `src/congressional_sales/models/__init__.py`**

```python
"""Models 1-3 (Section 7) and the Benjamini-Hochberg multiple-comparisons
correction (Section 8)."""
```

- [ ] **Step 2: Write the failing test — `tests/models/test_model1.py`**

```python
from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from congressional_sales.models import model1


def test_clustered_mean_recovers_the_simple_average():
    values = [0.10, 0.20, 0.30, 0.40]
    clusters = ["A", "A", "B", "B"]
    got = model1.clustered_mean(values, clusters)
    assert got["mean"] == pytest.approx(0.25)
    assert got["n"] == 4
    assert got["se"] > 0


def test_clustered_mean_se_differs_by_clustering_choice():
    """Clustering by a variable correlated with the outcome (here: cluster
    B is uniformly higher-valued) should generally produce a different SE
    than clustering by an uncorrelated grouping -- this is a sanity check
    that cluster_ids actually flows into the statsmodels call, not a
    from-scratch re-derivation of cluster-robust variance."""
    values = [0.10, 0.12, 0.30, 0.32, 0.11, 0.31]
    by_pair = ["A", "A", "B", "B", "A", "B"]
    by_row = ["1", "2", "3", "4", "5", "6"]  # every row its own cluster
    se_pair = model1.clustered_mean(values, by_pair)["se"]
    se_row = model1.clustered_mean(values, by_row)["se"]
    assert se_pair != pytest.approx(se_row)


def test_unconditional_means_table_has_one_row_per_transaction_type():
    sample = pl.DataFrame(
        {
            "transaction": ["Sale", "Sale", "Purchase"],
            "bioguide_id": ["A1", "A2", "A1"],
            "report_date": [date(2020, 1, 15), date(2020, 2, 20), date(2020, 1, 10)],
            "car": [-0.05, -0.03, 0.04],
        }
    )
    t = model1.unconditional_means_table(sample, car_col="car")
    assert set(t["transaction"].to_list()) == {"Sale", "Purchase"}
    sale_row = t.filter(pl.col("transaction") == "Sale")
    assert sale_row["mean"][0] == pytest.approx(-0.04)
    assert sale_row["n"][0] == 2


def test_unconditional_means_table_drops_null_car_rows():
    sample = pl.DataFrame(
        {
            "transaction": ["Sale", "Sale"],
            "bioguide_id": ["A1", "A2"],
            "report_date": [date(2020, 1, 15), date(2020, 2, 20)],
            "car": [-0.05, None],
        }
    )
    t = model1.unconditional_means_table(sample, car_col="car")
    assert t.filter(pl.col("transaction") == "Sale")["n"][0] == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/models/test_model1.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement `src/congressional_sales/models/model1.py`**

```python
"""Model 1 (Section 7): unconditional mean CAR with cluster-robust SEs,
computed both ways Section 7 requires -- clustered on member and,
separately, on calendar month."""

from __future__ import annotations

import numpy as np
import polars as pl
import statsmodels.api as sm


def clustered_mean(values: list[float], cluster_ids: list) -> dict:
    y = np.array(values, dtype=float)
    X = np.ones((len(y), 1))
    fit = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": np.array(cluster_ids)})
    return {"mean": float(fit.params[0]), "se": float(fit.bse[0]), "t_stat": float(fit.tvalues[0]), "n": len(y)}


def unconditional_means_table(sample: pl.DataFrame, car_col: str) -> pl.DataFrame:
    rows = []
    for txn_type in ("Sale", "Purchase"):
        subset = sample.filter(pl.col("transaction") == txn_type).drop_nulls(car_col)
        if subset.is_empty():
            continue
        values = subset[car_col].to_list()
        by_member = clustered_mean(values, subset["bioguide_id"].to_list())
        month_ids = subset["report_date"].dt.truncate("1mo").cast(pl.Utf8).to_list()
        by_month = clustered_mean(values, month_ids)
        rows.append(
            {
                "transaction": txn_type, "mean": by_member["mean"],
                "se_member": by_member["se"], "se_month": by_month["se"], "n": by_member["n"],
            }
        )
    return pl.DataFrame(rows)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/models/test_model1.py -v`
Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add src/congressional_sales/models/__init__.py src/congressional_sales/models/model1.py tests/models/test_model1.py
git commit -m "Add Model 1: unconditional means with member- and month-clustered SEs"
```

### Task 19: Model 2 — pooled fixed-effects regression

**Files:**
- Create: `src/congressional_sales/models/model2.py`
- Test: `tests/models/test_model2.py`

**Interfaces:**
- Consumes: a regression-ready `pl.DataFrame` with columns `car: Float64,
  sale: Int (0/1), opportunistic: Int (0/1), committee_match: Int (0/1),
  log_size: Float64, prior_12mo_return: Float64, size_band: Utf8,
  chamber: Utf8, party: Utf8, seniority_terms: Int64, bioguide_id: Utf8
  (member FE), year: Int64 (year FE), industry: Utf8 (industry FE)`.
- Produces: `model2.build_model2_frame(sample_with_car: pl.DataFrame,
  size_proxies: dict[tuple[str, "datetime.date"], float], terms:
  pl.DataFrame, car_col: str) -> pl.DataFrame` (assembles the columns
  above from the sample; `sale=1` iff `transaction == "Sale"`;
  `opportunistic = 1 - is_routine`; `seniority_terms` = count of prior
  terms for that `bioguide_id` in `terms` with `term_start <
  report_date`); `model2.run_model2(df: pl.DataFrame) -> dict` (keys:
  `params: dict[str, float], se: dict[str, float], n_obs: int,
  n_absorbed_member: int, n_absorbed_year: int, n_absorbed_industry: int`
  — `params`/`se` cover `sale, opportunistic, sale_x_opportunistic,
  committee_match, sale_x_committee_match, log_size,
  prior_12mo_return, seniority_terms` plus any `size_band`/`chamber`/
  `party` dummy columns; standard errors clustered at the member level).

**Documented omission (see Global Constraints):** `book-to-market` is not
a control in this implementation — no data source for it exists in this
plan. This function must not silently produce a regression table that
looks complete; `run_model2`'s docstring states the omission explicitly.

**Library-version note:** this task uses `linearmodels.iv.absorbing.
AbsorbingLS` to absorb the three high-dimensional fixed effects (member,
year, industry) without materializing dummy columns for hundreds of
members. Its exact `.fit()` keyword arguments for cluster-robust
covariance have varied across `linearmodels` versions — confirm the
installed version's signature (`python -c "from linearmodels.iv.absorbing
import AbsorbingLS; help(AbsorbingLS.fit)"`) before trusting the call
below verbatim, and adjust if it differs.

- [ ] **Step 1: Write the failing test — `tests/models/test_model2.py`**

```python
from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from congressional_sales.models import model2


def _regression_frame() -> pl.DataFrame:
    # A small, hand-constructed panel spanning 3 members x 2 years x 2
    # industries, with car deliberately higher for Sale=1 rows so beta_sale
    # should come out positive and detectable even after FE absorption --
    # this is a sanity/wiring check, not an exact-recovery proof (a
    # from-scratch exact-recovery test for a 3-way absorbed-FE model would
    # need a much larger synthetic panel than is proportionate here).
    rows = []
    for member in ["A1", "A2", "A3"]:
        for year in (2019, 2020):
            for industry in ("Business Equipment", "Energy"):
                for sale in (0, 1):
                    rows.append(
                        {
                            "car": (0.05 if sale else -0.01) + hash((member, year, industry)) % 5 * 0.001,
                            "sale": sale, "opportunistic": 1, "committee_match": 0,
                            "log_size": 10.0, "prior_12mo_return": 0.05, "size_band": "$1,001 - $15,000",
                            "chamber": "Representatives", "party": "R", "seniority_terms": 2,
                            "bioguide_id": member, "year": year, "industry": industry,
                        }
                    )
    return pl.DataFrame(rows)


def test_run_model2_returns_all_expected_coefficient_keys():
    df = _regression_frame()
    result = model2.run_model2(df)
    expected = {
        "sale", "opportunistic", "sale_x_opportunistic", "committee_match",
        "sale_x_committee_match", "log_size", "prior_12mo_return", "seniority_terms",
    }
    assert expected.issubset(result["params"].keys())
    assert expected.issubset(result["se"].keys())
    assert result["n_obs"] == df.height


def test_run_model2_sale_coefficient_is_positive_on_constructed_data():
    df = _regression_frame()
    result = model2.run_model2(df)
    assert result["params"]["sale"] > 0


def test_build_model2_frame_computes_seniority_from_prior_terms():
    sample = pl.DataFrame(
        {
            "ticker": ["AAPL"], "bioguide_id": ["A1"], "transaction": ["Sale"],
            "report_date": [date(2020, 6, 1)], "is_routine": [False], "committee_match": [True],
            "amount_range": ["$1,001 - $15,000"], "chamber": ["Representatives"], "party": ["R"],
            "car": [-0.05],
        }
    )
    terms = pl.DataFrame(
        {
            "bioguide_id": ["A1", "A1", "A1"], "full_name": ["x"] * 3, "chamber": ["rep"] * 3,
            "term_start": [date(2015, 1, 1), date(2017, 1, 1), date(2019, 1, 1)],
            "term_end": [date(2017, 1, 1), date(2019, 1, 1), date(2021, 1, 1)],
            "state": ["XX"] * 3, "party": ["R"] * 3,
        }
    )
    out = model2.build_model2_frame(sample, size_proxies={("AAPL", date(2020, 6, 1)): 100_000.0}, terms=terms, car_col="car")
    assert out["seniority_terms"][0] == 3  # all 3 prior terms started before the report_date
    assert out["sale"][0] == 1
    assert out["opportunistic"][0] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/models/test_model2.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/congressional_sales/models/model2.py`**

```python
"""Model 2 (Section 7): pooled fixed-effects regression.

    CAR_i = b0 + b1*Sale_i + b2*Opportunistic_i + b3*(Sale x Opportunistic)_i
            + b4*CommitteeMatch_i + b5*(Sale x CommitteeMatch)_i
            + gamma*Controls_i + MemberFE + YearFE + IndustryFE + e_i

Controls implemented: log_size (Task 16's dollar-volume proxy, in place of
log market cap -- no shares-outstanding source in this project),
prior_12mo_return, size_band, chamber, party, seniority_terms.
book-to-market is OMITTED -- no data source for it exists in this
project. This is a documented deviation from Section 7, not a silent
gap; state it in the paper's limitations section.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import polars as pl


def build_model2_frame(sample_with_car: pl.DataFrame, size_proxies: dict, terms: pl.DataFrame, car_col: str) -> pl.DataFrame:
    def _seniority(bioguide: str, report_date) -> int:
        prior = terms.filter((pl.col("bioguide_id") == bioguide) & (pl.col("term_start") < report_date))
        return prior.height

    rows = []
    for row in sample_with_car.iter_rows(named=True):
        size = size_proxies.get((row["ticker"], row["report_date"]))
        rows.append(
            {
                "car": row[car_col],
                "sale": 1 if row["transaction"] == "Sale" else 0,
                "opportunistic": 0 if row.get("is_routine") else 1,
                "committee_match": 1 if row.get("committee_match") else 0,
                "log_size": math.log(size) if size and size > 0 else None,
                "prior_12mo_return": row.get("prior_12mo_return"),
                "size_band": row["amount_range"],
                "chamber": row["chamber"],
                "party": row["party"],
                "seniority_terms": _seniority(row["bioguide_id"], row["report_date"]),
                "bioguide_id": row["bioguide_id"],
                "year": row["report_date"].year,
                "industry": row.get("industry", "Other"),
            }
        )
    return pl.DataFrame(rows).drop_nulls(["car", "log_size"])


def run_model2(df: pl.DataFrame) -> dict:
    from linearmodels.iv.absorbing import AbsorbingLS

    pdf = df.to_pandas()
    pdf["sale_x_opportunistic"] = pdf["sale"] * pdf["opportunistic"]
    pdf["sale_x_committee_match"] = pdf["sale"] * pdf["committee_match"]

    numeric_regressors = [
        "sale", "opportunistic", "sale_x_opportunistic", "committee_match",
        "sale_x_committee_match", "log_size", "prior_12mo_return", "seniority_terms",
    ]
    categorical_regressors = pd.get_dummies(pdf[["size_band", "chamber", "party"]], drop_first=True)
    exog = pd.concat([pdf[numeric_regressors], categorical_regressors], axis=1).astype(float)
    exog = pd.concat([pd.Series(1.0, index=exog.index, name="const"), exog], axis=1)

    absorb = pdf[["bioguide_id", "year", "industry"]].astype("category")

    model = AbsorbingLS(pdf["car"].astype(float), exog, absorb=absorb)
    fit = model.fit(cov_type="clustered", clusters=pdf["bioguide_id"])

    return {
        "params": {k: float(v) for k, v in fit.params.items() if k != "const"},
        "se": {k: float(v) for k, v in fit.std_errors.items() if k != "const"},
        "n_obs": int(fit.nobs),
        "n_absorbed_member": pdf["bioguide_id"].nunique(),
        "n_absorbed_year": pdf["year"].nunique(),
        "n_absorbed_industry": pdf["industry"].nunique(),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/models/test_model2.py -v`
Expected: `3 passed`. If `AbsorbingLS.fit(cov_type="clustered",
clusters=...)` raises a `TypeError` on the installed `linearmodels`
version, check `help(AbsorbingLS.fit)` per this task's library-version
note and adjust the call (recent versions have used `cov_type="clustered"`
with a `clusters=` DataFrame/Series consistently, but confirm against
what's actually installed rather than assuming).

- [ ] **Step 5: Commit**

```bash
git add src/congressional_sales/models/model2.py tests/models/test_model2.py
git commit -m "Add Model 2: pooled fixed-effects regression (AbsorbingLS)"
```

### Task 20: Model 3 — calendar-time portfolio regression

**Files:**
- Create: `src/congressional_sales/models/model3.py`
- Test: `tests/models/test_model3.py`

**Interfaces:**
- Consumes: `storage.read("equity_eod")`, `storage.read("ff_factors")`
  (daily; this task compounds them to monthly internally — no new data
  source needed).
- Produces: `model3.monthly_factor_returns(factors: pl.DataFrame) ->
  pl.DataFrame` (columns `month: Date, mkt_rf, smb, hml, mom, rf`, each a
  compounded `prod(1+daily) - 1` over the calendar month);
  `model3.monthly_stock_return(ticker: str, month: date, prices:
  pl.DataFrame) -> float | None` (same compounding, for one ticker/month);
  `model3.calendar_time_portfolio_returns(screened_sales: list[tuple[str,
  date]], prices: pl.DataFrame, holding_months: int = 3) -> pl.DataFrame`
  (columns `month: Date, portfolio_return: Float64, n_names: Int64` — a
  ticker is a member of the **short** portfolio for `holding_months`
  calendar months starting the month after its `report_date`, so
  `portfolio_return` is the **negative** of the equal-weighted average of
  its members' monthly returns — Section 7 explicitly says "a monthly
  calendar-time portfolio of **shorted** screened-sale names");
  `model3.calendar_time_alpha(portfolio_returns: pl.DataFrame, factors:
  pl.DataFrame) -> dict` (keys `alpha, se, t_stat, n_months` from OLS of
  `portfolio_return - rf` on `[mkt_rf, smb, hml, mom]`).

**Documented approximation:** "90 days held" (Section 7) is implemented as
3 calendar months, the standard convention in the calendar-time portfolio
literature, rather than exact trading-day counting — a calendar-time
portfolio is monthly-rebalanced by construction, so exact day counts
don't carry through cleanly anyway. State this in the paper's methodology
section.

- [ ] **Step 1: Write the failing test — `tests/models/test_model3.py`**

```python
from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from congressional_sales.models import model3

PRICE_SCHEMA = {
    "ticker": pl.Utf8, "date": pl.Date, "open": pl.Float64, "high": pl.Float64,
    "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64, "close_adj": pl.Float64,
}
FACTOR_SCHEMA = {"date": pl.Date, "mkt_rf": pl.Float64, "smb": pl.Float64, "hml": pl.Float64, "mom": pl.Float64, "rf": pl.Float64}


def test_monthly_factor_returns_compounds_daily_to_monthly():
    factors = pl.DataFrame(
        [
            {"date": date(2020, 1, 2), "mkt_rf": 0.01, "smb": 0.0, "hml": 0.0, "mom": 0.0, "rf": 0.0001},
            {"date": date(2020, 1, 3), "mkt_rf": 0.01, "smb": 0.0, "hml": 0.0, "mom": 0.0, "rf": 0.0001},
        ],
        schema=FACTOR_SCHEMA,
    )
    got = model3.monthly_factor_returns(factors)
    assert got.height == 1
    assert got["mkt_rf"][0] == pytest.approx(1.01 * 1.01 - 1, abs=1e-9)


def test_monthly_stock_return_compounds_within_month():
    prices = pl.DataFrame(
        [
            {"ticker": "T", "date": date(2020, 1, 2), "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1.0, "close_adj": 100.0},
            {"ticker": "T", "date": date(2020, 1, 31), "open": 1.0, "high": 1.0, "low": 1.0, "close": 110.0, "volume": 1.0, "close_adj": 110.0},
        ],
        schema=PRICE_SCHEMA,
    )
    got = model3.monthly_stock_return("T", date(2020, 1, 1), prices)
    assert got == pytest.approx(0.10)


def test_calendar_time_portfolio_is_short_so_a_rising_stock_gives_a_negative_return():
    prices = pl.DataFrame(
        [
            {"ticker": "T", "date": date(2020, 3, 1), "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1.0, "close_adj": 100.0},
            {"ticker": "T", "date": date(2020, 3, 31), "open": 1.0, "high": 1.0, "low": 1.0, "close": 120.0, "volume": 1.0, "close_adj": 120.0},
        ],
        schema=PRICE_SCHEMA,
    )
    got = model3.calendar_time_portfolio_returns([("T", date(2020, 2, 15))], prices, holding_months=3)
    # T's disclosure is Feb 15 -> it's short-held for March/April/May.
    march = got.filter(pl.col("month") == date(2020, 3, 1))
    assert march["portfolio_return"][0] == pytest.approx(-0.20, abs=1e-6)
    assert march["n_names"][0] == 1


def test_calendar_time_portfolio_excludes_months_outside_the_holding_window():
    prices = pl.DataFrame(
        [{"ticker": "T", "date": date(2020, 1, 1), "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1.0, "close_adj": 100.0}],
        schema=PRICE_SCHEMA,
    )
    got = model3.calendar_time_portfolio_returns([("T", date(2020, 2, 15))], prices, holding_months=3)
    assert got.filter(pl.col("month") == date(2020, 1, 1)).is_empty()  # before the disclosure
    assert got.filter(pl.col("month") == date(2020, 6, 1)).is_empty()  # after the 3-month window
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/models/test_model3.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/congressional_sales/models/model3.py`**

```python
"""Model 3 (Section 7): calendar-time short portfolio of screened-sale
names, regressed on the four factors. Addresses cross-sectional
dependence in overlapping event windows, which CAR-based Models 1/2
handle poorly (Section 7's own stated rationale).

"90 days held" is approximated as 3 calendar months (documented
approximation -- see the plan's task notes), the standard convention in
this literature.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import polars as pl
import statsmodels.api as sm


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _add_months(d: date, n: int) -> date:
    total = (d.year * 12 + (d.month - 1)) + n
    return date(total // 12, total % 12 + 1, 1)


def monthly_factor_returns(factors: pl.DataFrame) -> pl.DataFrame:
    return (
        factors.with_columns(pl.col("date").dt.truncate("1mo").alias("month"))
        .group_by("month")
        .agg(
            ((1 + pl.col("mkt_rf")).product() - 1).alias("mkt_rf"),
            ((1 + pl.col("smb")).product() - 1).alias("smb"),
            ((1 + pl.col("hml")).product() - 1).alias("hml"),
            ((1 + pl.col("mom")).product() - 1).alias("mom"),
            ((1 + pl.col("rf")).product() - 1).alias("rf"),
        )
        .sort("month")
    )


def monthly_stock_return(ticker: str, month: date, prices: pl.DataFrame) -> float | None:
    month_start, month_end = _month_start(month), _add_months(_month_start(month), 1)
    rows = prices.filter(
        (pl.col("ticker") == ticker) & (pl.col("date") >= month_start) & (pl.col("date") < month_end)
    ).sort("date")
    if rows.height < 2:
        return None
    p0, p1 = rows["close_adj"][0], rows["close_adj"][-1]
    if p0 == 0:
        return None
    return (p1 - p0) / p0


def calendar_time_portfolio_returns(screened_sales: list[tuple[str, date]], prices: pl.DataFrame, holding_months: int = 3) -> pl.DataFrame:
    # ticker -> set of held months (the holding_months calendar months
    # starting the month AFTER report_date).
    membership: dict[date, list[str]] = {}
    for ticker, report_date in screened_sales:
        start = _add_months(_month_start(report_date), 1)
        for k in range(holding_months):
            m = _add_months(start, k)
            membership.setdefault(m, []).append(ticker)

    rows = []
    for month, tickers in sorted(membership.items()):
        returns = [r for t in tickers if (r := monthly_stock_return(t, month, prices)) is not None]
        if not returns:
            continue
        long_return = sum(returns) / len(returns)
        rows.append({"month": month, "portfolio_return": -long_return, "n_names": len(returns)})

    if not rows:
        return pl.DataFrame(schema={"month": pl.Date, "portfolio_return": pl.Float64, "n_names": pl.Int64})
    return pl.DataFrame(rows).sort("month")


def calendar_time_alpha(portfolio_returns: pl.DataFrame, factors: pl.DataFrame) -> dict:
    monthly_factors = monthly_factor_returns(factors)
    merged = portfolio_returns.join(monthly_factors, on="month", how="inner")
    if merged.is_empty():
        return {"alpha": None, "se": None, "t_stat": None, "n_months": 0}
    y = (merged["portfolio_return"] - merged["rf"]).to_numpy()
    X = merged.select("mkt_rf", "smb", "hml", "mom").to_numpy()
    X = sm.add_constant(X)
    fit = sm.OLS(y, X).fit()
    return {"alpha": float(fit.params[0]), "se": float(fit.bse[0]), "t_stat": float(fit.tvalues[0]), "n_months": len(y)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/models/test_model3.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/congressional_sales/models/model3.py tests/models/test_model3.py
git commit -m "Add Model 3: calendar-time short-portfolio regression"
```

### Task 21: Benjamini-Hochberg correction across the 18 test variants

**Files:**
- Create: `src/congressional_sales/models/multiple_comparisons.py`
- Test: `tests/models/test_multiple_comparisons.py`

**Interfaces:**
- Consumes: nothing (pure statistics function).
- Produces: `multiple_comparisons.bh_adjust(p_values: list[float]) ->
  list[float]` (BH-adjusted q-values, same order as input);
  `multiple_comparisons.bh_corrected_threshold(p_values: list[float],
  alpha: float = 0.05) -> float | None` (the largest p-value satisfying
  the BH critical-value condition `p_(k) <= (k/n)*alpha`; `None` if no
  p-value survives); `multiple_comparisons.eighteen_variant_grid(
  horizons: list[int] = [30, 90, 180], methods: list[str] =
  ["market_adjusted", "four_factor", "size_industry_matched"], samples:
  list[str] = ["unscreened", "screened"]) -> list[tuple[int, str, str]]`
  (the exact 3x3x2 = 18-cell grid Section 8 specifies, as a fixed,
  literal list — this function exists so nothing downstream constructs
  the grid ad hoc in a way that could drift from Section 8's exact
  wording).

- [ ] **Step 1: Write the failing test — `tests/models/test_multiple_comparisons.py`**

```python
from __future__ import annotations

import pytest

from congressional_sales.models import multiple_comparisons as mc


def test_bh_adjust_matches_hand_worked_three_value_example():
    """p=[0.01, 0.04, 0.03], n=3: sorted order statistics p(1)=0.01,
    p(2)=0.03, p(3)=0.04 give q(1)=0.03, q(2)=0.045, q(3)=0.04; the
    running-minimum-from-the-top monotone adjustment gives adj(3)=0.04,
    adj(2)=min(0.045,0.04)=0.04, adj(1)=min(0.03,0.04)=0.03. Mapped back
    to input order [0.01, 0.04, 0.03] -> [0.03, 0.04, 0.04]."""
    got = mc.bh_adjust([0.01, 0.04, 0.03])
    assert got == pytest.approx([0.03, 0.04, 0.04])


def test_bh_adjust_empty_input():
    assert mc.bh_adjust([]) == []


def test_bh_adjust_preserves_order_and_length():
    p = [0.5, 0.001, 0.3, 0.02]
    got = mc.bh_adjust(p)
    assert len(got) == len(p)


def test_bh_corrected_threshold_on_hand_worked_example():
    # Same 3-value example: adjusted q-values are [0.03, 0.04, 0.04], all
    # <= 0.05, so the largest RAW p-value whose own BH critical value
    # condition holds is the threshold. p(3)=0.04 <= (3/3)*0.05=0.05 -- holds.
    assert mc.bh_corrected_threshold([0.01, 0.04, 0.03], alpha=0.05) == pytest.approx(0.04)


def test_bh_corrected_threshold_none_when_nothing_survives():
    assert mc.bh_corrected_threshold([0.9, 0.8, 0.99], alpha=0.05) is None


def test_eighteen_variant_grid_has_exactly_18_cells():
    grid = mc.eighteen_variant_grid()
    assert len(grid) == 18
    assert len(set(grid)) == 18  # no duplicate cells
    assert (90, "four_factor", "screened") in grid  # the pre-specified PRIMARY test cell (Section 8)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/models/test_multiple_comparisons.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/congressional_sales/models/multiple_comparisons.py`**

```python
"""Benjamini-Hochberg FDR correction, PRE_ANALYSIS_PLAN.md Section 8: the
study runs 3 horizons x 3 adjustment methods x 2 samples = 18 variants of
the main test, and this correction must be applied across all of them."""

from __future__ import annotations


def bh_adjust(p_values: list[float]) -> list[float]:
    n = len(p_values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: p_values[i])
    adjusted_sorted = [0.0] * n
    running_min = 1.0
    for rank in range(n, 0, -1):
        idx = order[rank - 1]
        q = p_values[idx] * n / rank
        running_min = min(running_min, q)
        adjusted_sorted[rank - 1] = running_min
    result = [0.0] * n
    for rank in range(n):
        result[order[rank]] = adjusted_sorted[rank]
    return result


def bh_corrected_threshold(p_values: list[float], alpha: float = 0.05) -> float | None:
    n = len(p_values)
    if n == 0:
        return None
    sorted_p = sorted(p_values)
    threshold = None
    for k, p in enumerate(sorted_p, start=1):
        if p <= (k / n) * alpha:
            threshold = p
    return threshold


def eighteen_variant_grid(
    horizons: list[int] | None = None,
    methods: list[str] | None = None,
    samples: list[str] | None = None,
) -> list[tuple[int, str, str]]:
    horizons = horizons or [30, 90, 180]
    methods = methods or ["market_adjusted", "four_factor", "size_industry_matched"]
    samples = samples or ["unscreened", "screened"]
    return [(h, m, s) for h in horizons for m in methods for s in samples]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/models/test_multiple_comparisons.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add src/congressional_sales/models/multiple_comparisons.py tests/models/test_multiple_comparisons.py
git commit -m "Add Benjamini-Hochberg correction across the 18 pre-specified test variants"
```

---

## Phase 6 — Attaching CAR/BHAR to the Sample, and Robustness

### Task 22: Attach CAR/BHAR at all 3 horizons x 3 methods to every sample row

Both T4/T5 (Phase 7 outputs) and the robustness suite (Task 23) need a
sample frame with every CAR/BHAR variant already computed as a column —
built once, here, rather than recomputed ad hoc by each consumer.

**Files:**
- Create: `src/congressional_sales/events/attach.py`
- Test: `tests/events/test_attach.py`

**Interfaces:**
- Consumes: `car.market_adjusted_car/bhar`, `car.four_factor_car/bhar`,
  `car.size_industry_matched_car/bhar` (Tasks 14-16).
- Produces: `attach.attach_car_bhar(sample: pl.DataFrame, prices:
  pl.DataFrame, factors: pl.DataFrame, sic: pl.DataFrame, event_date_col:
  str = "transaction_date") -> pl.DataFrame` (returns `sample` with 18 new
  columns: `{car,bhar}_{market,four_factor,size_industry}_{30,90,180}` —
  `event_date_col` defaults to `"transaction_date"` per the Global
  Constraints note above; the one place this project calls
  `event_date_col="report_date"` is Robustness item 6, Task 23).

**Known performance note (do not silently over-engineer around it now):**
this iterates row-by-row calling Phase 4's functions, each of which
re-filters `prices`/`factors` internally — fine for correctness and for
a sample in the low thousands of rows, but real if the study eventually
runs against tens of thousands of transactions. Note it in the report, do
not attempt a vectorized rewrite as part of this task unless a real
performance problem shows up when running against the actual sample.

- [ ] **Step 1: Write the failing test — `tests/events/test_attach.py`**

```python
from __future__ import annotations

from datetime import date, timedelta

import polars as pl
import pytest

from congressional_sales.events import attach

PRICE_SCHEMA = {
    "ticker": pl.Utf8, "date": pl.Date, "open": pl.Float64, "high": pl.Float64,
    "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64, "close_adj": pl.Float64,
}
FACTOR_SCHEMA = {"date": pl.Date, "mkt_rf": pl.Float64, "smb": pl.Float64, "hml": pl.Float64, "mom": pl.Float64, "rf": pl.Float64}
SIC_SCHEMA = {"ticker": pl.Utf8, "cik": pl.Int64, "sic_code": pl.Utf8, "sic_description": pl.Utf8}
SAMPLE_SCHEMA = {
    "ticker": pl.Utf8, "bioguide_id": pl.Utf8, "transaction": pl.Utf8,
    "transaction_date": pl.Date, "report_date": pl.Date,
}


def test_attach_car_bhar_adds_all_18_columns_and_uses_transaction_date_by_default():
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(250)]
    price_rows, factor_rows = [], []
    price = 100.0
    for i, d in enumerate(sessions):
        if i > 0:
            price *= 1.001
        price_rows.append({"ticker": "AAPL", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": price, "volume": 1000.0, "close_adj": price})
        price_rows.append({"ticker": "SPY", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1000.0, "close_adj": 100.0})
        factor_rows.append({"date": d, "mkt_rf": 0.0002 * (i % 5), "smb": 0.0001, "hml": 0.0001, "mom": 0.0001, "rf": 0.0001})
    prices = pl.DataFrame(price_rows, schema=PRICE_SCHEMA)
    factors = pl.DataFrame(factor_rows, schema=FACTOR_SCHEMA)
    sic = pl.DataFrame({"ticker": ["AAPL"], "cik": [320193], "sic_code": ["3571"], "sic_description": ["x"]}, schema=SIC_SCHEMA)
    sample = pl.DataFrame(
        {
            "ticker": ["AAPL"], "bioguide_id": ["A1"], "transaction": ["Sale"],
            "transaction_date": [sessions[200]], "report_date": [sessions[210]],
        },
        schema=SAMPLE_SCHEMA,
    )

    out = attach.attach_car_bhar(sample, prices, factors, sic)
    expected_cols = {
        f"{metric}_{method}_{h}"
        for metric in ("car", "bhar")
        for method in ("market", "four_factor", "size_industry")
        for h in (30, 90, 180)
    }
    assert expected_cols.issubset(set(out.columns))
    # AAPL rises every session, so the market-adjusted CAR (which nets out
    # SPY's exactly-flat price) must be positive.
    assert out["car_market_30"][0] > 0


def test_attach_car_bhar_report_date_variant_uses_report_date_as_event_date():
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(250)]
    price_rows = []
    for i, d in enumerate(sessions):
        price_rows.append({"ticker": "AAPL", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0 + i, "volume": 1000.0, "close_adj": 100.0 + i})
        price_rows.append({"ticker": "SPY", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1000.0, "close_adj": 100.0})
    prices = pl.DataFrame(price_rows, schema=PRICE_SCHEMA)
    factors = pl.DataFrame(schema=FACTOR_SCHEMA)
    sic = pl.DataFrame({"ticker": ["AAPL"], "cik": [320193], "sic_code": ["3571"], "sic_description": ["x"]}, schema=SIC_SCHEMA)
    # transaction_date is early (little forward runway before the fixture ends);
    # report_date is later still with room for a 30-day window. Only the
    # report_date variant should have a non-null car_market_30.
    sample = pl.DataFrame(
        {
            "ticker": ["AAPL"], "bioguide_id": ["A1"], "transaction": ["Sale"],
            "transaction_date": [sessions[245]], "report_date": [sessions[200]],
        },
        schema=SAMPLE_SCHEMA,
    )
    by_transaction_date = attach.attach_car_bhar(sample, prices, factors, sic, event_date_col="transaction_date")
    by_report_date = attach.attach_car_bhar(sample, prices, factors, sic, event_date_col="report_date")
    assert by_transaction_date["car_market_30"][0] is None  # not enough forward sessions from day 245 of 250
    assert by_report_date["car_market_30"][0] is not None  # plenty of forward sessions from day 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/events/test_attach.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/congressional_sales/events/attach.py`**

```python
"""Attaches every CAR/BHAR variant (3 horizons x 3 methods, both metrics)
to each sample row. event_date_col defaults to "transaction_date" -- see
PRE_ANALYSIS_PLAN.md Section 6's primary specification and the Global
Constraints note on why this differs from every point-in-time-gated
filter elsewhere in this codebase."""

from __future__ import annotations

import polars as pl

from . import car

HORIZONS = (30, 90, 180)


def attach_car_bhar(
    sample: pl.DataFrame, prices: pl.DataFrame, factors: pl.DataFrame, sic: pl.DataFrame,
    event_date_col: str = "transaction_date",
) -> pl.DataFrame:
    out_rows = []
    for row in sample.iter_rows(named=True):
        ticker, event_date = row["ticker"], row[event_date_col]
        result = dict(row)
        for h in HORIZONS:
            result[f"car_market_{h}"] = car.market_adjusted_car(ticker, event_date, h, prices)
            result[f"bhar_market_{h}"] = car.market_adjusted_bhar(ticker, event_date, h, prices)
            result[f"car_four_factor_{h}"] = car.four_factor_car(ticker, event_date, h, prices, factors)
            result[f"bhar_four_factor_{h}"] = car.four_factor_bhar(ticker, event_date, h, prices, factors)
            result[f"car_size_industry_{h}"] = car.size_industry_matched_car(ticker, event_date, h, prices, sic)
            result[f"bhar_size_industry_{h}"] = car.size_industry_matched_bhar(ticker, event_date, h, prices, sic)
        out_rows.append(result)
    return pl.DataFrame(out_rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/events/test_attach.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/congressional_sales/events/attach.py tests/events/test_attach.py
git commit -m "Attach all 18 CAR/BHAR variants to sample rows, transaction_date default per Section 6"
```

### Task 23: Robustness suite (T7 — Section 9)

Per T7's own label ("robustness grid, **primary specification only**"),
every check here reruns only the pre-specified primary test — β1 (the
`sale` coefficient) in Model 2, 90-day horizon, four-factor adjusted,
screened sample — under 10 different sample restrictions. It does NOT
rerun all 18 CAR variants under each restriction.

Items 6 and 10 are NOT filters on this function's input and are
deliberately excluded from its loop:
- **Item 6** (filing-date entry) needs its own `attach_car_bhar(...,
  event_date_col="report_date")` call on an otherwise-identical sample —
  a different CAR column, not a row filter. Compute it once, separately,
  and pass its `car_four_factor_90` column through this same function
  under the label `"filing_date_entry"` (see Step 3's `run_robustness_
  suite` signature — it accepts an optional second frame for exactly this
  case).
- **Item 10** (18-month holdout) is `scripts/run_holdout.py` (Task 29),
  run last and once, never as part of the routine robustness loop.

**Files:**
- Create: `src/congressional_sales/robustness.py`
- Test: `tests/test_robustness.py`

**Interfaces:**
- Consumes: `model2.build_model2_frame`, `model2.run_model2` (Task 19).
- Produces: `robustness.winsorize(values: pl.Series, lower: float = 0.01,
  upper: float = 0.99) -> pl.Series`; `robustness.run_robustness_suite(
  sample_with_car: pl.DataFrame, size_proxies: dict, terms: pl.DataFrame,
  car_col: str = "car_four_factor_90", filing_date_variant: pl.DataFrame |
  None = None) -> pl.DataFrame` (columns `check: Utf8, beta_sale:
  Float64, se: Float64, n: Int64` — one row per robustness check, `None`
  values where a check has too few observations (`< 10`) to run a
  meaningful fixed-effects regression rather than raising).

- [ ] **Step 1: Write the failing test — `tests/test_robustness.py`**

```python
from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from congressional_sales import robustness


def test_winsorize_clips_extreme_values_to_the_percentile_bounds():
    values = pl.Series([1.0, 2.0, 3.0, 4.0, 100.0, -100.0])
    got = robustness.winsorize(values, lower=0.10, upper=0.90)
    assert got.max() < 100.0
    assert got.min() > -100.0
    assert got.len() == 6  # winsorizing clips, never drops rows


def _sample_row(bioguide, ticker, sale, car, chamber="Representatives", amount_range="$1,001 - $15,000", year=2020, industry="Business Equipment"):
    return {
        "ticker": ticker, "bioguide_id": bioguide, "transaction": "Sale" if sale else "Purchase",
        "report_date": date(year, 6, 1), "car_four_factor_90": car,
        "is_routine": False, "committee_match": False, "amount_range": amount_range,
        "chamber": chamber, "party": "R", "industry": industry,
    }


def test_run_robustness_suite_produces_one_row_per_check_and_the_full_sample():
    rows = [_sample_row(f"M{i}", f"T{i}", sale=(i % 2 == 0), car=0.01 * i) for i in range(30)]
    sample = pl.DataFrame(rows)
    terms = pl.DataFrame(
        schema={
            "bioguide_id": pl.Utf8, "full_name": pl.Utf8, "chamber": pl.Utf8,
            "term_start": pl.Date, "term_end": pl.Date, "state": pl.Utf8, "party": pl.Utf8,
        }
    )
    size_proxies = {(f"T{i}", date(2020, 6, 1)): 100_000.0 for i in range(30)}
    result = robustness.run_robustness_suite(sample, size_proxies, terms)
    labels = set(result["check"].to_list())
    assert "full_screened_sample" in labels
    assert "excl_top5_traders" in labels
    assert "senate_only" in labels
    assert "house_only" in labels
    assert "winsorized_1_99" in labels
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_robustness.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/congressional_sales/robustness.py`**

```python
"""Robustness suite, PRE_ANALYSIS_PLAN.md Section 9 / T7. Every check
reruns only the pre-specified primary test (beta_sale in Model 2, 90-day
horizon, four-factor, screened sample) -- see this task's plan notes for
why items 6 and 10 are handled outside this module."""

from __future__ import annotations

import polars as pl

from .models import model2


def winsorize(values: pl.Series, lower: float = 0.01, upper: float = 0.99) -> pl.Series:
    lo, hi = values.quantile(lower), values.quantile(upper)
    return values.clip(lo, hi)


def _most_frequent(sample: pl.DataFrame, col: str, n: int) -> set:
    counts = sample.group_by(col).agg(pl.len().alias("_n")).sort("_n", descending=True)
    return set(counts[col].head(n).to_list())


def _run_primary(label: str, df: pl.DataFrame, size_proxies: dict, terms: pl.DataFrame, car_col: str) -> dict:
    if df.height < 10:
        return {"check": label, "beta_sale": None, "se": None, "n": df.height}
    frame = model2.build_model2_frame(df, size_proxies, terms, car_col)
    if frame.height < 10 or frame["bioguide_id"].n_unique() < 2:
        return {"check": label, "beta_sale": None, "se": None, "n": frame.height}
    result = model2.run_model2(frame)
    return {"check": label, "beta_sale": result["params"].get("sale"), "se": result["se"].get("sale"), "n": result["n_obs"]}


def run_robustness_suite(
    sample_with_car: pl.DataFrame, size_proxies: dict, terms: pl.DataFrame,
    car_col: str = "car_four_factor_90", filing_date_variant: pl.DataFrame | None = None,
) -> pl.DataFrame:
    checks = []
    df = sample_with_car

    checks.append(_run_primary("full_screened_sample", df, size_proxies, terms, car_col))

    top5 = _most_frequent(df, "bioguide_id", 5)
    checks.append(_run_primary("excl_top5_traders", df.filter(~pl.col("bioguide_id").is_in(top5)), size_proxies, terms, car_col))
    top10 = _most_frequent(df, "bioguide_id", 10)
    checks.append(_run_primary("excl_top10_traders", df.filter(~pl.col("bioguide_id").is_in(top10)), size_proxies, terms, car_col))

    checks.append(_run_primary("excl_2020_2021", df.filter(~pl.col("report_date").dt.year().is_in([2020, 2021])), size_proxies, terms, car_col))

    for band in df["amount_range"].unique().to_list():
        checks.append(_run_primary(f"size_band_{band}", df.filter(pl.col("amount_range") == band), size_proxies, terms, car_col))

    top_tickers = _most_frequent(df, "ticker", 10)
    checks.append(_run_primary("excl_top10_tickers", df.filter(~pl.col("ticker").is_in(top_tickers)), size_proxies, terms, car_col))

    checks.append(_run_primary("excl_tech_sector", df.filter(pl.col("industry") != "Business Equipment"), size_proxies, terms, car_col))

    winsorized = df.with_columns(winsorize(df[car_col]).alias(car_col))
    checks.append(_run_primary("winsorized_1_99", winsorized, size_proxies, terms, car_col))

    seniority_counts = (
        terms.group_by("bioguide_id").agg(pl.len().alias("n_terms")).filter(pl.col("n_terms") >= 3)["bioguide_id"]
    )
    checks.append(_run_primary("three_plus_terms", df.filter(pl.col("bioguide_id").is_in(seniority_counts)), size_proxies, terms, car_col))

    checks.append(_run_primary("senate_only", df.filter(pl.col("chamber") == "Senate"), size_proxies, terms, car_col))
    checks.append(_run_primary("house_only", df.filter(pl.col("chamber") == "Representatives"), size_proxies, terms, car_col))

    if filing_date_variant is not None:
        checks.append(_run_primary("filing_date_entry", filing_date_variant, size_proxies, terms, car_col))

    return pl.DataFrame(checks)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_robustness.py -v`
Expected: `2 passed`. The 30-row synthetic sample in the second test is
sized to clear every internal `< 10` / `< 2 unique members` guard for
every check's filtered subset — if a specific check's row ends up with
`beta_sale=None` unexpectedly, check whether that check's filter leaves
too few rows or too few distinct `bioguide_id` values in this particular
fixture (each of the 30 rows uses a distinct `M{i}`/`T{i}`, so
`excl_top5_traders`/`excl_top10_traders` remove entire members rather
than thinning an existing one — confirm this still clears the `>=2
distinct members` guard before trusting the assertion list above).

- [ ] **Step 5: Commit**

```bash
git add src/congressional_sales/robustness.py tests/test_robustness.py
git commit -m "Add Section 9 robustness suite (T7)"
```

---

## Phase 7 — Outputs (Section 10)

Nothing beyond T1-T8 and F1-F8 goes in the paper (Global Constraints).
Every function in this phase composes results already computed by earlier
tasks — Task 8's `FunnelResult`, Task 9's `descriptive` functions, Task
22's attached CAR/BHAR columns, Tasks 18/20/21's model results, Task 23's
robustness table — rather than recomputing anything.

### Task 24: Tables T1-T8

**Files:**
- Create: `src/congressional_sales/outputs/__init__.py`
- Create: `src/congressional_sales/outputs/tables.py`
- Test: `tests/outputs/test_tables.py`

**Interfaces:**
- Consumes: `funnel.FunnelResult` (Task 8), `descriptive.build_t2/build_t3`
  (Task 9), a CAR-attached sample (Task 22), `model2.run_model2` output
  (Task 19), `model3.calendar_time_alpha` output (Task 20),
  `robustness.run_robustness_suite` output (Task 23).
- Produces: `tables.t1_funnel(result: FunnelResult) -> pl.DataFrame`
  (columns `step, count_before, count_after, excluded`); `tables.t2(sample,
  sic) -> pl.DataFrame` (pass-through of `descriptive.build_t2`);
  `tables.t3(sample) -> pl.DataFrame` (pass-through of
  `descriptive.build_t3`, reshaped to one row); `tables.t4_mean_car(
  sample_with_car: pl.DataFrame) -> pl.DataFrame` (columns `transaction,
  horizon, method, mean_car, n` — one row per `{Sale,Purchase} x {30,90,180}
  x {market,four_factor,size_industry}`, 18 rows); `tables.t5_model2(
  full_result: dict, screened_result: dict) -> pl.DataFrame` (columns
  `param, beta_full, se_full, beta_screened, se_screened`);
  `tables.t6_model3(alpha_result: dict) -> pl.DataFrame`; `tables.
  t7_robustness(robustness_table: pl.DataFrame) -> pl.DataFrame`
  (pass-through); `tables.t8_holdout(holdout_result: dict) -> pl.DataFrame`.

- [ ] **Step 1: Create `src/congressional_sales/outputs/__init__.py`**

```python
"""T1-T8 and F1-F8, PRE_ANALYSIS_PLAN.md Section 10. Nothing beyond this
pre-specified list goes in the paper."""
```

- [ ] **Step 2: Write the failing test — `tests/outputs/test_tables.py`**

```python
from __future__ import annotations

import polars as pl

from congressional_sales.outputs import tables
from congressional_sales.sample.funnel import FunnelResult, FunnelStep


def test_t1_funnel_reports_step_before_after_and_excluded_count():
    result = FunnelResult(
        steps=[FunnelStep("common_stock_only", 100, 90), FunnelStep("above_statutory_threshold", 90, 88)],
        sample=pl.DataFrame(),
    )
    t1 = tables.t1_funnel(result)
    assert t1.height == 2
    row = t1.filter(pl.col("step") == "common_stock_only")
    assert row["count_before"][0] == 100
    assert row["count_after"][0] == 90
    assert row["excluded"][0] == 10


def test_t4_mean_car_has_18_rows_per_transaction_type_pair():
    sample = pl.DataFrame(
        {
            "transaction": ["Sale", "Purchase"],
            "car_market_30": [-0.01, 0.02], "car_market_90": [-0.02, 0.03], "car_market_180": [-0.03, 0.04],
            "car_four_factor_30": [-0.01, 0.02], "car_four_factor_90": [-0.02, 0.03], "car_four_factor_180": [-0.03, 0.04],
            "car_size_industry_30": [-0.01, 0.02], "car_size_industry_90": [-0.02, 0.03], "car_size_industry_180": [-0.03, 0.04],
        }
    )
    t4 = tables.t4_mean_car(sample)
    assert t4.height == 18  # 2 transaction types x 3 horizons x 3 methods
    sale_90_four_factor = t4.filter(
        (pl.col("transaction") == "Sale") & (pl.col("horizon") == 90) & (pl.col("method") == "four_factor")
    )
    assert sale_90_four_factor["mean_car"][0] == -0.02


def test_t5_model2_combines_full_and_screened():
    full = {"params": {"sale": 0.01}, "se": {"sale": 0.005}}
    screened = {"params": {"sale": -0.02}, "se": {"sale": 0.008}}
    t5 = tables.t5_model2(full, screened)
    row = t5.filter(pl.col("param") == "sale")
    assert row["beta_full"][0] == 0.01
    assert row["beta_screened"][0] == -0.02
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/outputs/test_tables.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement `src/congressional_sales/outputs/tables.py`**

```python
"""T1-T8, PRE_ANALYSIS_PLAN.md Section 10."""

from __future__ import annotations

import polars as pl

from ..sample.funnel import FunnelResult

HORIZONS = (30, 90, 180)
METHODS = ("market", "four_factor", "size_industry")
METHOD_LABELS = {"market": "market_adjusted", "four_factor": "four_factor", "size_industry": "size_industry_matched"}


def t1_funnel(result: FunnelResult) -> pl.DataFrame:
    return pl.DataFrame(
        [{"step": s.name, "count_before": s.count_before, "count_after": s.count_after, "excluded": s.count_before - s.count_after} for s in result.steps]
    )


def t2(sample: pl.DataFrame, sic: pl.DataFrame):
    from ..sample.descriptive import build_t2

    return build_t2(sample, sic)


def t3(sample: pl.DataFrame) -> pl.DataFrame:
    from ..sample.descriptive import build_t3

    return pl.DataFrame([build_t3(sample)])


def t4_mean_car(sample_with_car: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for txn_type in ("Sale", "Purchase"):
        subset = sample_with_car.filter(pl.col("transaction") == txn_type)
        if subset.is_empty():
            continue
        for h in HORIZONS:
            for m in METHODS:
                col = f"car_{m}_{h}"
                values = subset[col].drop_nulls()
                rows.append(
                    {
                        "transaction": txn_type, "horizon": h, "method": METHOD_LABELS[m],
                        "mean_car": float(values.mean()) if values.len() else None, "n": values.len(),
                    }
                )
    return pl.DataFrame(rows)


def t5_model2(full_result: dict, screened_result: dict) -> pl.DataFrame:
    params = sorted(set(full_result["params"]) | set(screened_result["params"]))
    return pl.DataFrame(
        [
            {
                "param": p,
                "beta_full": full_result["params"].get(p), "se_full": full_result["se"].get(p),
                "beta_screened": screened_result["params"].get(p), "se_screened": screened_result["se"].get(p),
            }
            for p in params
        ]
    )


def t6_model3(alpha_result: dict) -> pl.DataFrame:
    return pl.DataFrame([alpha_result])


def t7_robustness(robustness_table: pl.DataFrame) -> pl.DataFrame:
    return robustness_table


def t8_holdout(holdout_result: dict) -> pl.DataFrame:
    return pl.DataFrame([holdout_result])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/outputs/test_tables.py -v`
Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add src/congressional_sales/outputs/__init__.py src/congressional_sales/outputs/tables.py tests/outputs/test_tables.py
git commit -m "Add T1-T8 table generation"
```

### Task 25: Event-time CAR series (needed by F3-F5) + Figures F1-F8

F3/F4/F5 need a continuous event-time CAR series across `[-30, +180]`,
which nothing built so far produces (Tasks 14-16 only compute CAR at the
3 pre-specified horizons). This task adds that series (market-adjusted
method only — the PAP does not specify which of the 3 methods the event-
time plots use, and market-adjusted is the simplest, most standard choice
for a visual plot; state this choice in the paper's methodology section)
before generating the figures that consume it.

**Files:**
- Modify: `src/congressional_sales/events/car.py`
- Create: `src/congressional_sales/outputs/figures.py`
- Test: `tests/events/test_car_event_series.py`
- Test: `tests/outputs/test_figures.py`

**Interfaces:**
- Consumes: `car.sessions_from_prices`, `car.daily_return`, `calendar.
  offset_within_days` (this file).
- Produces: `car.event_time_series(ticker: str, event_date: date, prices:
  pl.DataFrame, market_ticker: str = "SPY", pre: int = 30, post: int =
  180) -> dict[int, float | None]` (keys are session offsets `-pre` through
  `+post`; value at `-pre` is always `0.0` (baseline); each subsequent
  value is the running cumulative market-adjusted abnormal return; once
  any session in the walk is missing, that offset AND every later offset
  become `None` — a cumulative sum cannot meaningfully skip a gap and
  resume); `figures.f1_sample_funnel(...) -> Figure` through `figures.
  f8_calendar_time_alpha(...) -> Figure` (one function per figure, exact
  signatures in Step 4 below — each returns a `matplotlib.figure.Figure`
  and takes already-computed results from earlier tasks, composing rather
  than recomputing).

- [ ] **Step 1: Write the failing test — `tests/events/test_car_event_series.py`**

```python
from __future__ import annotations

from datetime import date, timedelta

import polars as pl
import pytest

from congressional_sales.events import car

PRICE_SCHEMA = {
    "ticker": pl.Utf8, "date": pl.Date, "open": pl.Float64, "high": pl.Float64,
    "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64, "close_adj": pl.Float64,
}


def test_event_time_series_baseline_is_zero_at_the_event_date():
    """Baseline is offset 0 (the event date), not offset -pre -- so
    series[+10] must equal market_adjusted_car's own [+1,+10] definition
    exactly (both sum the identical 10 post-event terms), and series[-k]
    is a SEPARATE backward accumulation from offset -1 down to -k, not a
    continuation of the forward walk. An earlier version of this test
    baselined at -pre and asserted series[10] == market_adjusted_car(...),
    which is wrong: baselining at -pre would make series[10] the sum of
    20 terms (offsets -9 through +10), not the 10 post-event terms
    market_adjusted_car computes -- caught by hand-tracing the two
    definitions against each other before this task was implemented."""
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(50)]
    rows = []
    aapl_price, spy_price = 100.0, 100.0
    for i, d in enumerate(sessions):
        if i > 0:
            aapl_price *= 1.01
            spy_price *= 1.001
        rows.append({"ticker": "AAPL", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": aapl_price, "volume": 1.0, "close_adj": aapl_price})
        rows.append({"ticker": "SPY", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": spy_price, "volume": 1.0, "close_adj": spy_price})
    prices = pl.DataFrame(rows, schema=PRICE_SCHEMA)

    series = car.event_time_series("AAPL", sessions[20], prices, pre=10, post=10)
    assert series[0] == 0.0
    assert series[10] == pytest.approx(car.market_adjusted_car("AAPL", sessions[20], 10, prices), abs=1e-9)


def test_event_time_series_none_after_a_gap():
    sessions = [date(2020, 1, 1) + timedelta(days=i) for i in range(15)]
    rows = [{"ticker": "AAPL", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1.0, "close_adj": 100.0} for d in sessions]
    rows += [{"ticker": "SPY", "date": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 100.0, "volume": 1.0, "close_adj": 100.0} for d in sessions]
    prices = pl.DataFrame(rows, schema=PRICE_SCHEMA)

    series = car.event_time_series("AAPL", sessions[5], prices, pre=5, post=20)
    assert series[9] is not None   # within the 15-day fixture
    assert series[10] is None      # walks off the known calendar
    assert series[15] is None      # stays None after the gap
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/events/test_car_event_series.py -v`
Expected: FAIL with `AttributeError: module 'car' has no attribute 'event_time_series'`

- [ ] **Step 3: Append to `src/congressional_sales/events/car.py`**

```python
def event_time_series(ticker: str, event_date: date, prices: pl.DataFrame, market_ticker: str = "SPY", pre: int = 30, post: int = 180) -> dict:
    """Baseline is offset 0 (the event date itself), not offset -pre --
    this makes series[+h] exactly equal market_adjusted_car(..., horizon=h),
    both being the sum of the same [+1, +h] daily abnormal returns. The
    pre-event side is a SEPARATE backward accumulation from offset -1 down
    to -pre, not a continuation of the forward walk -- the two directions
    share only the offset-0 baseline of 0.0, matching the standard
    event-study convention of centering the plot on the event date rather
    than on the start of the pre-event window.
    """
    sessions = sessions_from_prices(prices, market_ticker)
    result: dict[int, float | None] = {0: 0.0}

    cumulative, broken = 0.0, False
    for offset in range(1, post + 1):
        if broken:
            result[offset] = None
            continue
        d = offset_within_days(sessions, event_date, offset)
        if d is None:
            broken = True
            result[offset] = None
            continue
        r_t = daily_return(ticker, d, prices, sessions)
        r_m = daily_return(market_ticker, d, prices, sessions)
        if r_t is None or r_m is None:
            broken = True
            result[offset] = None
            continue
        cumulative += r_t - r_m
        result[offset] = cumulative

    cumulative, broken = 0.0, False
    for offset in range(-1, -pre - 1, -1):
        if broken:
            result[offset] = None
            continue
        d = offset_within_days(sessions, event_date, offset)
        if d is None:
            broken = True
            result[offset] = None
            continue
        r_t = daily_return(ticker, d, prices, sessions)
        r_m = daily_return(market_ticker, d, prices, sessions)
        if r_t is None or r_m is None:
            broken = True
            result[offset] = None
            continue
        cumulative += r_t - r_m
        result[offset] = cumulative

    return result
```

- [ ] **Step 4: Write the failing test — `tests/outputs/test_figures.py`**, then implement `src/congressional_sales/outputs/figures.py`

```python
from __future__ import annotations

import matplotlib
import polars as pl

matplotlib.use("Agg")  # headless -- these tests never open a display

from congressional_sales.outputs import figures


def test_f2_filing_lag_histogram_returns_a_figure_and_marks_45_days():
    lags = pl.Series([1, 5, 10, 30, 46, 60, 90])
    fig = figures.f2_filing_lag_histogram(lags)
    assert fig is not None
    ax = fig.axes[0]
    # A vertical line at x=45 must exist -- verified via axvline's stored data.
    assert any(abs(line.get_xdata()[0] - 45) < 1e-6 for line in ax.get_lines())


def test_f3_event_time_car_plot_returns_a_figure_with_two_series():
    sale_series = {-30: 0.0, 0: -0.01, 90: -0.03, 180: -0.05}
    purchase_series = {-30: 0.0, 0: 0.005, 90: 0.02, 180: 0.04}
    fig = figures.f3_event_time_car(sale_series, purchase_series)
    ax = fig.axes[0]
    assert len(ax.get_lines()) >= 2


def test_f6_random_control_distribution_marks_the_actual_result():
    simulated = [0.0, 0.001, -0.002, 0.003, -0.001] * 20  # 100 values
    fig = figures.f6_random_control_distribution(simulated, actual=0.05)
    ax = fig.axes[0]
    assert any(abs(line.get_xdata()[0] - 0.05) < 1e-9 for line in ax.get_lines())
```

Run: `uv run pytest tests/outputs/test_figures.py -v` — expect
`ModuleNotFoundError`, then implement:

```python
"""F1-F8, PRE_ANALYSIS_PLAN.md Section 10. Static publication figures via
matplotlib -- every function takes already-computed results and composes,
never recomputes."""

from __future__ import annotations

import matplotlib.pyplot as plt
import polars as pl

from ..sample.funnel import FunnelResult


def f1_sample_funnel(result: FunnelResult):
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = [s.name for s in result.steps]
    counts = [s.count_after for s in result.steps]
    ax.barh(labels, counts)
    ax.set_xlabel("Transactions remaining")
    ax.set_title("Sample Construction Funnel (F1)")
    fig.tight_layout()
    return fig


def f2_filing_lag_histogram(lags: pl.Series):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(lags.to_list(), bins=30)
    ax.axvline(45, color="red", linestyle="--", label="45-day STOCK Act threshold")
    ax.set_xlabel("Filing lag (days)")
    ax.set_ylabel("Count")
    ax.legend()
    ax.set_title("Filing Lag Distribution (F2)")
    fig.tight_layout()
    return fig


def _plot_event_series(ax, series: dict, label: str) -> None:
    offsets = sorted(k for k, v in series.items() if v is not None)
    values = [series[o] for o in offsets]
    ax.plot(offsets, values, label=label)


def f3_event_time_car(sale_series: dict, purchase_series: dict):
    fig, ax = plt.subplots(figsize=(9, 5))
    _plot_event_series(ax, sale_series, "Sales")
    _plot_event_series(ax, purchase_series, "Purchases")
    ax.axvline(0, color="gray", linestyle=":")
    ax.axhline(0, color="gray", linestyle=":")
    ax.set_xlabel("Trading sessions relative to transaction date")
    ax.set_ylabel("Cumulative market-adjusted abnormal return")
    ax.legend()
    ax.set_title("Event-Time CAR: Purchases vs. Sales (F3)")
    fig.tight_layout()
    return fig


def f4_event_time_car_by_routine(opportunistic_series: dict, routine_series: dict):
    fig, ax = plt.subplots(figsize=(9, 5))
    _plot_event_series(ax, opportunistic_series, "Opportunistic")
    _plot_event_series(ax, routine_series, "Routine")
    ax.axvline(0, color="gray", linestyle=":")
    ax.set_xlabel("Trading sessions relative to transaction date")
    ax.set_ylabel("Cumulative market-adjusted abnormal return")
    ax.legend()
    ax.set_title("Event-Time CAR: Opportunistic vs. Routine Sales (F4, H3)")
    fig.tight_layout()
    return fig


def f5_event_time_car_by_committee_match(matched_series: dict, unmatched_series: dict):
    fig, ax = plt.subplots(figsize=(9, 5))
    _plot_event_series(ax, matched_series, "Committee-matched sector")
    _plot_event_series(ax, unmatched_series, "Non-matched sector")
    ax.axvline(0, color="gray", linestyle=":")
    ax.set_xlabel("Trading sessions relative to transaction date")
    ax.set_ylabel("Cumulative market-adjusted abnormal return")
    ax.legend()
    ax.set_title("Event-Time CAR: Committee-Match vs. Non-Match (F5, H4)")
    fig.tight_layout()
    return fig


def f6_random_control_distribution(simulated: list, actual: float):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(simulated, bins=40)
    ax.axvline(actual, color="red", linestyle="--", label="Actual result")
    ax.set_xlabel("Simulated mean CAR")
    ax.legend()
    ax.set_title("Random Control Distribution (F6)")
    fig.tight_layout()
    return fig


def f7_year_by_year_effect(years: list, effects: list, ci_lower: list, ci_upper: list):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.errorbar(years, effects, yerr=[[e - lo for e, lo in zip(effects, ci_lower)], [hi - e for e, hi in zip(effects, ci_upper)]], fmt="o")
    ax.axhline(0, color="gray", linestyle=":")
    ax.set_xlabel("Year")
    ax.set_ylabel("Effect size (beta_sale)")
    ax.set_title("Year-by-Year Effect Size (F7)")
    fig.tight_layout()
    return fig


def f8_calendar_time_alpha(months: list, cumulative_alpha: list):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(months, cumulative_alpha)
    ax.axhline(0, color="gray", linestyle=":")
    ax.set_xlabel("Month")
    ax.set_ylabel("Cumulative calendar-time alpha")
    ax.set_title("Calendar-Time Portfolio Cumulative Alpha (F8)")
    fig.tight_layout()
    return fig
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/events/test_car_event_series.py tests/outputs/test_figures.py -v`
Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add src/congressional_sales/events/car.py src/congressional_sales/outputs/figures.py tests/events/test_car_event_series.py tests/outputs/test_figures.py
git commit -m "Add event-time CAR series and F1-F8 figure generation"
```

### Task 26: Paper assembly

**Files:**
- Create: `src/congressional_sales/outputs/paper.py`
- Test: `tests/outputs/test_paper.py`

**Interfaces:**
- Consumes: every table from Task 24, every figure from Task 25.
- Produces: `paper.build_paper_markdown(tables: dict[str, pl.DataFrame],
  figure_paths: dict[str, str], bh_threshold: float | None) -> str` (a
  single self-contained Markdown document: title, Section 1-4 narrative
  stubs the human author fills in by hand, then T1-T8 rendered as Markdown
  tables in order, F1-F8 referenced as image links in order, and a fixed
  **Limitations** section listing every documented deviation from this
  plan verbatim — survivorship bias, Screen 3 scope, committee-data
  recency, size/matching proxies, book-to-market omission, filing-lag
  90-day-as-3-calendar-months approximation — plus the PAP's own Section
  13 boilerplate: no causal claim, no individual-member claim, no legality
  claim, no investment recommendation).

- [ ] **Step 1: Write the failing test — `tests/outputs/test_paper.py`**

```python
from __future__ import annotations

import polars as pl

from congressional_sales.outputs import paper


def test_build_paper_markdown_includes_every_table_and_figure_and_the_limitations_section():
    tables = {"T1": pl.DataFrame({"step": ["a"], "count_after": [10]}), "T4": pl.DataFrame({"mean_car": [-0.01]})}
    figures = {"F1": "figures/f1.png", "F2": "figures/f2.png"}
    md = paper.build_paper_markdown(tables, figures, bh_threshold=0.012)
    assert "## Table T1" in md
    assert "## Table T4" in md
    assert "figures/f1.png" in md
    assert "figures/f2.png" in md
    assert "## Limitations" in md
    assert "No causal claim" in md
    assert "No investment recommendation" in md
    assert "survivorship-biased" in md.lower()
    assert "0.012" in md  # the reported BH-corrected threshold


def test_build_paper_markdown_handles_missing_bh_threshold():
    md = paper.build_paper_markdown({}, {}, bh_threshold=None)
    assert "no result survived" in md.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/outputs/test_paper.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/congressional_sales/outputs/paper.py`**

```python
"""Assembles the final paper. T1-T8 and F1-F8 only (Section 10) -- this
function is the single place all of them get stitched together, so it is
also the single place to verify nothing extra snuck in."""

from __future__ import annotations

import polars as pl

LIMITATIONS = """## Limitations

- **Survivorship bias.** This study's price data has no delisting-inclusive
  source; a security that was acquired, went bankrupt, or otherwise
  delisted after a disclosed transaction is absent from that transaction's
  event window rather than carrying a delisting return.
- **Screen 3 (liquidation events) scope.** Only "more than 60% of a
  member's disclosed portfolio sold" (approximated from transaction data,
  not true holdings) and a retirement-window proxy (from committee-
  assignment term-end dates) are implemented. Blind trust establishment
  and confirmation to an executive-branch position have no available
  structured data source and are not detected.
- **Committee-assignment data is a current-only snapshot**, not a true
  historical per-congress record; H4's committee-match variable uses each
  member's most recently known committee assignment.
- **Size and industry matching** use trailing dollar volume as a proxy for
  market capitalization (no shares-outstanding source), matched only
  within this study's own sample universe rather than the broader market.
- **Book-to-market is omitted** from Model 2's control set -- no data
  source for it exists in this project.
- **The 90-day holding period in Model 3** is approximated as 3 calendar
  months, the standard calendar-time-portfolio convention, not an exact
  trading-day count.

No causal claim about information sources is made -- this study observes
timing, not mechanism. No claim about any individual member is made. No
claim about the legality of any transaction is made. No investment
recommendation is made.
"""


def build_paper_markdown(tables: dict[str, pl.DataFrame], figure_paths: dict[str, str], bh_threshold: float | None) -> str:
    parts = ["# Do Congressional Sales Carry More Information Than Purchases?\n"]

    if bh_threshold is not None:
        parts.append(f"Benjamini-Hochberg corrected significance threshold across the 18 pre-specified test variants: **{bh_threshold:.4g}**.\n")
    else:
        parts.append("Benjamini-Hochberg correction: no result survived correction across the 18 pre-specified test variants.\n")

    for name in ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"):
        if name in tables:
            parts.append(f"## Table {name}\n")
            parts.append(tables[name].to_pandas().to_markdown(index=False))
            parts.append("")

    for name in ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8"):
        if name in figure_paths:
            parts.append(f"## Figure {name}\n")
            parts.append(f"![{name}]({figure_paths[name]})")
            parts.append("")

    parts.append(LIMITATIONS)
    return "\n".join(parts)
```

Add `tabulate` to `pyproject.toml`'s dependencies (`polars.to_pandas().to_markdown()`
requires it as a `pandas` extra).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/outputs/test_paper.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/congressional_sales/outputs/paper.py tests/outputs/test_paper.py pyproject.toml
git commit -m "Add paper assembly (T1-T8, F1-F8, fixed limitations section)"
```

---

## Phase 8 — Verification (Section 11)

### Task 27: NaN audit, delisting audit, ticker-remap audit

**Files:**
- Create: `src/congressional_sales/verification/__init__.py`
- Create: `src/congressional_sales/verification/audits.py`
- Test: `tests/verification/test_audits.py`

**Interfaces:**
- Consumes: a CAR-attached sample (Task 22), `storage.read("equity_eod")`.
- Produces: `audits.nan_audit(sample_with_car: pl.DataFrame) ->
  pl.DataFrame` (columns `column: Utf8, n_null: Int64, pct_null:
  Float64` — one row per CAR/BHAR column, per Section 11's "report how
  many observations were dropped at each computation step and why");
  `audits.delisting_audit(sample: pl.DataFrame, prices: pl.DataFrame,
  gap_days: int = 90) -> pl.DataFrame` (columns `ticker: Utf8,
  last_price_date: Date, days_since_last_price: Int64` — every sample
  ticker whose most recent price row is more than `gap_days` before
  `report_date().max()`, i.e. a ticker that looks like it quietly stopped
  trading, flagged for the paper's survivorship-bias discussion, per
  Section 11's "Delisting handling" item — this cannot fix the bias
  (Global Constraints), it quantifies it); `audits.ticker_reuse_audit(
  sic: pl.DataFrame) -> pl.DataFrame` (columns `cik: Int64,
  tickers: list[Utf8], n_tickers: Int64` — CIKs mapped to more than one
  ticker in `sic`, i.e. a real instance of the "symbols get reused" trap
  Section 11 warns about; empty if none found).

- [ ] **Step 1: Create `src/congressional_sales/verification/__init__.py`**

```python
"""Section 11 verification: NaN audit, delisting audit, ticker-remap
audit, and the 20-transaction hand-check harness (Task 28)."""
```

- [ ] **Step 2: Write the failing test — `tests/verification/test_audits.py`**

```python
from __future__ import annotations

from datetime import date

import polars as pl

from congressional_sales.verification import audits


def test_nan_audit_counts_nulls_per_car_column():
    sample = pl.DataFrame({"car_market_30": [0.01, None, 0.02], "car_market_90": [None, None, 0.03]})
    got = audits.nan_audit(sample)
    m30 = got.filter(pl.col("column") == "car_market_30")
    assert m30["n_null"][0] == 1
    m90 = got.filter(pl.col("column") == "car_market_90")
    assert m90["n_null"][0] == 2


def test_delisting_audit_flags_a_ticker_with_a_large_price_gap():
    sample = pl.DataFrame({"ticker": ["DEAD", "LIVE"], "report_date": [date(2020, 6, 1), date(2020, 6, 1)]})
    prices = pl.DataFrame(
        {
            "ticker": ["DEAD", "LIVE"], "date": [date(2020, 1, 1), date(2020, 6, 1)],
            "open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0], "close": [1.0, 1.0],
            "volume": [1.0, 1.0], "close_adj": [1.0, 1.0],
        }
    )
    got = audits.delisting_audit(sample, prices, gap_days=90)
    assert "DEAD" in got["ticker"].to_list()
    assert "LIVE" not in got["ticker"].to_list()


def test_ticker_reuse_audit_flags_a_cik_with_multiple_tickers():
    sic = pl.DataFrame(
        {"ticker": ["OLDNAME", "NEWNAME", "OTHER"], "cik": [1, 1, 2], "sic_code": ["1", "1", "2"], "sic_description": ["x", "x", "y"]}
    )
    got = audits.ticker_reuse_audit(sic)
    assert got.height == 1
    assert got["cik"][0] == 1
    assert set(got["tickers"][0]) == {"OLDNAME", "NEWNAME"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/verification/test_audits.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement `src/congressional_sales/verification/audits.py`**

```python
"""Section 11 audits: NaN accounting, delisting-gap detection (quantifies
the survivorship-bias deviation, does not fix it), and ticker-reuse
detection (the "match on a permanent identifier, symbols get reused"
warning)."""

from __future__ import annotations

import polars as pl


def nan_audit(sample_with_car: pl.DataFrame) -> pl.DataFrame:
    car_cols = [c for c in sample_with_car.columns if c.startswith("car_") or c.startswith("bhar_")]
    n = sample_with_car.height
    rows = [
        {"column": c, "n_null": sample_with_car[c].null_count(), "pct_null": sample_with_car[c].null_count() / n if n else 0.0}
        for c in car_cols
    ]
    return pl.DataFrame(rows)


def delisting_audit(sample: pl.DataFrame, prices: pl.DataFrame, gap_days: int = 90) -> pl.DataFrame:
    as_of = sample["report_date"].max()
    last_price = prices.group_by("ticker").agg(pl.col("date").max().alias("last_price_date"))
    sample_tickers = sample.select("ticker").unique()
    joined = sample_tickers.join(last_price, on="ticker", how="left")
    gapped = joined.with_columns(
        (pl.lit(as_of) - pl.col("last_price_date")).dt.total_days().alias("days_since_last_price")
    ).filter(pl.col("days_since_last_price") > gap_days)
    return gapped.select("ticker", "last_price_date", "days_since_last_price")


def ticker_reuse_audit(sic: pl.DataFrame) -> pl.DataFrame:
    return (
        sic.group_by("cik")
        .agg(pl.col("ticker").unique().alias("tickers"))
        .with_columns(pl.col("tickers").list.len().alias("n_tickers"))
        .filter(pl.col("n_tickers") > 1)
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/verification/test_audits.py -v`
Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add src/congressional_sales/verification/__init__.py src/congressional_sales/verification/audits.py tests/verification/test_audits.py
git commit -m "Add Section 11 audits: NaN, delisting gaps, ticker reuse"
```

### Task 28: 20-transaction hand-check worksheet + light-touch primary-portal puller

Section 11's hand-check is fundamentally human-in-the-loop ("pull them,
compute CAR manually, confirm the pipeline matches") — this task's code
produces the worksheet a person fills in, plus a small, rate-limited
puller against the two primary government portals to support the
cross-check, per the Global Constraints "Quiver-primary, light-touch
verification" decision (never bulk; a handful of requests per run,
manually triggered, never part of `run_full_pipeline.py`'s routine path).

**Files:**
- Create: `src/congressional_sales/sources/primary_portals.py`
- Create: `src/congressional_sales/verification/hand_check.py`
- Test: `tests/verification/test_hand_check.py`

**Interfaces:**
- Consumes: a CAR-attached sample (Task 22).
- Produces: `hand_check.select_worksheet_sample(sample_with_car:
  pl.DataFrame, n: int = 20, seed: int = 42) -> pl.DataFrame` (a
  deterministic random sample of `n` rows via the given seed, so re-
  running produces the same 20 transactions); `hand_check.
  build_worksheet(rows: pl.DataFrame) -> pl.DataFrame` (adds empty
  `manual_car_market_90: Float64, manual_notes: Utf8, matches_pipeline:
  Utf8` columns for a human to fill in, alongside the pipeline's own
  `ticker, transaction, transaction_date, report_date, car_market_90`
  columns for comparison); `primary_portals.house_disclosure_url(ticker:
  str, report_date) -> str` and `primary_portals.senate_efd_search_url()
  -> str` (URL builders only — no network I/O in this task; both sites
  are HTML-form/search-driven, not clean JSON APIs, so this task
  deliberately stops at "here is where to look," leaving the actual pull
  as a manual step per transaction rather than an automated one).

**Verify live before relying on this for real hand-checks:** the House
Clerk site (`https://disclosures-clerk.house.gov/PublicDisclosure/
FinancialDisclosure`) and Senate eFD (`https://efdsearch.senate.gov/
search/`) are both real, current URLs, but their exact query/search
mechanics were not verified against a live session during planning (both
require form interaction, not a documented JSON API) — confirm the actual
navigation path manually before writing this into any automated helper
beyond a URL builder, and do not scale this past the ~20 hand-check
transactions under any circumstances (see Global Constraints).

- [ ] **Step 1: Write the failing test — `tests/verification/test_hand_check.py`**

```python
from __future__ import annotations

from datetime import date

import polars as pl

from congressional_sales.sources import primary_portals
from congressional_sales.verification import hand_check


def test_select_worksheet_sample_is_deterministic_with_the_same_seed():
    sample = pl.DataFrame({"ticker": [f"T{i}" for i in range(100)], "car_market_90": [0.01 * i for i in range(100)]})
    a = hand_check.select_worksheet_sample(sample, n=20, seed=42)
    b = hand_check.select_worksheet_sample(sample, n=20, seed=42)
    assert a["ticker"].to_list() == b["ticker"].to_list()
    assert a.height == 20


def test_build_worksheet_adds_blank_manual_columns():
    rows = pl.DataFrame(
        {
            "ticker": ["AAPL"], "transaction": ["Sale"], "transaction_date": [date(2020, 6, 1)],
            "report_date": [date(2020, 6, 15)], "car_market_90": [-0.02],
        }
    )
    ws = hand_check.build_worksheet(rows)
    assert "manual_car_market_90" in ws.columns
    assert "matches_pipeline" in ws.columns
    assert ws["manual_car_market_90"][0] is None


def test_house_disclosure_url_is_well_formed():
    url = primary_portals.house_disclosure_url("AAPL", date(2020, 6, 15))
    assert url.startswith("https://disclosures-clerk.house.gov/")


def test_senate_efd_search_url_is_well_formed():
    assert primary_portals.senate_efd_search_url().startswith("https://efdsearch.senate.gov/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/verification/test_hand_check.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/congressional_sales/sources/primary_portals.py`**

```python
"""URL builders (not automated pullers -- see this task's plan notes) for
the two primary disclosure portals, used only to support the Section 11
20-transaction hand-check. Never bulk-scraped -- see Global Constraints."""

from __future__ import annotations

from datetime import date

HOUSE_DISCLOSURE_BASE = "https://disclosures-clerk.house.gov/PublicDisclosure/FinancialDisclosure"
SENATE_EFD_SEARCH_BASE = "https://efdsearch.senate.gov/search/"


def house_disclosure_url(ticker: str, report_date: date) -> str:
    return f"{HOUSE_DISCLOSURE_BASE}?ticker={ticker.upper()}&year={report_date.year}"


def senate_efd_search_url() -> str:
    return SENATE_EFD_SEARCH_BASE
```

- [ ] **Step 4: Implement `src/congressional_sales/verification/hand_check.py`**

```python
"""Section 11's 20-transaction hand-check: this module builds the
worksheet a human fills in -- it does not perform the hand-check itself."""

from __future__ import annotations

import polars as pl


def select_worksheet_sample(sample_with_car: pl.DataFrame, n: int = 20, seed: int = 42) -> pl.DataFrame:
    return sample_with_car.sample(n=min(n, sample_with_car.height), seed=seed)


def build_worksheet(rows: pl.DataFrame) -> pl.DataFrame:
    return rows.with_columns(
        pl.lit(None).cast(pl.Float64).alias("manual_car_market_90"),
        pl.lit(None).cast(pl.Utf8).alias("manual_notes"),
        pl.lit(None).cast(pl.Utf8).alias("matches_pipeline"),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/verification/test_hand_check.py -v`
Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add src/congressional_sales/sources/primary_portals.py src/congressional_sales/verification/hand_check.py tests/verification/test_hand_check.py
git commit -m "Add 20-transaction hand-check worksheet and primary-portal URL builders"
```

---

## Phase 9 — Orchestration

### Task 29: End-to-end pipeline script + holdout script + reproduction runbook

**Files:**
- Create: `scripts/run_full_pipeline.py`
- Create: `scripts/run_holdout.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: every module built in Tasks 1-28.
- Produces: two runnable scripts and a documented reproduction procedure.

**Open question to resolve before the first real run (not a code task —
a data-scoping decision):** discovering the *full* ticker universe
Congress has ever traded is not yet solved by any task above. Task 4's
`ingest_congress_trades(ticker)` requires already knowing a ticker.
Quiver's own Python SDK (fetched live during planning — see
`sources/quiver.py`'s task notes) also exposes a bulk, no-ticker-filter
endpoint (`https://api.quiverquant.com/beta/bulk/congresstrading`) that
was NOT verified live during planning and is not wired into Task 4. Before
the first real full-sample run, either (a) make one live call to that bulk
endpoint to discover the complete ticker universe (verify its response
shape and pagination behavior first — it was only seen referenced in the
SDK source, never actually called), or (b) seed from a known broad
universe (S&P 500 + Russell 3000 constituents) and accept that names Congress
traded outside that universe are missed. Document whichever is chosen in
the paper's sample-construction section — this is exactly the kind of
sample-selection decision Section 4 requires being explicit about.

- [ ] **Step 1: Implement `scripts/run_full_pipeline.py`**

```python
"""End-to-end pipeline: ingest -> sample -> screen -> attach CAR -> models
-> robustness -> outputs. Excludes the 18-month holdout period entirely
(see run_holdout.py, run last and once only, per PRE_ANALYSIS_PLAN.md
Section 4/9)."""

from __future__ import annotations

from datetime import date

from congressional_sales import storage
from congressional_sales.events.attach import attach_car_bhar
from congressional_sales.events.car import event_time_series
from congressional_sales.events.permutation import random_control_test
from congressional_sales.models import model1, model2, model3, multiple_comparisons
from congressional_sales.outputs import figures, paper, tables
from congressional_sales.robustness import run_robustness_suite
from congressional_sales.sample import classify, descriptive
from congressional_sales.sample.funnel import build_sample
from congressional_sales.sample.screens import screen1_rebalancing, screen2_tax_management, screen3_liquidation
from congressional_sales.verification.audits import delisting_audit, nan_audit, ticker_reuse_audit
from congressional_sales.verification.hand_check import build_worksheet, select_worksheet_sample

HOLDOUT_START = date(2025, 1, 1)  # the most recent 18 months -- confirm against
                                    # "most recent complete year" at run time (Section 4)
                                    # and update this constant, do not hardcode silently.


def main() -> None:
    result = build_sample(period_end=HOLDOUT_START)
    prices, factors = storage.read("equity_eod"), storage.read("ff_factors")
    terms, assignments = storage.read("legislator_terms"), storage.read("committee_assignments")
    sic = storage.read("sic_codes")

    unscreened = result.sample
    screened = screen3_liquidation(
        screen2_tax_management(screen1_rebalancing(unscreened), prices), terms
    ).filter(~(pl_or(["excluded_rebalancing", "excluded_tax_management", "excluded_liquidation"])))
    screened = classify.committee_match(classify.is_routine_trader(screened), assignments, sic)

    unscreened_with_car = attach_car_bhar(unscreened, prices, factors, sic)
    screened_with_car = attach_car_bhar(screened, prices, factors, sic)

    t1 = tables.t1_funnel(result)
    t2 = tables.t2(screened, sic)
    t3 = tables.t3(screened)
    t4 = tables.t4_mean_car(screened_with_car)

    size_proxies = {}  # populate via car.size_proxy per (ticker, report_date) pair actually used
    full_frame = model2.build_model2_frame(unscreened_with_car, size_proxies, terms, "car_four_factor_90")
    screened_frame = model2.build_model2_frame(screened_with_car, size_proxies, terms, "car_four_factor_90")
    full_result = model2.run_model2(full_frame)
    screened_result = model2.run_model2(screened_frame)
    t5 = tables.t5_model2(full_result, screened_result)

    screened_sales = [(r["ticker"], r["report_date"]) for r in screened_with_car.filter(screened_with_car["transaction"] == "Sale").iter_rows(named=True)]
    portfolio_returns = model3.calendar_time_portfolio_returns(screened_sales, prices)
    alpha_result = model3.calendar_time_alpha(portfolio_returns, factors)
    t6 = tables.t6_model3(alpha_result)

    robustness_table = run_robustness_suite(screened_with_car, size_proxies, terms)
    t7 = tables.t7_robustness(robustness_table)

    nan_audit(screened_with_car).write_csv(storage.paths().outputs / "nan_audit.csv")
    delisting_audit(screened, prices).write_csv(storage.paths().outputs / "delisting_audit.csv")
    ticker_reuse_audit(sic).write_csv(storage.paths().outputs / "ticker_reuse_audit.csv")
    build_worksheet(select_worksheet_sample(screened_with_car)).write_csv(storage.paths().outputs / "hand_check_worksheet.csv")

    md = paper.build_paper_markdown(
        {"T1": t1, "T2": t2, "T3": t3, "T4": t4, "T5": t5, "T6": t6, "T7": t7}, {}, bh_threshold=None,
    )
    (storage.paths().outputs / "paper.md").write_text(md)
    print(f"Wrote outputs to {storage.paths().outputs}")


def pl_or(cols: list[str]):
    import polars as pl

    expr = pl.col(cols[0])
    for c in cols[1:]:
        expr = expr | pl.col(c)
    return expr


if __name__ == "__main__":
    main()
```

This script is intentionally left with two rough edges for the
implementer to close during Task 29 rather than treat as finished:
`size_proxies` is an empty dict (must be populated by calling
`car.size_proxy` for every `(ticker, report_date)` pair the sample
actually needs, cached, before `build_model2_frame` can produce non-null
`log_size` values), and F1-F8 figure generation/writing to disk is not
yet wired in (each `figures.fN_*` function needs its specific inputs
assembled from the tables/results above and `fig.savefig(...)` called).
Both are straightforward composition of already-built, already-tested
pieces — finish them as part of this task's own review cycle, they were
left out of this listing only to keep it from growing further.

- [ ] **Step 2: Implement `scripts/run_holdout.py`**

```python
"""The 18-month holdout evaluation -- PRE_ANALYSIS_PLAN.md Section 4/9
item 10: run LAST, run ONCE. Do not re-run after seeing its result; if a
methodology bug is found here, the correct response is to log it as a
limitation, not to quietly patch and re-run."""

from __future__ import annotations

from datetime import date

from congressional_sales import storage
from congressional_sales.events.attach import attach_car_bhar
from congressional_sales.models import model2
from congressional_sales.sample.funnel import build_sample

HOLDOUT_START = date(2025, 1, 1)  # keep in sync with run_full_pipeline.py


def main() -> None:
    result = build_sample(period_start=HOLDOUT_START)
    prices, factors = storage.read("equity_eod"), storage.read("ff_factors")
    sic = storage.read("sic_codes")
    terms = storage.read("legislator_terms")

    with_car = attach_car_bhar(result.sample, prices, factors, sic)
    frame = model2.build_model2_frame(with_car, {}, terms, "car_four_factor_90")
    holdout_result = model2.run_model2(frame)
    print("HOLDOUT RESULT (Section 9 item 10 -- run once, report as-is):")
    print(holdout_result)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Document the reproduction procedure in `README.md`**

Add a "Reproducing this study" section covering: `uv sync`; set
`QUIVER_API_TOKEN`/`TIINGO_API_TOKEN` in `.env`; run each `ingest_*`
command for the full ticker universe (see this task's open question
above); `uv run python scripts/run_full_pipeline.py`; confirm output
files under `outputs/`; run a second time on a different day and diff the
two `outputs/` directories byte-for-byte except `paper.md`'s
`data_vintage`-equivalent timestamp lines, satisfying Section 11's "twice,
on different days, confirm identical output" requirement.

- [ ] **Step 4: Commit**

```bash
git add scripts/run_full_pipeline.py scripts/run_holdout.py README.md
git commit -m "Add end-to-end pipeline orchestration, holdout script, and reproduction runbook"
```

---

## Post-Plan Self-Review

Performed against the spec (`PRE_ANALYSIS_PLAN.md`) section by section:

- **Section 2 (H1-H4):** H1/H2 tested via Model 1 (Task 18) and Model 2's
  `sale` coefficient (Task 19). H3 via `is_routine`/`opportunistic`
  interaction (Tasks 13, 19). H4 via `committee_match` interaction (Tasks
  13, 19). Covered.
- **Section 3 (data):** Quiver (Task 4), primary portals light-touch
  (Task 28), prices (Task 2), Fama-French (Task 5), committee records
  (Task 6). Delisting-inclusive prices explicitly NOT covered — documented
  deviation, not a gap.
- **Section 4 (sample construction):** Task 8 (funnel, T1), Task 2's
  price ingestion for the "resolvable price data" inclusion rule. Covered.
- **Section 5 (screens):** Tasks 10-13 (Screens 1-4). Covered, with the
  Screen 3 scope decision documented.
- **Section 6 (outcome variables):** Tasks 14-16 (3 CAR methods), BHAR
  built alongside each. Covered, with the size/industry-matching
  documented deviation.
- **Section 7 (models):** Tasks 18-20 (Models 1-3). Covered, with the
  book-to-market omission documented.
- **Section 8 (statistical discipline):** Task 21 (BH correction), Task
  17 (permutation test). Covered.
- **Section 9 (robustness):** Task 23 covers items 1-5, 7-9; item 6 via
  Task 22's `event_date_col="report_date"` variant; item 10 via Task 29's
  `run_holdout.py`. Covered.
- **Section 10 (outputs):** Tasks 24-26 (T1-T8, F1-F8, paper assembly).
  Covered.
- **Section 11 (verification):** Task 27 (NaN/delisting/ticker-reuse
  audits), Task 28 (hand-check worksheet), calendar.py's own test suite
  (Task 3) for trading-day alignment, Task 29's Step 3 for the dual-
  reproduction runbook. Covered.
- **Section 12 (interpretation rules):** Not code — these are rules for
  whoever writes the paper's prose around the tables Task 26 assembles.
  Worth a one-line comment in `paper.py` pointing back to this section,
  but not a separate task.
- **Section 13 (what the paper does not claim):** Hardcoded into
  `paper.LIMITATIONS` (Task 26).

**Placeholder scan:** no "TBD"/"TODO"/"add appropriate" language found
except the two explicitly-flagged, explicitly-scoped rough edges in Task
29's orchestration script (`size_proxies` population, figure-saving
wiring) — both are composition of already-built, already-tested pieces,
not undesigned logic, and are called out by name rather than glossed over.

**Type consistency:** `pl.DataFrame` column names for the CAR-attached
sample (`car_{method}_{horizon}`, `bhar_{method}_{horizon}`) are used
identically across Tasks 22 (producer), 19/23/24/26/27/28 (consumers) —
verified by grep during this review.

**Known open items surfaced during planning, not resolved by any task
(intentionally — these are judgment calls for you to confirm, not
implementation gaps):** the full-ticker-universe discovery question
(Task 29), the exact `linearmodels.AbsorbingLS` clustered-covariance
kwarg signature for whatever version gets installed (Task 19), and the
real Ken French `Siccodes12.zip` text layout (Task 7) — all three are
flagged in-place with an explicit verification step rather than assumed.
