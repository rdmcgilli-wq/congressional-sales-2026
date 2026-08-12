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

Pipeline and analysis code are implemented and tested. No full-sample run
against real ingested data has been performed yet — see "Reproducing this
study" below, and the open sample-scoping decision it flags.

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

These steps go from raw primary-source data (Quiver Quantitative, Tiingo,
the Ken French data library, and the public-domain
`unitedstates/congress-legislators` records) to every table and figure in
the pre-specified output list.

### 1. Environment

```bash
uv sync
```

Python 3.12+ is required. Every dependency is pinned in `uv.lock`; do not
install into a system interpreter.

### 2. Credentials

Copy `.env.example` to `.env` and fill in:

```
QUIVER_API_TOKEN=...   # https://www.quiverquant.com/api-setup/ (Trader tier)
TIINGO_API_TOKEN=...   # https://www.tiingo.com/ (free key covers ~500 symbols/month)
CONTACT_EMAIL=...      # sent as the User-Agent on every outbound request
```

`.env` is git-ignored and must stay that way. Nothing else needs a key: the
Ken French files and the legislator/committee YAML are unauthenticated.

The warehouse lives in `data/` by default. Set `CONGRESS_SALES_HOME` to
redirect it somewhere else (an external disk, a scratch dir for a trial
run); `outputs/` is always written to the repository root regardless.

### 3. Discover the ticker universe — do this before ingesting

**Resolved by `PRE_ANALYSIS_PLAN.md` Addendum A (2026-08-11): this is no
longer an open decision.** The universe is disclosure-defined, not
index-defined. Discover it via Quiver's bulk endpoint
(`https://api.quiverquant.com/beta/bulk/congresstrading`, verified live:
single call, no pagination, full historical dataset), restricted to
disclosures filed within the sample period, then ingest each distinct
ticker symbol it returns through the normal per-ticker pipeline below —
this bulk pull is used only to discover symbols, never to classify them
(the per-ticker endpoint's own `TickerType` field still governs the
common-stock filter in Section 4). See Addendum A for the full reasoning
and the live-verified counts (114,951 disclosure records; 5,046 distinct
tickers within the sample period).

### 4. Ingest

```bash
uv run python -c "from congressional_sales.sources.french import ingest_factors; ingest_factors()"
uv run python -c "from congressional_sales.sources.legislators import ingest_legislator_terms, ingest_committee_assignments; ingest_legislator_terms(); ingest_committee_assignments()"

# Per ticker, for every ticker in the universe chosen in step 3.
# SPY is REQUIRED -- it is the market benchmark and defines the trading
# calendar every event window is measured against.
uv run python -c "
from congressional_sales.sources.prices import ingest_prices
from congressional_sales.sources.quiver import ingest_congress_trades
from congressional_sales.sources.sic import ingest_sic_codes
universe = ['SPY', 'AAPL', 'MSFT']  # <- replace with the universe from step 3
for t in universe:
    ingest_prices(t)
    ingest_congress_trades(t)
ingest_sic_codes(universe)
"
```

Ingestion is idempotent — every table upserts on its natural key, so a
re-run over an overlapping window is always safe and never duplicates rows.
Rate limits are enforced per host in `config.py`; a full universe pull takes
hours, and that is deliberate.

Price history must extend far enough back: a transaction needs ~250
trading sessions *before* it (the four-factor estimation window) and 180
sessions *after* it (the longest event horizon), or it drops out of the
funnel and out of Model 2.

### 5. Run the pipeline

```bash
uv run python scripts/run_full_pipeline.py
```

This builds the sample, applies Screens 1–4, attaches every CAR/BHAR
variant, fits Models 2 and 3, runs the robustness suite, and writes to
`outputs/`:

| File | Contents |
| --- | --- |
| `paper.md` | Tables T1–T7 and links to every generated figure; `run_holdout.py` appends Table T8 later, once, if run afterward |
| `f1_sample_funnel.png` … `f8_calendar_time_alpha.png` | Figures F1–F5, F7, F8 (F6 only if at least one permutation iteration produced a usable value; F7 only if at least 2 calendar years fit) |
| `nan_audit.csv` | Per-column null accounting for every CAR/BHAR variant |
| `delisting_audit.csv` | Tickers whose price history ends well before the sample does |
| `ticker_reuse_audit.csv` | CIKs mapping to more than one ticker symbol |
| `hand_check_worksheet.csv` | The 20-transaction worksheet for the Section 11 manual check |
| `bh_correction_grid.csv` | All 18 Section 8 (horizon, method, sample) cells: beta_sale, se, p-value, n -- the raw grid the reported BH threshold is computed from |
| `t8_holdout.csv` | Written by `run_holdout.py`, not this script -- Section 9 item 10's holdout result |

Known gaps in this output, all reported rather than papered over:

- **F7 (year-by-year effect)** is generated via
  `robustness.year_by_year_effects`, which refits Model 2 per calendar year
  with `absorb_year=False` (YearFE is degenerate -- constant, one level --
  on any single-year subset, and controls for nothing there anyway).
  A year too thin, or degenerate even without YearFE, is skipped rather than
  plotted as a fabricated point; if fewer than 2 years fit, F7 itself is
  skipped and the script says so.
- **The Benjamini-Hochberg threshold is computed**, via
  `models.multiple_comparisons.run_eighteen_variant_grid` fitting all 18
  pre-specified cells and feeding their p-values to `bh_corrected_threshold`.
  Any cell too thin or FE-degenerate to fit reports a None row in
  `bh_correction_grid.csv` rather than crashing the whole grid, and the
  script prints how many of the 18 cells actually produced a p-value.
- **T4 carries Model 1's member- and month-clustered SEs** (`tables.t4_mean_car`
  is routed through `models.model1.unconditional_means_table`), satisfying
  Section 7's "report both."
- **F6's permutation test is capped** at `PERMUTATION_MAX_TXNS` transactions
  (50 by default), a permanent, documented deviation from Section 8's
  literal "the same tickers" -- not a TODO to lift later, kept because an
  uncapped run recomputes the primary CAR 1,000 times per transaction and
  dominates the pipeline's runtime on a full-scale sample. Set it to `None`
  in `scripts/run_full_pipeline.py` for a specific run if compute budget
  allows the full screened-sale set instead.

### 6. Verify (Section 11)

Do the manual hand-check on `outputs/hand_check_worksheet.csv` — pull those
20 transactions from the primary portals, compute CAR by hand, and confirm
the pipeline matches. Then confirm reproducibility:

```bash
# Day 1
uv run python scripts/run_full_pipeline.py && cp -R outputs outputs-run1

# Day 2, from the same warehouse
uv run python scripts/run_full_pipeline.py && cp -R outputs outputs-run2

diff -r outputs-run1 outputs-run2
```

The two directories must be byte-for-byte identical — including the PNGs,
which carry only a matplotlib-version tag and no creation timestamp
(verified). Every stochastic step in the pipeline is explicitly seeded for
exactly this reason, so any difference is a real non-determinism bug, not
noise. Two caveats that are legitimate differences rather than bugs:
re-ingesting between the runs changes the data, and changing the
environment changes the version string baked into every PNG — run both
against the same warehouse snapshot and the same `uv.lock`.

### 7. Run the holdout — last, and once

```bash
uv run python scripts/run_holdout.py
```

Section 9 item 10: this re-runs the primary specification on the final 18
months, which nothing above has touched. Run it once, after everything else
is final, and report what it says. If it reveals a methodology problem, log
that as a limitation — do not patch the pipeline and re-run it.

Writes `outputs/t8_holdout.csv` (Table T8) and appends a "## Table T8"
section to `outputs/paper.md` if that file already exists from step 5.
Running this script a second time appends a second T8 section rather than
replacing the first — consistent with "run once," not a guard this script
adds on top of it.

The sample-period constants (`SAMPLE_PERIOD_START` and `HOLDOUT_START`, which
appear in both scripts, plus `HOLDOUT_END`, which only `run_holdout.py`
needs) must be kept in sync across the two files. They currently encode a
2026 run: study period 2014-01-01 through 2025-12-31 (the most recent
complete year), holdout 2024-07-01 through 2025-12-31. Re-confirm them
whenever the study period rolls forward.

## License

Code: MIT (see `LICENSE`). Output data and tables are derived from public
government disclosures and public market data; no proprietary data is
redistributed in this repository.
