# Pre-Analysis Plan

## Do Congressional Sales Carry More Information Than Purchases?

**Version:** 1.0
**Committed (pre-analysis):** 2026-08-08T22:17:31Z
**Author:** Ryan McGillicuddy
**Status:** Pre-registered. No analysis code has been written or run against
this study's data as of this commit. Any change to this document after
analysis begins must be made as a new, separately dated version appended
below this one — never edited in place.

---

## 1. Motivation

Nearly all research on congressional trading focuses on purchases, because
purchase data is cleaner: a purchase is an affirmative decision to acquire
exposure, while a sale can reflect rebalancing, tax management, liquidity
needs, or divestment requirements.

But if members of Congress hold material nonpublic information, the
higher-value use of that information is often loss avoidance rather than
gain capture. Selling before adverse news is less conspicuous than buying
before favorable news, is not subject to the same public scrutiny, and
produces no visible "winning trade" for journalists to find.

This creates a testable asymmetry that the existing literature has largely
sidestepped.

## 2. Hypotheses

State these before running anything. Do not add hypotheses after seeing
results.

**H1 (main).** Disclosed congressional sales are followed by negative
abnormal returns in the underlying security, after excluding sales
attributable to rebalancing, tax management, and liquidation events.

**H2 (asymmetry).** The absolute magnitude of abnormal returns following
screened sales exceeds that following purchases over matched horizons.

**H3 (mechanism).** The sale effect is concentrated among sales that are
unusual relative to the member's own trading history ("opportunistic"
sales), and absent among members who trade on a routine schedule.

**H4 (falsification).** The sale effect should be absent or substantially
weaker in sectors outside the member's committee jurisdiction. If the
effect appears uniformly across all sectors, an information-based
explanation is weakened.

Null results on all four are a publishable finding. Commit to reporting
them.

## 3. Data

| Source | Purpose |
|---|---|
| House Clerk financial disclosure portal | Primary PTR filings, House |
| Senate Public Financial Disclosure Database | Primary PTR filings, Senate |
| Quiver Quantitative API | Cross-check and coverage gap detection |
| Daily price + return data (specify vendor) | Return calculation; must include delisted securities |
| Fama-French factor data (Ken French library) | Risk adjustment |
| Congressional committee assignment records | H4 sector mapping |

Critical: pull from the primary government sources, not only the
aggregator. You need actual filing timestamps, and aggregator coverage has
known gaps.

**Known deviation (recorded pre-analysis):** as of v1.0, this project has no
delisting-inclusive price source. The daily price data in use is
survivorship-biased (delisted/acquired/bankrupt tickers drop out of the
feed rather than carrying a delisting return). This is a documented
limitation, not a silent gap — see the Limitations section of any output
paper, and the "Delisting handling" checklist item in Section 11.

## 4. Sample construction

Period: 2014 through the most recent complete year. Hold out the final 18
months as an untouched validation sample.

**Inclusion:**

- Common stock transactions only
- Transactions above $1,000 (statutory threshold)
- Member, spouse, and dependent child transactions
- Securities with resolvable price data covering the full event window

**Exclusion:**

- Options, bonds, mutual funds, ETFs, municipal securities
- Exchanges and transfers (not directional decisions)
- Transactions in securities with fewer than 60 trading days of prior price
  history
- Duplicate filings (deduplicate on member–ticker–transaction date–amount
  band)

Log every exclusion with a count. The paper needs a sample construction
table.

## 5. The core methodological problem: screening sales

This is where the paper is won or lost. A raw "sales predict negative
returns" finding is uninteresting because sales are confounded. You must
construct a screened subsample and defend every filter.

Build the screens as a sequential funnel, reporting the count remaining
after each:

**Screen 1 — Rebalancing.** Exclude sales where the same member purchased
the same ticker within 90 days before or after, or where the sale occurs on
a date with three or more simultaneous sales across unrelated sectors.

**Screen 2 — Tax management.** Exclude sales in November and December where
the position shows an unrealized loss relative to the member's most recent
disclosed purchase of that ticker.

