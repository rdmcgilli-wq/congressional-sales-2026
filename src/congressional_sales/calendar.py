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

from . import storage


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
