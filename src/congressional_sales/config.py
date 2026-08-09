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

    def table(self, name: str) -> Path:
        return self.parquet / name

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