**Screen 3 — Liquidation events.** Exclude all transactions by a member
within a window surrounding: announced retirement, blind trust
establishment, confirmation to an executive branch position, or any date on
which the member disclosed sales of more than 60% of their disclosed
portfolio.

**Screen 4 — Routine traders.** Following the routine-versus-opportunistic
framework in the corporate insider literature, classify a member as routine
if they traded in the same calendar month in each of the three prior years.
Analyze routine and opportunistic members separately (this is H3).

Report main results on both the unscreened and screened samples. The gap
between them is itself informative.

## 6. Outcome variables

**Primary:** Cumulative abnormal return (CAR) over [+1, +30], [+1, +90], and
[+1, +180] trading days from the transaction date.

Abnormal return computed three ways, all reported:

- Market-adjusted (return minus CRSP value-weighted or SPY)
- Four-factor adjusted (Fama-French three-factor plus momentum), estimation
  window [-250, -30]
- Size- and industry-matched control portfolio (match on market cap decile
  and Fama-French 12-industry classification)

**Secondary:** Buy-and-hold abnormal return (BHAR) at the same horizons, as
a robustness check on CAR.

For sales, the informed-trading prediction is negative CAR. For purchases,
positive. H2 compares absolute magnitudes.

## 7. Empirical specification

**Model 1 — Unconditional means.** Mean CAR for screened sales and for
purchases at each horizon, with standard errors clustered at the member
level and, separately, at the calendar-month level. Report both.

**Model 2 — Pooled regression.**

```
CAR_i = β0 + β1·Sale_i + β2·Opportunistic_i + β3·(Sale × Opportunistic)_i
        + β4·CommitteeMatch_i + β5·(Sale × CommitteeMatch)_i
        + γ·Controls_i + MemberFE + YearFE + IndustryFE + ε_i
```

Controls: log market cap, book-to-market, prior 12-month return,
transaction size band, chamber, party, seniority (terms served).

β1 tests H1/H2. β3 tests H3. β5 tests H4.

**Model 3 — Calendar-time portfolio.** Construct a monthly calendar-time
portfolio of shorted screened-sale names held 90 days, regress excess
returns on the four factors, report alpha. This addresses cross-sectional
dependence in overlapping event windows, which the CAR approach handles
poorly.

## 8. Statistical discipline

Pre-specified primary test: β1 in Model 2 at the 90-day horizon, four-factor
adjusted, screened sample. Everything else is secondary.

**Multiple comparisons:** You are running 3 horizons × 3 adjustment methods
× 2 samples = 18 variants of the main test. Apply a Benjamini–Hochberg
correction across all reported tests and state the corrected threshold in
the paper.

**Random control:** For each result, sample the same number of transactions
from the same tickers on random dates within the same period. Run 1,000
iterations. Report where the actual result falls in that distribution. This
is the single most persuasive robustness check available to you.

Do not add specifications after seeing results. If you decide a new test is
warranted, mark it explicitly as post-hoc exploratory analysis in the
paper. Referees respect this; they do not respect silent specification
search.

## 9. Robustness set (pre-specified, all reported regardless of outcome)

1. Excluding the 5 and 10 most active traders
2. Year-by-year results (does the effect exist outside 2020–2021?)
3. Split by transaction size band
4. Excluding the 10 most-traded tickers
5. Excluding all technology sector transactions
6. Entry at filing date rather than transaction date (the actionability
   question)
7. Winsorizing returns at 1% and 99%
8. Restricting to members serving three or more terms
9. Senate versus House split
10. Results on the 18-month holdout sample (run last, once only)

## 10. Pre-specified output list

The bot produces exactly these. Nothing else goes in the paper.

**Tables**

- T1: Sample construction funnel with counts at each exclusion and screen
- T2: Descriptive statistics — transactions by year, chamber, party, sector,
  size band
- T3: Filing lag distribution (median, mean, p90, max, share beyond 45
  days)
- T4: Mean CAR by transaction type and horizon, all three adjustment
  methods
- T5: Model 2 regression results, full and screened samples
- T6: Model 3 calendar-time alphas
- T7: Robustness grid (all 10 checks, primary specification only)
- T8: Holdout sample results

**Figures**

