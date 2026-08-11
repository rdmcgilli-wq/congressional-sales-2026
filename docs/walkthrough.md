# Project Walkthrough

**Purpose.** A read-through of the entire codebase against `PRE_ANALYSIS_PLAN.md`
(v1.0 + Addendum A), written so the author can defend this study line by
line — to a professor, a referee, or themselves six months from now. Nothing
here was run to produce this document; it is a static read of the code, the
tests, and the plan. Where this document says a number came from a real run,
that run was the narrow four-ticker mechanical sanity check (AAPL/MSFT/NVDA/SPY)
described elsewhere in this project's history, never a full-universe run.

Seven sections, in the order requested: repo map, decision log, one
transaction's data flow, the four screens in plain language, known
weaknesses ranked by severity, test coverage gaps, and Section 11
verification status.

---

## 1. Repo map

### Top level

| Path | Contents |
|---|---|
| `PRE_ANALYSIS_PLAN.md` | The pre-registration: v1.0 (2026-08-08) plus Addendum A (2026-08-11, ticker-universe rule). |
| `README.md` | Reproduction instructions. **Stale in one place** — see Weakness 17. |
| `LICENSE` | MIT. |
| `pyproject.toml` / `uv.lock` | Dependency pins (Python 3.12+; polars, duckdb, httpx, statsmodels, linearmodels, matplotlib, pyyaml, scipy, pandas). |
| `.env.example` | Credential template. The real `.env` is git-ignored; nothing in this codebase or this audit reads or writes it. |
| `paper/draft.md` | The paper draft: literature review, institutional background, data, methods drafted; results/discussion/conclusion held pending. |
| `docs/superpowers/plans/2026-08-08-congressional-sales-study.md` | The original 29-task implementation plan this codebase was built from. Process artifact, not itself mapped to a PAP section. |
| `scripts/run_full_pipeline.py` | Main orchestration: ingest → sample → screen → CAR → models → robustness → outputs. Excludes the 18-month holdout window entirely. |
| `scripts/run_holdout.py` | Section 9 item 10. Run last, once, on the holdout window only. |

### `src/congressional_sales/` — infrastructure (no PAP section; expected)

`__init__.py` (empty), `config.py` (paths, credentials, per-host rate
limits), `storage.py` (idempotent parquet + DuckDB-view warehouse),
`calendar.py` (trading-session calendar and `offset_trading_day` — the t+1
discipline Section 11 calls out), `http.py` (shared rate-limited HTTP
client every source module routes through).

### `sources/` — Section 3 (data)

- `quiver.py` — primary trade-level data via Quiver's per-ticker endpoint. A recorded deviation from Section 3's literal source table: primary government portals are not bulk-pulled (see Global Constraints / README); Quiver is primary, not a cross-check.
- `prices.py` — daily EOD prices via Tiingo. Carries the documented survivorship-bias deviation (Section 3/11).
- `french.py` — Fama-French three factors + momentum, Ken French's data library.
- `legislators.py` — member terms and committee assignments, `unitedstates/congress-legislators`. Feeds Section 7's seniority control and Section 5/7's H4 committee mapping.
- `sic.py` — SIC code lookup via SEC EDGAR, feeding FF12 industry classification (Section 6 size/industry matching, Section 7 IndustryFE).
- `primary_portals.py` — URL builders supporting the Section 11 hand-check only, never a bulk integration. **Its own docstring flags both URL formats as unverified against a live session** — see Weakness 18.

### `sample/` — Section 4/5 (sample construction and screening)

- `funnel.py` — the inclusion/exclusion funnel; its step log is Table T1 directly.
- `screens.py` — Screens 1–3 (rebalancing, tax management, liquidation).
- `classify.py` — Screen 4 (routine vs. opportunistic) and `committee_match` (H4).
- `industry.py` — FF12 12-industry classification from a SIC code, parsed live from Ken French's own published range file rather than hand-transcribed.
- `descriptive.py` — Tables T2 (descriptive stats) and T3 (filing-lag distribution).

### `events/` — Section 6/8 (outcome variables, permutation test)

