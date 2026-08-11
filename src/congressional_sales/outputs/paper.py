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
- **Model 3's calendar-time alpha uses plain (non-Newey-West) standard
  errors.** With a 3-month holding period, consecutive monthly portfolio
  returns share overlapping composition, which can induce positive
  residual autocorrelation and understate the reported SE -- i.e. overstate
  Model 3's significance. The point estimate itself is unaffected; only
  inference on this secondary model is. Kept as the pre-registered
  estimator rather than switched post-hoc.
- **BHAR is computed for every CAR variant but not separately reported.**
  All 18 `bhar_*` columns are attached to the sample alongside their CAR
  counterparts; no table or figure currently presents them.
- **T8 (18-month holdout results) is not included in this document.**
  `scripts/run_holdout.py` is a separate, run-once, run-last script (Section
  9 item 10) that prints its result rather than writing it to `outputs/`.
- **All trade-level data is sourced from Quiver Quantitative**, a
  third-party aggregator of House/Senate financial disclosures, not pulled
  directly from the House Clerk or Senate eFD systems (Global Constraints:
  bulk-scraping the primary portals is out of scope for this study; see
  Section 11's light-touch hand-check). Aggregator coverage gaps, if any,
  are not independently verified beyond the ~20-transaction manual
  cross-check.
- **Every join and match in this study keys on the ticker symbol**, not a
  permanent security identifier (e.g. CIK or CUSIP). `ticker_reuse_audit`
  detects CIKs mapped to more than one symbol but does not remap or
  correct for it.
- **F6's random-control permutation test resamples a capped subset of
  transactions** (`PERMUTATION_MAX_TXNS` in `scripts/run_full_pipeline.py`),
  not the full screened-sale set Section 8 specifies ("the same tickers"),
  for tractability -- each of the 1,000 iterations recomputes a four-factor
  CAR per resampled transaction.

No causal claim about information sources is made -- this study observes
timing, not mechanism. No claim about any individual member is made. No
claim about the legality of any transaction is made. No investment recommendation is made.
"""


def build_paper_markdown(
    tables: dict[str, pl.DataFrame], figure_paths: dict[str, str], bh_threshold: float | None,
    bh_computed: bool = True,
) -> str:
    """bh_computed distinguishes two different reasons bh_threshold can be
    None: the Section 8 18-variant correction was genuinely run and zero
    results survived it (bh_computed=True, the default -- "no result
    survived correction" is then a real finding), versus the correction
    was never computed at all (bh_computed=False -- found during the
    whole-branch review: run_full_pipeline.py always calls this with
    bh_threshold=None because it doesn't yet build the correction grid,
    and the old unconditional "no result survived correction" wording
    rendered a false, substantive claim into the generated paper about a
    test that was never run)."""
    parts = ["# Do Congressional Sales Carry More Information Than Purchases?\n"]

    if bh_threshold is not None:
        parts.append(f"Benjamini-Hochberg corrected significance threshold across the 18 pre-specified test variants: **{bh_threshold:.4g}**.\n")
    elif bh_computed:
        parts.append("Benjamini-Hochberg correction: no result survived correction across the 18 pre-specified test variants.\n")
    else:
        parts.append(
            "Benjamini-Hochberg correction: **not yet computed** across the 18 "
            "pre-specified test variants. Treat every table above as uncorrected "
            "for multiple comparisons until this grid is computed -- do not read "
            "this as a finding of non-significance.\n"
        )

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