- F1: Sample construction flow diagram
- F2: Filing lag histogram with 45-day line marked
- F3: Event-time CAR plot, purchases vs sales, [-30, +180], with confidence
  bands
- F4: Same, opportunistic vs routine members (H3)
- F5: Same, committee-match vs non-match (H4)
- F6: Random control distribution with actual result marked
- F7: Year-by-year effect size with confidence intervals
- F8: Calendar-time portfolio cumulative alpha

## 11. Verification requirements

Before trusting any output:

- Hand-check 20 transactions. Pull them, compute CAR manually, confirm the
  pipeline matches.
- Trading-day alignment. Confirm t+1 means the next trading day, not
  calendar day. Off-by-one errors here are the most common silent failure.
- Delisting handling. Confirm delisted securities are in the sample with
  appropriate delisting returns, not silently dropped. **(Known deviation:
  see Section 3 — this project currently has no delisting-inclusive price
  source. This checklist item cannot pass as stated; the paper must report
  the survivorship-biased sample explicitly instead of silently proceeding
  as if it passed.)**
- Ticker remapping. Match on a permanent identifier, not symbol. Symbols
  get reused.
- NaN audit. Report how many observations were dropped at each computation
  step and why.
- Reproduce end to end from raw data twice, on different days, and confirm
  identical output.

## 12. Interpretation rules

Fix these now:

- A result is reported as supportive only if it survives Benjamini–Hochberg
  correction and falls outside the 95th percentile of the random control.
- A result that appears only in 2020–2021 is reported as period-specific,
  not as a general finding.
- A result that disappears when the top 5 traders are excluded is reported
  as concentrated, not as a Congress-wide effect.
- Statistical significance without economic significance (alpha below
  plausible transaction costs) is reported as economically negligible.

## 13. What the paper does not claim

- No causal claim about information sources. You observe timing, not
  mechanism.
- No claim about any individual member.
- No claim about legality of any transaction.
- No investment recommendation.

Write these into the paper's limitations section explicitly.

---

## Addendum A (2026-08-11): Ticker universe rule

**Committed:** 2026-08-11 (pre-analysis — see status note below)
**Author:** Ryan McGillicuddy
**Status:** Committed before any universe-wide data ingestion. The only
ingestion performed as of this addendum is a four-ticker mechanical
pipeline check (AAPL, MSFT, NVDA, SPY) run to validate the codebase end
to end on live data, not to test any hypothesis — no result from that
check informed this rule. This addendum does not edit Section 3 or
Section 4 above; both remain as committed in v1.0.

**Rule.** The study's ticker universe is disclosure-defined, not
index-defined: it is the full set of distinct ticker symbols named in
any congressional financial disclosure filed within the sample period
(2014-01-01 through the most recent complete year), discovered via
Quiver Quantitative's bulk congressional-trading endpoint
(`/beta/bulk/congresstrading`), not assumed from S&P 500, Russell 3000,
or any other index membership list. A ticker enters the universe if and
only if at least one disclosure names it during the sample period.
Common-stock-only filtering and every other Section 4 inclusion/exclusion
criterion are applied AFTER universe discovery, to each ticker's own
subsequently-ingested per-ticker data, exactly as already specified in
Section 4 — this rule determines which tickers get pulled, not which
transactions survive the funnel. That determination remains entirely
Section 4's, unchanged.

**Reasoning.** An index-defined universe (e.g., current S&P 500 or
Russell 3000 constituents) was rejected for two compounding reasons.
First, it is itself survivorship-biased in exactly the way Section 3's
already-documented price-data deviation is: a company removed from a
major index because it was acquired at a discount, delisted, or went
bankrupt would be excluded from the universe entirely, for the same
underlying reason its price history disappears from the feed — deleting
the same category of evidence twice, once at the sample-construction
stage and once at the price-data stage, both times against the
strongest instances of H1. Second, an index-defined universe would
silently exclude any ticker a member genuinely disclosed trading, with
no way to distinguish "never traded" from "traded, but outside the
index we chose" — an unlogged exclusion happening before the funnel
ever sees the data, which contradicts Section 4's own "log every
exclusion with a count" requirement. A disclosure-defined universe has
neither problem: it is mechanically determined by the actual disclosed
transactions the study is about, requires no external membership list
or cutoff date for index composition, and changes nothing about which
individual trades are included or excluded — Section 4's screens apply
identically once the universe is fixed by this rule.