- `car.py` — the CAR/BHAR engine: market-adjusted, four-factor, and size/industry-matched, for both CAR and BHAR, plus the event-time series F3–F5 are built from.
- `attach.py` — attaches all 18 CAR/BHAR columns plus `industry` and `prior_12mo_return` to a sample frame.
- `permutation.py` — the Section 8 random-control test.

### `models/` — Section 7/8 (empirical specification, multiple comparisons)

- `model1.py` — unconditional means with member- and month-clustered SEs.
- `model2.py` — the pooled fixed-effects regression; β1 (`sale` at 90-day, four-factor, screened) is the study's single pre-registered primary test.
- `model3.py` — the calendar-time short-portfolio regression.
- `multiple_comparisons.py` — Benjamini-Hochberg correction and the 18-variant grid. **Fully implemented and tested, never called by `run_full_pipeline.py`** — see Weakness 2. This is the single most important finding in this audit.

### `outputs/` — Section 10 (tables, figures, paper assembly)

- `tables.py` — T1–T8.
- `figures.py` — F1–F8. **F7 is never actually produced by the orchestration script** — see Weakness 4.
- `paper.py` — assembles `paper.md`, including the pre-written `LIMITATIONS` block (Section 13 compliance) and the honest "not yet computed" BH-threshold wording.

### `verification/` — Section 11

- `audits.py` — NaN audit, delisting-gap audit (quantifies the survivorship-bias deviation, does not fix it), ticker-reuse audit (detects, does not remap).
- `hand_check.py` — builds the 20-transaction worksheet template. **Does not perform the hand-check** — see verification status, item 1.

### `tests/`

Mirrors `src/` one-to-one, 25 files. 148 `def test_` lines; 152 tests
actually collected once `pytest.mark.parametrize` is accounted for (two
parametrized functions in `tests/models/test_model2.py` add 4 extra cases).

### Anything not mapping to a PAP section?

No. Every module outside the four pure-infrastructure files (`config.py`,
`storage.py`, `calendar.py`, `http.py`) maps cleanly to a PAP section.
`primary_portals.py` nominally maps to Section 11 but is a genuinely weak
link — see Weakness 18 — not an unmapped module.

---

## 2. Decision log

Every place the code had to pick a specific value, tie-break rule, or
interpretation the PAP itself left open. These are the choices a referee
or advisor would ask about first, because none of them is wrong on its
face, but none of them was fully forced by the plan either.

**D1 — Common-stock filter is `ticker_type == "ST"`.** PAP says "common
stock transactions only." Implementation uses Quiver's own per-ticker
`TickerType` tag, `"ST"`. Chosen because it's the vendor's own canonical
stock label on the endpoint this project actually ingests from (Addendum A
explicitly keeps the broader, less consistent bulk-endpoint vocabulary out
of this decision — the bulk endpoint is used only to discover symbols, not
to classify them).

**D2 — "Above $1,000" is implemented as strictly `amount_low > 1000.0`.**
A transaction disclosed at exactly $1,000 is excluded. This is a literal
reading of "above," not an inclusive one; defensible, but worth being able
to state plainly if asked why $1,000-even isn't in the sample.

**D3 — Directional filter is a whitelist, not a blacklist.** Only
`{"Purchase", "Sale"}` survive (after normalizing any `"Sale*"`-prefixed
value to `"Sale"`). Rejected alternative: blacklisting known non-directional
strings like `"Exchange"`/`"Transfer"`, which would require knowing every
such string Quiver might use in advance and would silently admit an
unanticipated future value instead of excluding it with a logged count.

