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

### 3. Decide the ticker universe — do this before ingesting

**This is a sample-selection decision that must be recorded in the paper,
not a technical detail.** `ingest_congress_trades(ticker)` fetches one
ticker at a time, so the set of tickers you ingest *is* the study
universe, and any name Congress traded outside it is silently absent from
the sample rather than logged as an exclusion.

Two defensible options:

- **(a) Bulk discovery.** Quiver exposes a no-ticker-filter bulk endpoint
  (`https://api.quiverquant.com/beta/bulk/congresstrading`) that yields the
  complete traded universe. It is referenced in Quiver's own SDK but was
  never called during planning, and is not wired into
  `sources/quiver.py` — verify its response shape and pagination behavior
  with a single manual call before relying on it.
- **(b) Seed from a broad index.** Use S&P 500 + Russell 3000 constituents
  and accept that names traded outside that universe are missed.

Whichever you choose, state it explicitly in the paper's
sample-construction section, per Section 4 of the pre-analysis plan.

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
| `paper.md` | Tables T1–T7 and links to every generated figure |
| `f1_sample_funnel.png` … `f8_calendar_time_alpha.png` | Figures F1–F6, F8 |
| `nan_audit.csv` | Per-column null accounting for every CAR/BHAR variant |
| `delisting_audit.csv` | Tickers whose price history ends well before the sample does |
| `ticker_reuse_audit.csv` | CIKs mapping to more than one ticker symbol |
| `hand_check_worksheet.csv` | The 20-transaction worksheet for the Section 11 manual check |

Known gaps in this output, all reported rather than papered over:

- **F7 (year-by-year effect) is not generated.** Model 2 absorbs a year
  fixed effect, so on a single-year subset that effect has one level and
  the estimator refuses to fit. Producing F7 needs a per-year Model 2
  variant without the year fixed effect, which does not exist yet.
- **The Benjamini-Hochberg threshold is not computed.** `paper.md` now
  renders the un-computed case as "not yet computed" and does not claim
  anything survived or failed to survive correction. Compute the Section 8
  18-variant grid before publishing anything from T4/T5/T7.
- **T4 carries Model 1's member- and month-clustered SEs** (`tables.t4_mean_car`
  is routed through `models.model1.unconditional_means_table`), satisfying
  Section 7's "report both."

The permutation test behind F6 recomputes the primary CAR 1,000 times per
transaction and dominates the runtime; `PERMUTATION_MAX_TXNS` at the top of
the script caps how many transactions it resamples.

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