Verified live on the date of this addendum, not assumed: the bulk
endpoint returns the full historical dataset in a single call (114,951
disclosure records total, no pagination required); restricted to
disclosures filed within the sample period alone, it yields 5,046
distinct ticker symbols. An index-defined universe would have covered
roughly 500 (S&P 500) to 3,000 (Russell 3000) of these at most, which
concretely bounds the scale of what that alternative would have missed.
The bulk endpoint's own `TickerType` field uses a broader, less
consistent vocabulary than the per-ticker ingestion endpoint this
project already relies on for common-stock filtering (`ST` there;
several additional labels including a separate `Stock` value in the
bulk feed) — the bulk pull is used here only to discover ticker
*symbols*, not to classify them; every discovered symbol still goes
through the existing, already-reviewed per-ticker ingestion and Section
4 funnel exactly as any manually-chosen ticker would.

With this addendum committed, the specification governing sample
construction is closed: the ticker universe, the inclusion/exclusion
funnel, the screens, the outcome variables, the models, and the output
list are now all fixed before any universe-wide analysis has been run.
Any further change is post-hoc by construction and must be reported as
such.

---

## Addendum B (2026-08-12): Screen 3(a) reported with and without

**Committed:** 2026-08-12 (pre-analysis — see status note below)
**Author:** Ryan McGillicuddy
**Status:** Committed before any universe-wide or real-data analysis. The
only ingestion performed as of this addendum remains the four-ticker
mechanical pipeline check (AAPL, MSFT, NVDA, SPY) noted in Addendum A, plus
a fully synthetic-warehouse end-to-end test added to this repository's own
test suite — no real transaction, and no result under either specification
below, has informed this rule. This addendum does not edit Section 5
above, which remains as committed in v1.0.

**Rule.** Screen 3's sub-condition (a) — excluding a sale that exceeds 60%
of the member's cumulative net disclosed exposure — is applied two ways,
both reported, neither treated as the sole specification: once exactly as
Section 5 originally specifies (the default), and once with sub-condition
(a) omitted entirely, leaving only sub-condition (b) (the retirement
window) active. `sample.sample.screens.screen3_liquidation` implements
this as an `apply_3a: bool` parameter, defaulting to `True` — every
existing caller that does not pass it gets Section 5's original behavior,
unchanged. Every table and figure downstream of the screened sample is to
be produced under both settings once a real run occurs, exactly as Section
4 already requires reporting both the unscreened and screened samples
side by side ("the gap between them is itself informative") — this
addendum applies that same discipline one level deeper, to a single
sub-condition of a single screen, rather than deciding the question by
fiat before any real data has been seen.

**Reasoning.** Sub-condition (a)'s cumulative-exposure figure is built
purely from this study's own disclosed transaction amounts within the
sample period — it has no visibility into a member's true, pre-existing
portfolio, which existed before 2014-01-01 and is never observed. Two
consequences follow directly, neither of which is a coding error: first,
the sub-condition can structurally never fire for any sale where the
member's cumulative prior *disclosed* exposure is zero or negative at that
point, regardless of how large the sale truly is relative to their real
(unobserved) holdings — a member who is a net seller from the very first
disclosure in the sample can never trigger sub-condition (a), no matter
what they sell. Second, and in the opposite direction, a member with a
short disclosed history who makes one large early purchase and then a
large early sale can trigger sub-condition (a) even though that sale is a
small fraction of their true portfolio. Both failure modes point the same
way: sub-condition (a) can be wrong in either direction, and there is no
way to know, from the disclosure data alone, which members it is wrong
for. Dropping it silently would change the screened sample from what v1.0
committed to without a record of why; keeping it silently would report a
single number as if it were not sensitive to a proxy this addendum has
just shown is imperfect in a specific, structural way. Reporting both is
the only option that does not quietly resolve an open measurement question
by fiat.

