"""Assembles the final paper. T1-T8 and F1-F8 only (Section 10) -- this
function is the single place all of them get stitched together, so it is
also the single place to verify nothing extra snuck in."""

from __future__ import annotations

import polars as pl

LIMITATIONS = """## Limitations

- **Survivorship bias.** This study's price data has no delisting-inclusive
  source; a security that was acquired, went bankrupt, or otherwise
  delisted after a disclosed transaction is absent from that transaction's
  event window rather than carrying a delisting return, so the resulting
  sample is survivorship-biased.
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
claim about the legality of any transaction is made. No investment recommendation is made.
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