**D4 — Dedup key excludes `report_date`.** The funnel's own dedup step
(and Quiver's upsert key) is `(ticker, bioguide_id, transaction_date,
transaction, amount_range)`. Two genuinely distinct filings of the same
transaction submitted on different dates collapse to one row (`keep="first"`).
Inherited from Quiver's own natural key, documented as an accepted
limitation of the data as published.

**D5 — Screen 1's "unrelated sectors" is implemented as ticker-distinctness,
not sector-distinctness.** `screen1_rebalancing` is a pure function that
deliberately does not take the SIC join as a dependency, so "3+ simultaneous
sales across unrelated sectors" becomes "3+ simultaneous sales across
distinct tickers" — weaker than the PAP's literal wording. The module's own
comment flags this as a documented simplification a stricter check could be
layered onto later.

**D6 — Screen 2's price comparison uses the nearest available close on or
before each date, not the literal transaction-date price.** Needed because
transaction dates aren't guaranteed to be trading days and the disclosed
price a member actually received is never itself in the data.

**D7 — Screen 3's "60% of disclosed portfolio" is a running signed-dollar
proxy, not true holdings.** Built purely from `amount_low` on every prior
disclosed transaction (purchases add, sales subtract). A member's real
portfolio existed before the sample period starts, and this proxy has zero
visibility into that base — it can only ever measure what's been disclosed
inside the window. Structurally, the sub-condition **cannot fire at all**
for any sale where cumulative prior disclosed exposure is zero or negative
at that point, no matter how large the sale truly is relative to the
member's real (unobserved) holdings.

**D8 — Screen 3's retirement window defaults to 90 days, and "retirement"
is inferred from the absence of a subsequent term, not an announcement
date.** Neither number nor proxy is specified in the PAP. The proxy cannot
distinguish voluntary retirement from electoral defeat, death in office, or
any other reason a member's last known term simply ends.

**D9 — Screen 4's routine-trader classification runs on the unscreened
sample, before Screens 1–3.** A deliberate ordering choice (see
`run_full_pipeline.py`'s own comment): checking a member's routine pattern
against the already-screened subset would see an artificially incomplete
trading history, since Screens 1–3 remove some of that member's own other
transactions.

**D10 — The committee → FF12-industry keyword map is a hand-built,
13-row research judgment, not a fact.** `classify.py`'s own docstring says
so directly. This is arguably the single most subjective piece of logic in
the codebase, and it feeds H4 directly.

**D11 — CAR/BHAR anchor on `transaction_date` by default; Model 3 anchors
on `report_date`.** These are two different, both-correct-for-their-purpose
uses of the two dates — `report_date` gates what's *knowable* for sample
inclusion (point-in-time correctness), `transaction_date` anchors the
outcome window to test *foreknowledge* (H1), and Model 3 can only ever
short a stock after its sale is disclosed, so it has to anchor on
`report_date`. Nowhere in the PAP is this split stated as a single coherent
rule — it's the correct design, but it needs a one-paragraph explanation
ready, because on first read it looks inconsistent.

**D12 — Model 1's month-clustering clusters on `report_date`'s month, not
`transaction_date`'s.** Consistent with D11's report-date convention, but
not literally what Section 7 says ("clustered ... at the calendar-month
level" doesn't specify which date).

**D13 — Two of Section 7's named controls are substituted or dropped.**
Log market cap → log trailing dollar-volume (no shares-outstanding source
exists in this project); book-to-market → omitted entirely (no data
source). Both documented extensively in-code and in `outputs/paper.py`'s
`LIMITATIONS` block.

**D14 — Chamber and party are never estimated as regressors, even though
Section 7 lists them under "Controls."** This one is mathematically forced,
not a free choice: both are member-invariant, so once `MemberFE` is
absorbed (itself pre-registered), including chamber/party dummies makes the
model unidentified and `AbsorbingLS` raises `AbsorbingEffectError` on any
realistic sample. Still worth stating plainly rather than letting a reader
notice two PAP-named controls are simply absent from every T5 row.

**D15 — Model 3's "90 days held" is 3 calendar months, starting the month
*after* `report_date`.** Neither the calendar-month approximation nor the
"starts the following month" boundary is specified in the PAP; both are
implementer choices, described in-code as "the standard convention in this
literature."

**D16 — `AbsorbingLS` is fit with `debiased=True`.** Not a library default
(`False`); set explicitly because the undebiased estimator understates the
primary test's own clustered SE by roughly 3% at realistic cluster counts.

**D17 — Winsorizing uses linear interpolation, not polars' default
("nearest").** Nearest-interpolation can return the sample's own extreme
value as its own clip bound on small/boundary-heavy samples, silently
no-op'ing the winsorization exactly where it matters most.

**D18 — F6's permutation test is capped at 50 transactions
(`PERMUTATION_MAX_TXNS`), not the full screened-sale set.** A documented
compute-tractability deviation from Section 8's literal "the same tickers"
— directly weakens the check the PAP itself calls "the single most
persuasive robustness check available."

**D19 — F3/F4/F5's mean event-time paths average a capped, seeded
100-transaction subsample (`EVENT_SERIES_MAX_TXNS`), not the full sample.**
Visualization-only; doesn't touch any table or statistic, but is still a
real deviation from "plot the sample."

**D20 — `is_routine`/`committee_match` are computed once, on the
unscreened sample, and carried into both the unscreened and screened
views.** Restated from D9 because of how consequential it is: Section 4's
"the gap between [unscreened and screened] is itself informative" requires
both views to share the same classification framework, not two different
ones.

**D21 — Canonical row-order sorting lives in the orchestration scripts,
not in `funnel.py` or `screens.py` themselves.** `sample.funnel.build_sample`
and `sample.screens.screen3_liquidation` are not independently
order-safe — a caller that doesn't also apply `CANONICAL_ORDER` before
calling them can get a different, non-reproducible answer (confirmed
empirically during this build: reversing row order changed
`screen3_liquidation`'s actual exclusion flags, not just row order). This
was patched at the call site "since that module is out of this task's
scope" rather than in the module itself — a latent trap for any future
caller of those two functions directly.

**D22 — `build_model2_frame` silently drops rows with a null
`log_size` or `prior_12mo_return`.** Recent IPOs and thinly covered tickers
are excluded from Model 2 specifically (though they can still appear in
T1/T4) — not imputed, and not flagged per-row anywhere downstream of that
function.

---

## 3. Data flow: one transaction, raw pull to its row in T4

Tracing a single disclosed sale end to end, in the order it's actually
touched.

**1. Raw ingestion.** `sources.quiver.ingest_congress_trades(ticker)` calls
Quiver's per-ticker historical endpoint and gets back Quiver's raw field
names (`Ticker`, `Representative`, `BioGuideID`, `Transaction`,
`TransactionDate`, `ReportDate`, `Range`, `Amount`, `TickerType`, ...).
`parse_congress_trades` renames these to the internal schema, casts both
dates to `pl.Date`, strips commas from `Amount` and casts it to
`amount_low: Float64`. Written to the `congress_trades` warehouse table,
upserted on `(ticker, bioguide_id, transaction_date, transaction,
amount_range)`.

**2. Prices, separately.** `sources.prices.ingest_prices(ticker, start=...)`
pulls Tiingo daily EOD and writes `equity_eod` (ticker, date, OHLCV,
`close_adj`), upserted on `(ticker, date)`. This has to happen for the
transaction's own ticker *and* for SPY, the market benchmark and calendar
anchor every CAR calculation in the codebase depends on.

**3. Supporting tables, ingested once, not per-transaction.**
`ff_factors` (Ken French daily factors + momentum), `legislator_terms` and
`committee_assignments` (`unitedstates/congress-legislators`), `sic_codes`
(EDGAR CIK + SIC per ticker).

**4. The sample funnel** (`sample.funnel.build_sample`, reading straight
from `congress_trades` and `equity_eod`). The row survives, in order:
`sample_period` (`report_date` in range) → `common_stock_only`
(`ticker_type == "ST"`) → `directional_transaction_only` (normalize any
`"Sale*"` to `"Sale"`, keep only Purchase/Sale) → `above_statutory_threshold`
(`amount_low > 1000.0`) → `dedupe_filings` (unique on the natural key,
keep first) → `min_prior_trading_history` (≥60 `equity_eod` rows for this
ticker strictly before `report_date`) → `full_forward_window` (≥180 rows
strictly after). Every step's before/after count *is* Table T1.

**5. Orchestration sorts into `CANONICAL_ORDER`, then classifies.**
`classify.is_routine_trader` adds `is_routine` (checked against this
member's own rows present in the unscreened frame). `classify.committee_match`
joins `sic_codes` (ticker → SIC → FF12 sector) and `committee_assignments`
(bioguide_id → committee name → keyword-mapped sectors) and adds
`committee_match`. This is the `unscreened` frame.

**6. Screening** (Screens 1–3 only ever flag sales; a purchase passes
through with all three flags `False` by construction). If this row is a
sale: `screen1_rebalancing` flags it if the same member bought the same
ticker within 90 days, or sold 3+ distinct tickers that same day.
`screen2_tax_management` flags it if it's a November/December sale below
the member's most recent prior purchase price for that ticker.
`screen3_liquidation` flags it if it exceeds 60% of the member's cumulative
signed disclosed exposure, or falls within 90 days of their last known term
end. Any flag `True` drops the row from `screened`, which is then re-sorted
into canonical order.

**7. CAR/BHAR attachment** (`events.attach.attach_car_bhar`, run separately
on `unscreened` and `screened`). From `transaction_date` (the default event
anchor), computes 3 horizons × 3 methods × 2 metrics = 18 columns per row,
each from `events.car`'s pure functions against this ticker's own
`equity_eod` rows, SPY's rows, `ff_factors` (four-factor estimation over
the transaction's own [-250,-30]-session window), and same-sector/
same-size-decile peers from `sic_codes`. Plus `industry` (this ticker's own
FF12 sector) and `prior_12mo_return` (this ticker's own trailing
~252-session return as of the transaction).

**8. Where this row lands in the outputs.** T1: counted at every funnel
step. T2/T3: bucketed into `descriptive.build_t2`/`build_t3`'s
year/chamber/party/sector/size-band counts and the filing-lag distribution.
**T4** (screened frame only, if this row survived screening): its own
`car_{method}_{horizon}` value is one input to
`model1.unconditional_means_table`'s per-(transaction type, horizon,
method) mean and clustered SE — the row contributes to a T4 cell, it is
not itself a T4 row (T4 has one row per triple, aggregating across every
row of that type). T5: if it survives `build_model2_frame`'s complete-case
filter, it becomes one observation in the pooled regression, contributing
to β1/β3/β5 via its own `sale`, `opportunistic`, `committee_match`,
`log_size`, `prior_12mo_return`, `size_band`, `seniority_terms`, and its
`bioguide_id`/`year`/`industry` fixed-effect memberships. T6: if it's a
screened sale, its `(ticker, report_date)` pair enters the calendar-time
portfolio, contributing to three consecutive months' short-portfolio
average return starting the month after its `report_date`.

The same disclosure can therefore appear in T1 always, T2/T3 if screened,
T4 if screened and CAR-attached with a non-null value for that specific
method/horizon, T5 if it additionally survives complete-case filtering,
and T6 only if it's specifically a screened sale.

---

## 4. Screen logic, plain language

**Screen 1 — Rebalancing.** A sale is excluded if either (a) the same
member bought the *same ticker* within 90 days before or after that sale
(both ends measured on `transaction_date`), or (b) on the sale's own date,
the same member sold 3 or more *distinct tickers*. **Ambiguity resolved:**
the PAP's condition (b) says "unrelated sectors"; the implementation checks
ticker-distinctness only, not sector-distinctness — weaker than the literal
text, because this screen is a pure function that deliberately doesn't take
the SIC join as a dependency (D5 above).

**Screen 2 — Tax management.** A November or December sale is excluded if
the nearest available closing price on or before the sale date is lower
than the nearest available closing price on or before the member's most
recent *prior* purchase of that same ticker. **Ambiguity resolved:** the
PAP doesn't say which purchase counts if the member bought the same ticker
more than once before — the implementation uses only the single most
recent one, not an average cost basis across all prior purchases; and
"the position shows a loss" is evaluated from the nearest tradable price on
or before each date, not a literal transaction-date price the data doesn't
actually carry.

**Screen 3 — Liquidation events.** A transaction is excluded if either
(a) it's a sale whose disclosed amount exceeds 60% of the member's
cumulative net dollar exposure built purely from every disclosed
transaction up to and including that one — purchases add, sales subtract,
using the low end of each disclosed range — and only if that running total
was positive going in; or (b) it falls within 90 days of the member's most
recently known term-end date, where no subsequent term exists in the
legislator-terms data. **Ambiguity resolved, substantially:** the PAP names
four distinct trigger events (announced retirement, blind trust
establishment, executive-branch confirmation, >60%-of-portfolio sold); only
the last is implemented as specified, and "retirement" itself is a proxy
(absence of a next term) rather than an observed announcement — it cannot
tell a voluntary retirement from an electoral defeat or a death in office.
Blind trust and executive-branch confirmation are not implemented at all;
no structured data source for either exists in this project.

**Screen 4 — Routine traders.** A member's transaction is "routine" if
that same member has at least one other transaction in the identical
calendar month in each of the three immediately preceding years, checked
against whatever set of transactions is in the frame the function is
handed. **Ambiguity resolved:** the PAP doesn't say against what set that
history should be checked; the implementation deliberately runs this on
the *unscreened* sample, before Screens 1–3 can remove any of that
member's other transactions and artificially truncate their visible
history (D9/D20 above) — a real, tested interpretive choice, not an
oversight.

---

## 5. Known weaknesses, ranked by severity

### Severe — would stop a referee cold

1. **Survivorship bias in price data.** Already the subject of active
   outreach outside this codebase; the single most damaging gap because it
   deletes exactly the strongest H1 evidence (informed sales ahead of
   delistings/bankruptcies/distressed acquisitions) twice — once from the
   universe (mitigated by Addendum A) and once from the price feed itself
   (not yet mitigated).

2. **The Benjamini-Hochberg correction is implemented and tested, but never
   invoked by `run_full_pipeline.py`.** `models/multiple_comparisons.py`
   has 6 passing tests, its math independently checked against
   `statsmodels.stats.multitest`. The orchestration script explicitly
   passes `bh_threshold=None, bh_computed=False` — it does not build the
   18-cell p-value grid at all. Per the PAP's own Section 12 rule ("A
   result is reported as supportive only if it survives Benjamini–Hochberg
   correction..."), **no result from a run of this pipeline today could be
   certified as supportive**, because the correction it must survive is
   never computed. `outputs/paper.py` renders this honestly rather than
   lying about it, which is good — but the underlying capability gap is
   real and this was the single most surprising finding of this audit.

3. **F6's permutation test — the PAP's own words, "the single most
   persuasive robustness check available" — is capped at 50 transactions**,
   not the full screened-sale set Section 8 specifies.

4. **F7 (year-by-year effect) is never generated.** A pre-specified output
   (Section 10) and a pre-specified robustness check (Section 9 item 2) is
   structurally missing: Model 2's year fixed effect collapses to one level
   on any single-year subset, and the per-year estimator variant that would
   fix this doesn't exist anywhere in the codebase yet.

5. **T8 (holdout results) is never written to a file.** `run_holdout.py`
   only prints to stdout. If that output isn't manually captured at run
   time, the PAP's own pre-registered item 10 result has no durable record.

### Moderate — defensible with a ready answer, but will draw questions

6. Screen 3's 60%-of-portfolio proxy has zero visibility into a member's
   true pre-existing holdings and structurally cannot fire for any sale
   where cumulative disclosed prior exposure isn't positive (D7).
7. Screen 1's "unrelated sectors" is ticker-distinctness only (D5).
8. H4's committee → industry mapping is an explicit, acknowledged "research
   judgment, not a fact" (D10) — probably the single most subjective piece
   of logic in the study, feeding directly into the falsification test.
9. Committee assignments are a current-only snapshot; H4's `committee_match`
   uses each member's most recent committee, not their true assignment at
   the historical transaction date.
10. All trade-level data is a single third-party aggregator (Quiver), cross-
    checked only via a hand-check protocol that is itself unverified (see
    Weakness 18 and verification item 1).
11. Size/industry-matched control peers are drawn only from this study's own
    ingested ticker set, not the broader market — thin in a narrow or
    early-stage pull, silently falling back to the full same-sector set
    below `n_deciles` peers.
12. Two Section 7 controls are substituted or dropped: log market cap →
    log dollar-volume, book-to-market → omitted (D13).
13. Every join in the codebase keys on ticker symbol, never a permanent
    identifier, for anything price/CAR-related.
14. The funnel's dedup key excludes `report_date`, so two genuinely
    distinct filings sharing the rest of the key collapse to one row.

### Minor — worth a footnote

15. The $1,000 threshold excludes a transaction disclosed at exactly $1,000
    (D2).
16. BHAR is fully computed (18 columns) but never separately tabulated
    anywhere.
17. **`README.md`'s "Decide the ticker universe" section is stale.** It
    still describes the universe as an open decision between two hand-picked
    options — Addendum A already committed to disclosure-defined bulk
    discovery. Two documents in the same repo currently give a reader
    contradictory instructions on an already-closed question.
18. `primary_portals.py`'s own docstring flags both URL builders as
    unverified against a live session — the Section 11 hand-check currently
    has no confirmed way to actually navigate to a specific filing on
    either primary portal.

---

## 6. Test coverage gaps

**What the 152 tests verify, well.** Every funnel step individually; all
three screens individually plus a same-day tie-break mutation test proving
the canonical sort is load-bearing; routine/committee classification
including the multi-keyword committee-name bug and its fix; real-format SIC
range parsing; T2/T3 descriptive stats; the trading calendar including the
weekend-skip regression and a caught-and-fixed `lru_cache` staleness bug;
storage upsert semantics; the CAR engine across all three adjustment
methods plus adversarial decile-tie-breaking; CAR attachment including
non-session event-date anchoring; the permutation test's reproducibility
and partial-failure accounting; Model 1's clustering; Model 2's FE
absorption, the chamber/party collinearity fix, and both required-column
and bad-transaction-value guards; Model 3's monthly compounding and short-
position sign; the BH math hand-verified against `statsmodels`; the
robustness suite's wiring and its filing-date-variant check; table/figure
rendering correctness down to exact plotted values; all three audits
including edge cases; every source module's parsing and ingestion logic
against mocked HTTP.

**What isn't tested — where this could be wrong and nothing would fail.**

- **No test exercises `run_full_pipeline.py` or `run_holdout.py` themselves.**
  Every module is unit-tested in isolation; nothing verifies the actual
  wiring — that `CANONICAL_ORDER` sorting happens where it needs to relative
  to screening, that `size_proxies` is built from the right frame, that
  `filing_date_variant` is threaded through correctly end to end. The only
  evidence the full pipeline works at all is the one narrow real-data
  sanity run, which is not a repeatable automated test.
- Screen 1 condition A is only tested with the purchase *before* the sale;
  no test constructs a purchase strictly *after* to confirm the `.abs()`
  symmetry actually behaves as intended.
- Screen 1 condition B is only tested with three obviously different-sector
  tickers (AAPL/XOM/JPM); no test exercises three *same-sector* tickers,
  which is exactly where the ticker-distinctness proxy's documented
  weakness (Weakness 7) would show up.
- No test constructs Screen 3's `prior_exposure <= 0` edge case (Weakness 6)
  — existing tests cover "large fraction of a positive base" and "small
  fraction," not "no positive base to measure against."
- No test covers `build_sample`'s behavior when a ticker has price history
  but SPY itself is absent from `equity_eod` — every downstream calendar
  and CAR calculation depends on SPY as anchor, and only the
  "prices entirely empty" path is exercised.
- No test wires `multiple_comparisons.eighteen_variant_grid` into an actual
  p-value pipeline, because no such pipeline exists yet (Weakness 2); its
  tests verify the pure math only.
- `run_holdout.py`'s own comments assert at length that pre-holdout history
  informs classification/screening without leaking any holdout *outcome*
  into anything — no automated test verifies this claim.
- Only `industry._parse_ranges` (pure parsing against a hand-built fixture)
  is tested; the live network fetch in `industry.load_ff12_ranges` has no
  test, so a change to Ken French's file layout or hosting URL wouldn't be
  caught before a real run hit it.
- `primary_portals.py`'s two URL functions are tested only for being
  "well-formed" (correct host prefix), not for resolving to a useful page —
  consistent with the module's own docstring admitting this was never
  confirmed.
- No test exercises `build_paper_markdown` at realistic multi-hundred-row
  scale; every existing fixture is small and hand-built.
- No test guards against BHAR columns ever leaking into a reported
  table/figure — nothing currently does this, but nothing would catch it
  if a future edit started.
- `select_worksheet_sample`'s `min(n, height)` edge (requesting 20 rows
  from a sample smaller than 20) is not exercised by any test.
- No test checks that `amount_low` is a sane lower bound across the *range*
  of real disclosed amount bands — Screen 3's exposure math depends on it
  directly, and only one hard-coded band string appears anywhere in the
  test suite.

---

## 7. Section 11 verification status

1. **Hand-check 20 transactions.** **Not done.** `verification.hand_check`
   only builds the blank worksheet template for a human to fill in; no
   actual manual check has been performed. Compounding this: the tool that
   would let a human find the real filing for each worksheet row
   (`primary_portals.py`) is itself unverified against a live site.

2. **Trading-day alignment (t+1).** **Substantially done at the unit
   level.** `calendar.py` has 7 dedicated tests including the explicit
   weekend-skip regression and a caught `lru_cache` staleness bug; every
   CAR/attachment function is built on this machinery, never raw date
   arithmetic. Not yet validated against a real full-scale sample — only
   the 4-ticker sanity check has touched real dates at all.

3. **Delisting handling.** **Cannot pass, and the PAP text says so itself.**
   `verification.audits.delisting_audit` correctly *quantifies* the gap
   (flags tickers with stale or absent price history) but does not close
   it. No delisting-inclusive price source exists in this project.

4. **Ticker remapping (match on a permanent identifier).** **Not done as
   stated.** `ticker_reuse_audit` *detects* CIKs mapped to more than one
   symbol, but nothing anywhere in the codebase re-keys any join on CIK or
   CUSIP — every price/CAR/sample join still keys on the ticker symbol
   itself. The audit is a smoke detector, not a fix.

5. **NaN audit.** **Partially done.** `nan_audit` reports null counts per
   CAR/BHAR column on the final CAR-attached frame, but this is a snapshot
   of the end state, not the PAP's requested step-by-step accounting. A row
   dropped later by `build_model2_frame`'s own complete-case filter is
   invisible to this audit entirely — it only ever sees the CAR-attached
   frame, not the post-Model-2-construction one.

6. **Reproduce end to end twice, confirm identical output.** **Not done
   against a real run; the infrastructure for it exists.** Every stochastic
   step is explicitly seeded, and `CANONICAL_ORDER` sorting was added
   specifically because row order was empirically shown to be unstable
   across runs without it. The actual two-runs-diffed protocol in
   `README.md` has never been executed against a full-scale warehouse —
   only argued for and indirectly supported by the 4-ticker sanity check's
   internal consistency.

**What's left before the real run, concretely:**

- Resolve delisting data (already in motion outside this codebase).
- Wire the Benjamini-Hochberg 18-variant grid into `run_full_pipeline.py`
  — the single most surprising gap this audit found.
- Actually perform the 20-transaction hand-check, after first confirming
  `primary_portals.py`'s URLs navigate somewhere real.
- Decide whether the F6/F3–F5 sampling caps are permanent documented
  deviations or should be lifted.
- Either build the missing per-year Model 2 variant for F7, or accept and
  report its absence as permanent.
- Route `run_holdout.py`'s result into a real T8 file instead of relying on
  captured stdout.
- Update `README.md`'s ticker-universe section so it no longer contradicts
  Addendum A.
