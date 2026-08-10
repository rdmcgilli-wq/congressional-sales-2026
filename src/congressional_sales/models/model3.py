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