This is a narrower, more targeted version of the same logic Addendum A
already applied to the ticker universe: a screening rule built from
incomplete, disclosure-only data can bias a study in a direction that
happens to align with — or against — the effect under test, and the
correct response, discovered before any real result exists, is to make the
sensitivity visible rather than to pick a side.

With this addendum committed, Screen 3 is reported under both
specifications from the first real run onward; no further decision on
sub-condition (a) is open.

---

## Addendum C (2026-08-21): Delisting-inclusive price data

**Committed:** 2026-08-21 (pre-analysis — see status note below)
**Author:** Ryan McGillicuddy
**Status:** Committed before any universe-wide or real-data analysis. The
only ingestion performed as of this addendum remains the four-ticker
mechanical pipeline check noted in Addendum A and the synthetic-warehouse
end-to-end test in this project's own test suite, plus one live,
single-ticker verification pull (Bed Bath & Beyond, described below) run
specifically to confirm this addendum's mechanism before committing to
it — not a universe-wide pull, and not informed by any result this study
is testing for. This addendum resolves Section 3's "known deviation" and
the corresponding Section 11 checklist item; it does not edit either
section's original text, which remains as committed in v1.0.

**Rule.** Tiingo (Section 3) remains the primary daily price source for
every ticker in the study universe. Separately, after the normal
per-ticker ingestion completes, every ticker whose price history
apparently ends more than 90 trading days before the sample period's
close is treated as a candidate delisting and patched with EOD Historical
Data (EODHD), a commercially licensed vendor ($199/year, "EOD Historical
Data — All World" tier) confirmed to retain full daily price history for
delisted U.S. securities through their last trading day, rather than
dropping them the way Tiingo does. The patch step queries EODHD for the
security's own exchange-assigned "Q" symbol suffix first — the
designation Nasdaq and NYSE attach specifically during a Chapter 11
proceeding — and only falls back to the security's plain ticker symbol if
that patched history resumes within 30 days of the last known date.
Whichever series is used is written into the same `equity_eod` table
every other price row lives in, keyed on the security's original ticker,
so the sample funnel, the CAR engine, and every model downstream see the
extended history with no change of their own.

**Reasoning.** A ticker symbol can be reassigned to an entirely unrelated
company after the original security delists, and this is not a
theoretical risk: verified live before this addendum was written, EODHD's
own data for the bare ticker "BBBY" is not Bed Bath & Beyond's real,
bankrupt price history at all for most of 2023 — it is the price history
of the company that later took over the same ticker after rebranding,
trading normally and continuously through the exact months the original
Bed Bath & Beyond was in bankruptcy proceedings. Querying a delisted
security's plain ticker and assuming whatever comes back belongs to the
company under study is therefore a *more* dangerous failure mode than
Tiingo's silent drop: a wrong answer that looks like a right one, rather
than a visible gap. The real, original entity's bankruptcy-period price
history — collapsing from single dollars to fractions of a cent before
final delisting — was only recoverable under its "Q"-suffixed symbol
(`BBBYQ`), confirmed by live query before this addendum was written. The
patch mechanism's ordering (Q-suffix preferred whenever it has any data;
bare-ticker data used only if it resumes within a short window of the
last known date) is built directly around this confirmed failure mode,
not a hypothetical one.

This is a partial fix, not a complete one, and is reported as such rather
than assumed to close Section 3's deviation entirely. The "Q" suffix
convention covers securities delisted via a formal Chapter 11 filing; a
security delisted for a different reason — a clean cash-out acquisition
settled after trading halts, a reverse-merger reissue under an unrelated
new symbol, or any other pattern this addendum's live verification did
not happen to encounter — may still be missed and left as a residual,
disclosed gap rather than a silently-assumed-solved one. Every ticker
this patch step cannot resolve is logged by name (a 0-row result from
`patch_all_stale_tickers`, `sources/eodhd.py`), not dropped without a
trace, matching Section 4's own "log every exclusion with a count"
discipline.

With this addendum committed, the sample no longer relies solely on a
survivorship-biased price feed. The residual gap it does not close is
disclosed in the paper's own Limitations section, alongside every ticker
this run's patch step could not resolve.
