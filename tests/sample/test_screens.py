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


def test_screen3_result_is_invariant_to_input_row_order_for_same_day_transactions():
    # Whole-branch review finding: this function's internal sort
    # (["bioguide_id", "transaction_date"]) is a PARTIAL key when a member
    # has same-day transactions -- polars' default maintain_order=False
    # does not guarantee tie-stable ordering, so cum_sum().over(...) could
    # see same-day rows in a different relative order depending on how
    # they arrived, silently changing which row "sees" the prior exposure
    # from the others and therefore changing excluded_liquidation's
    # actual value (not just row order). Regression/contract guard: feed
    # the identical three same-day rows in forward and reversed order and
    # assert byte-identical flags either way. This is a total-order
    # contract test, not a mutation-proof against the old partial-key
    # code -- polars' observed sort behavior happens to be stable for
    # inputs this small on this build (confirmed empirically before
    # writing this test), so this guards against a future regression
    # (e.g. a refactor dropping the extended sort key, a different
    # polars version, or a larger real dataset) rather than reproducing
    # today's exact failure.
    d = date(2020, 6, 1)
    forward = [
        _row("AAPL", "A1", "Purchase", d, amount=10000.0),
        _row("MSFT", "A1", "Sale", d, amount=8000.0),
        _row("GOOG", "A1", "Sale", d, amount=100.0),
    ]
    terms = _terms("A1", "rep", date(2015, 1, 1), date(2025, 1, 1))
    out_forward = screens.screen3_liquidation(_df(forward), terms).sort("ticker")
    out_reversed = screens.screen3_liquidation(_df(list(reversed(forward))), terms).sort("ticker")
    assert out_forward["excluded_liquidation"].to_list() == out_reversed["excluded_liquidation"].to_list()
