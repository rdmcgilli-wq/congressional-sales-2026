# Do Congressional Sales Carry More Information Than Purchases?

A pre-registered empirical study of whether disclosed congressional stock
sales predict negative abnormal returns, and whether that effect is larger
than the (more heavily studied) purchase-side effect.

**Pre-analysis plan:** [`PRE_ANALYSIS_PLAN.md`](PRE_ANALYSIS_PLAN.md),
version 1.0, committed 2026-08-08T22:17:31Z — before any analysis code in
this repository existed. The plan fixes the hypotheses, sample construction
rules, screening funnel, statistical tests, and the complete output list
(8 tables, 8 figures) in advance. Any specification not in that list that
later appears in this repo's output is explicitly post-hoc and will be
labeled as such, per Section 8 of the plan.

## Status

Pre-registration only. Data pipeline and analysis code have not been
written yet.

## Known deviation from the plan (recorded pre-analysis)

Section 3/11 of the plan call for delisting-inclusive price data (a company
that was acquired or went bankrupt after a disclosed sale needs a real
delisting return, not a silent drop from the sample). This project
currently has no source for that. The analysis will proceed on
survivorship-biased daily price data, and this will be reported explicitly
in the paper's limitations section rather than treated as resolved — see
the inline note in `PRE_ANALYSIS_PLAN.md` Section 3 and the corresponding
Section 11 checklist item.

## Reproducing this study

Once the pipeline is built, this section will document exact steps to go
from raw primary-source data (House Clerk, Senate eFD, Quiver Quantitative,
Ken French data library, congressional committee records) to every table
and figure in the pre-specified output list, including the two independent
end-to-end reproduction runs required by Section 11.

## License

Code: MIT (see `LICENSE`). Output data and tables are derived from public
government disclosures and public market data; no proprietary data is
redistributed in this repository.
