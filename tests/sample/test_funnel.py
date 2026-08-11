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
    # 300 trading days of prior history (ends 2020-02-24, before report_date)
    # plus 200 trading days of forward history (starts the day after
    # report_date) -- this test's target is the common_stock_only step, so
    # the fixture must also clear the later min_prior_trading_history and
    # full_forward_window steps or the final `result.sample` assertion below
    # would fail for reasons unrelated to ticker_type. See task-8-report.md
    # for why the brief's original prior-only fixture couldn't do this.
    prices = _trading_dates(date(2019, 1, 1), 300) + _trading_dates(date(2020, 6, 16), 200)
    _seed_prices("AAPL", prices)
    _seed_prices("MUNIBOND", prices)
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
    # THIN: only 10 trading days before report_date. THIN is excluded by the
    # prior-history floor itself, so it never reaches full_forward_window --
    # it doesn't need forward coverage seeded.
    _seed_prices("THIN", _trading_dates(date(2020, 5, 1), 10))
    # RICH: 300 trading days before report_date (well over the 60-day floor)
    # plus 200 trading days after it (well over the 180-day forward floor),
    # so RICH also clears full_forward_window and this test's `result.sample`
    # assertion isolates the prior-history floor, not an unrelated step.
    _seed_prices("RICH", _trading_dates(date(2019, 1, 1), 300) + _trading_dates(date(2020, 6, 16), 200))
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
    # Prior + forward coverage (see comment in test_common_stock_only_...
    # above) so this fixture clears every step and the height==1 assertion
    # actually isolates dedup behavior rather than an unrelated exclusion.
    _seed_prices("AAPL", _trading_dates(date(2019, 1, 1), 300) + _trading_dates(date(2020, 6, 16), 200))
    result = funnel.build_sample(period_start=date(2020, 1, 1), period_end=date(2020, 12, 31))
    assert result.sample.height == 1


def test_funnel_steps_are_monotonically_non_increasing():
    report = date(2020, 6, 15)
    _seed_trade("AAPL", "A001", report, report, 1001.0)
    _seed_prices("AAPL", _trading_dates(date(2019, 1, 1), 300))
    result = funnel.build_sample(period_start=date(2020, 1, 1), period_end=date(2020, 12, 31))
    for step in result.steps:
        assert step.count_after <= step.count_before


def test_directional_transaction_only_normalizes_real_sale_variants():
    # Real Quiver data uses "Sale (Full)"/"Sale (Partial)", not a bare
    # "Sale" string (confirmed against this study's sibling private-repo
    # Quiver adapter, live-verified against the real API). A row with
    # this real-world variant must survive the funnel and come out
    # normalized to the canonical "Sale" -- not be silently dropped or
    # left as the unnormalized variant string (which models.model2 would
    # then code as a purchase, since it only recognizes literal "Sale").
    report = date(2020, 6, 15)
    _seed_trade("AAPL", "A001", report, report, 1001.0, transaction="Sale (Partial)")
    prices = _trading_dates(date(2019, 1, 1), 300) + _trading_dates(date(2020, 6, 16), 200)
    _seed_prices("AAPL", prices)
    result = funnel.build_sample(period_start=date(2020, 1, 1), period_end=date(2020, 12, 31))
    step = next(s for s in result.steps if s.name == "directional_transaction_only")
    assert step.count_before == 1
    assert step.count_after == 1
    assert result.sample["transaction"].to_list() == ["Sale"]


def test_directional_transaction_only_excludes_exchanges_and_transfers():
    # PRE_ANALYSIS_PLAN.md Section 4: "Exchanges and transfers (not
    # directional decisions)" are excluded. Whitelist, not blacklist --
    # this must exclude ANY value that isn't Purchase/Sale(-variant),
    # without needing to know Quiver's exact string for an exchange or
    # transfer in advance.
    report = date(2020, 6, 15)
    _seed_trade("AAPL", "A001", report, report, 1001.0, transaction="Purchase")
    _seed_trade("AAPL", "A002", report, report, 1001.0, transaction="Exchange")
    prices = _trading_dates(date(2019, 1, 1), 300) + _trading_dates(date(2020, 6, 16), 200)
    _seed_prices("AAPL", prices)
    result = funnel.build_sample(period_start=date(2020, 1, 1), period_end=date(2020, 12, 31))
    step = next(s for s in result.steps if s.name == "directional_transaction_only")
    assert step.count_before == 2
    assert step.count_after == 1
    assert result.sample["bioguide_id"].to_list() == ["A001"]


def test_period_filter_excludes_trades_outside_the_sample_window():
    _seed_trade("AAPL", "A001", date(2013, 6, 15), date(2013, 6, 15), 1001.0)  # before period_start
    _seed_prices("AAPL", _trading_dates(date(2012, 1, 1), 300))
    result = funnel.build_sample(period_start=date(2014, 1, 1), period_end=date(2020, 12, 31))
    assert result.sample.is_empty()
