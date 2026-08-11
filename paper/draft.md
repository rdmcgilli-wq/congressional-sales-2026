# Do Congressional Sales Carry More Information Than Purchases?

**Status of this draft:** Sections 2–6 and the Limitations/Scope sections are
drafted from the pre-analysis plan (`PRE_ANALYSIS_PLAN.md`, v1.0 and
Addendum A) and describe procedures that are implemented and validated
against live data, but not yet run at full scale — no result in this
document should be read as a finding. Section 1 (Introduction) is an
outline only, held for last per standard practice: it is easier to state
the paper's contribution precisely once the literature review has located
it. Sections 7–9 (Results, Discussion, Conclusion) are placeholders. They
wait on two things, in order: (1) resolution of the delisting-inclusive
price-data question (in progress — see `PRE_ANALYSIS_PLAN.md` Section 3's
known deviation and the outreach described in this project's own
development history), and (2) the full-universe run itself. Running the
full analysis on survivorship-biased data now would burn the
pre-registration for output that would have to be discarded once a better
price source is in hand.

**One open citation.** Section 2's treatment of Peez (2026) is a
placeholder built from the abstract only — SSRN and ResearchGate both
blocked automated retrieval of the full text (confirmed: direct HTML
fetch, direct PDF delivery-endpoint fetch, and a raw HTTP request with a
standard browser user-agent all returned HTTP 403). It needs the actual
paper — specifically the committee–industry crosswalk mechanics, the
sample period, and whatever screening (if any) Peez applies to sales
before its own name is dropped from that paragraph's flag.

---

## 1. Introduction

*[Outline only — drafted last, after the literature review below fixes
the paper's position relative to Ziobrowski, Eggers & Hainmueller, Chen &
Sacerdote, Pyun, and Peez.]*

- Open on the asymmetry: nearly all congressional-trading research studies
  purchases, because purchase data is behaviorally cleaner (an affirmative
  decision to acquire exposure) while sale data is confounded by
  rebalancing, tax management, liquidity needs, and divestment
  requirements.
- State the paper's actual move: if members hold material nonpublic
  information, loss avoidance is the less conspicuous, less scrutinized
  use of it — no visible "winning trade," no story. That should push any
  real information advantage toward the sale side, which is exactly the
  side the literature has not screened.
- One paragraph on what "screened" means and why it is the paper's real
  contribution, not a footnote — point forward to Section 5.
- State H1–H4 plainly (Section 2 below already carries their content;
  this paragraph just needs to introduce them, not re-derive them).
- Close with what the paper does not claim (Section 9 below has the full
  list) and the pre-registration timestamp — both belong in the
  introduction's last paragraph, not buried at the end.

---

## 2. Literature Review

The empirical literature on congressional trading divides cleanly along a
line this paper is designed to sit across: studies that find abnormal
returns on the **purchase** side, and studies that, testing trading
broadly rather than screening it, find none.

**Ziobrowski, Cheng, Boyd, and Ziobrowski (2004)** established the
field's central stylized fact. Using disclosed transactions of U.S.
Senators, they found that a portfolio mimicking Senate purchases beat the
market by roughly 85 basis points per month, while a portfolio mimicking
Senate sales lagged the market by roughly 12 basis points per month
(Ziobrowski et al. 2004, *Journal of Financial and Quantitative
Analysis*). The purchase-side result became the field's headline finding
and the one nearly every subsequent paper, popular or academic, has
reproduced or contested. The sale-side result — an order of magnitude
smaller, oppositely signed relative to the informed-selling prediction as
naively stated, and never itself decomposed into rebalancing, tax,
liquidity, and information-driven components — was reported and then
largely set aside. **Ziobrowski, Boyd, Cheng, and Ziobrowski (2011)**
extended the same design to the House of Representatives (roughly 16,000
transactions, 1985–2001) and again found a significant purchase-side
result, smaller than the Senate estimate (about 55 basis points per
month), with the sale side again not separately pursued. Later work
applying alternative specifications to the Senate sample found the
original purchase-side result significant in as few as three of eight
tested specifications, underscoring that raw, unscreened congressional
returns are sensitive to modeling choices in a way a single headline
coefficient obscures.

**Eggers and Hainmueller (2013)**, using 2004–2008 disclosures, found the
opposite: no evidence of informed trading or above-market returns for
Congress as a whole or for any subset of members they tested, with the
average member underperforming the market by 2–3% annually over the
period — a result they summarized as political insider trading being
"more myth than reality" for that window. Read next to Ziobrowski et al.,
the disagreement is informative on its own: two credible designs, applied
to overlapping populations in different periods, reach opposite headline
conclusions without either screening sales for the confounds this paper's
Section 5 treats as the central methodological problem. **Eggers and
Hainmueller (2014)**, in a companion paper on the same sample, found that
members' *politically connected* investments — holdings in firms with a
geographic or committee-based tie to the member — outperformed their
unconnected holdings, while the unconnected holdings largely explained
the aggregate underperformance. That result matters for this paper for a
specific reason: it is evidence that connection-based informational
advantage is real and detectable in *some* dimension of congressional
portfolios even in a sample where aggregate trading shows no edge,
which is precisely the logic behind this paper's H4 (committee-match
falsification test) — connection should matter for returns even when
undifferentiated trading does not.

**Chen and Sacerdote (2026)**, in an NBER working paper covering
2012–2023 disclosures (post-STOCK Act), reached a conclusion closer to
Eggers and Hainmueller than to Ziobrowski et al.: legislators'
portfolios, on average, match or underperform market benchmarks, and
members' trade timing tracks retail-investor sentiment more than it
anticipates subsequent market moves. Their result is the most recent and
most direct evidence that whatever edge congressional trading may carry,
it is not visible in an *aggregate, unscreened* portfolio-mimicking
design — which is not a result this paper's hypotheses are staked
against, since H1 is stated specifically as a claim about *screened*
sales, not about congressional portfolios generally. If anything, Chen
and Sacerdote's null aggregate finding sharpens the question this paper
asks: whether that null result. survives, reverses, or strengthens once
rebalancing-, tax-, and liquidation-driven sales are removed from the
sample is exactly what Section 4's "report both the unscreened and
screened samples — the gap between them is itself informative" is built
to test directly, rather than assume.

**Pyun (2025)** is the paper in this literature closest to this study's
own robustness design rather than its main hypothesis. Exploiting the
STOCK Act's distinction between transaction date and disclosure (report)
date, Pyun finds return predictability is stronger measured from the
transaction date than from the report date — consistent with informed
insiders having a first-mover advantage — but that predictability remains
economically meaningful even measured from the later, publicly knowable
report date. Pyun's predictability is concentrated in large-cap firms and
in purchases by Representatives, strengthening post-COVID. This paper's
own primary specification anchors on transaction date for the same
reason Pyun's first result does (testing foreknowledge rather than public
actionability), and Section 9's robustness item 6 (entry at report date)
is a direct analogue of Pyun's own transaction-versus-report comparison,
run here specifically on the screened sale side rather than on purchases.

**Peez (2026)** is the paper closest to this study's H4 specifically, and
the one this section cannot yet fully place. Working from the abstract
alone: Peez classifies congressional stock *sales* as jurisdictional or
non-jurisdictional using a rule-based committee–industry crosswalk with
dynamic session-level committee assignment, evaluates the two groups
through calendar-time portfolios estimated with a Carhart four-factor
model, and reports a statistically significant short-horizon sell spread
of 7.23% over 20 trading days — jurisdictionally relevant sales followed
by more negative abnormal returns than non-jurisdictional sales, an
effect more pronounced in the House. *[PLACEHOLDER — full paper needed.
Once available: state Peez's exact sample period and committee-crosswalk
construction, note whether Peez screens sales for rebalancing/tax/
liquidation at all or tests the raw sale side directly, and position this
paper's contribution against it explicitly — broader hypothesis scope
(H1–H3 in addition to the H4-adjacent question), a four-screen exclusion
funnel Peez's abstract does not describe, and three abnormal-return
methods against Peez's one. Do not finalize this paragraph, or write
Section 1's introduction, before this is resolved.]*

Finally, this paper's H3 (the opportunistic-versus-routine trader split)
is not new to congressional trading; it is imported directly from the
corporate insider-trading literature. **Cohen, Malloy, and Pomorski
(2012)**, using SEC Form 4 filings, showed that a large share (over half)
of all corporate insider trades follow a predictable, recurring personal
pattern — "routine" trades — that carry no informational content: their
own abnormal returns are statistically indistinguishable from zero.
Stripping routine trades out of the sample isolates "opportunistic"
trades that carry essentially all of the insider-trading universe's
predictive power, worth 82 basis points per month value-weighted, with
the most informative opportunistic traders concentrated among local,
non-executive insiders at geographically concentrated, poorly governed
firms. This paper's Screen 4 — classifying a member as routine if they
traded the same calendar month in each of the three prior years, and
analyzing routine and opportunistic members separately — is a direct
transplant of Cohen, Malloy, and Pomorski's classification logic onto
congressional rather than corporate insiders, and H3 is the same
prediction in the new setting: any information-driven sale effect should
be concentrated among opportunistic sellers and absent among routine
ones.

**Where this paper sits.** No paper in this set does all four of the
following at once: (1) treat the sale side as the primary object of
study rather than a residual comparison to purchases; (2) construct and
defend a sequential screening funnel that removes rebalancing, tax-loss
harvesting, and liquidation-event sales before testing for an
information effect, rather than testing raw, unscreened sales; (3)
report results on both the unscreened and screened samples so the gap
between them is itself evidence; and (4) pre-register all four hypotheses,
every screen, every model, the full robustness set, and the complete
output list before running anything against real data. Ziobrowski et al.
and Peez find sale-side or jurisdiction-side signal without this paper's
screening step; Eggers and Hainmueller and Chen and Sacerdote find no
aggregate signal without asking whether a screened subsample would differ;
Pyun and Cohen–Malloy–Pomorski supply, respectively, the disclosure-timing
and routine/opportunistic machinery this paper imports and applies to the
sale side specifically. The gap those four leave — a pre-registered,
sale-focused, fully screened test of informed selling in Congress — is
this paper's contribution.

---

## 3. Institutional Background: The STOCK Act

The Stop Trading on Congressional Knowledge Act ("STOCK Act") was signed
into law in April 2012. Before it, members of Congress were already
subject to annual financial disclosure requirements, but nothing compelled
prompt, transaction-level public disclosure of individual trades — a
sale made in January might not become visible to the public until the
following year's annual filing. The STOCK Act's central mechanical change
was the Periodic Transaction Report (PTR): covered individuals — members
of Congress, certain congressional officers and employees, and other
covered federal officials — must file a report of a covered transaction
within 30 days of being notified of it, and in no case later than 45 days
after the transaction itself. Covered transactions are purchases, sales,
and exchanges of stocks, bonds, commodity futures, and other securities
exceeding $1,000 in value; the requirement explicitly reaches transactions
by a covered official's spouse and dependent children, and explicitly
exempts widely held investment vehicles such as mutual funds from the
accelerated (PTR-level) reporting requirement, though not from annual
disclosure.

Three features of this statutory design are load-bearing for this paper's
own construction, not incidental background:

- **The $1,000 statutory threshold** this paper's sample-construction
  rule (Section 4) inherits is not an analytical choice — it is the
  STOCK Act's own reporting floor. A transaction below it is never
  disclosed at all, so no filtering decision on this project's part
  determines what enters the disclosed universe below that line; the
  statute already has.
- **The spouse-and-dependent-child scope** is why this paper's sample
  construction does not implement a separate filer-relationship screen
  (noted directly in `sample/funnel.py`'s own module docstring): every
  disclosed PTR transaction already covers all three relationships by
  the legal definition of what a PTR filing is, so there is no
  "member-only" subset to construct that the disclosure regime itself
  has not already merged.
- **The transaction-date/report-date gap the 45-day rule creates** is the
  single fact this paper's primary specification and its Section 9
  robustness item 6 are both built around. A transaction is knowable to
  the member on the transaction date; it becomes knowable to the public,
  and therefore actionable by anyone else, only on the report date, up to
  45 days later. Testing from the transaction date asks whether members
  had foreknowledge; testing from the report date asks whether the
  disclosed information itself was actionable. Pyun (2025, discussed in
  Section 2) is the closest existing evidence on how much this
  distinction matters in practice, and this paper's own primary/
  robustness split is designed to produce a second, independent estimate
  of the same gap, specific to the screened sale side.

---

## 4. Data

Six data sources were used, matched one-to-one against
`PRE_ANALYSIS_PLAN.md` Section 3:

| Source | Role in this study |
|---|---|
| Quiver Quantitative API | Primary source for disclosed congressional transactions (ticker, transaction type, transaction date, report date, disclosed amount range, filer) |
| Tiingo | Daily equity end-of-day prices, split/dividend-adjusted |
| Ken French Data Library | Daily Fama-French three-factor plus momentum factors, for risk adjustment |
| `unitedstates/congress-legislators` (public-domain dataset) | Member term histories (chamber, party, state, term start/end dates) |
| `unitedstates/congress-legislators` committee-assignment records | Current committee assignments, used to construct the committee–industry jurisdiction mapping for H4 |
| SEC EDGAR | Ticker-to-SIC-code resolution, used to assign each security a Fama-French 12-industry classification |

**A documented deviation from the original data plan, decided before any
analysis began.** The original plan specified pulling primary PTR filings
directly from the House Clerk's and Senate's own disclosure portals, using
Quiver only as a cross-check. That was not implemented. Both primary
portals restrict bulk use of their disclosure data to non-commercial,
research, or news purposes under federal statute, and the decision made
before any code was written was to treat Quiver — a paid, actively
maintained aggregator already used elsewhere in this research program —
as the primary trade-level source, reserving the primary portals for a
small, manually triggered, non-bulk verification pull supporting the
20-transaction hand-check this paper's verification protocol requires
(Section 8 below). This is a real deviation from the original data table,
not a silent one: it is recorded here, and the light-touch verification
step it necessitates is part of the paper's verification protocol, not an
afterthought.

**Ticker universe.** The set of securities considered is disclosure-defined,
not index-defined (Addendum A, `PRE_ANALYSIS_PLAN.md`): every ticker that
appears in at least one congressional disclosure filed within the sample
period was included, discovered via Quiver's bulk congressional-trading
endpoint rather than assumed from S&P 500, Russell 3000, or any other
index-membership list. This choice was made, and verified against a live
pull of the endpoint, specifically to avoid compounding the survivorship
problem described immediately below at the sample-construction stage as
well as the price-data stage — an index-defined universe would silently
drop exactly the companies most likely to have been delisted, acquired at
a discount, or gone bankrupt, for the same underlying reason their price
histories are absent from the return data.

**Known deviation, recorded pre-analysis: survivorship bias in price
data.** As of this draft, no delisting-inclusive price source is in use.
The daily price feed drops a security from the data once it is delisted,
acquired, or ceases trading, rather than carrying a delisting return for
it (the academic convention for this correction — following Shumway
1997 and its refinement in Shumway and Warther 1999 — imputes a return,
conventionally −30% to −55% depending on exchange and delisting reason,
for the final period a security is held through a performance-related
delisting). This is a materially more serious limitation for this study
than it would be for most: H1 predicts that informed sales precede
negative subsequent returns, and the single strongest instance of that
prediction — a member selling ahead of a bankruptcy, a forced merger, or
a delisting for cause — is mechanically the transaction most likely to
have its outcome deleted from a survivorship-biased feed rather than
measured by it. Beaver, McNichols, and Price (2007) show directly that
this kind of omission is not random noise: delisting firm-years cluster
disproportionately in the extreme decile of exactly the kind of variable
this paper sorts on, systematically biasing measured effect sizes rather
than merely adding variance to them. Resolving this — most likely through
CRSP delisting-inclusive returns accessed via an institutional
affiliation — is a precondition for the full-scale run this paper reports
on, not a caveat added after the fact; see the Limitations section below
for the full statement that will ship with whichever resolution is
reached.

---

## 5. Sample Construction

The sample period runs from January 1, 2014 through the most recently
completed calendar year at the time of the full-scale run, with the final
18 months of that period held out entirely as an untouched validation
sample, evaluated once, after every other result in this paper is final
(Section 8 below).

Transactions were included if they met all of the following:

- The disclosed transaction was in common stock (Quiver's own instrument
  classification), excluding options, bonds, mutual funds, ETFs, and
  municipal securities.
- The transaction was a directional purchase or sale, excluding exchanges
  and transfers. Because the underlying disclosure data records sale
  transactions under several literal strings rather than one canonical
  label (for example, distinguishing a full sale from a partial one),
  this step normalizes any disclosed value denoting a sale to a single
  canonical category before applying the directional filter, so that a
  partial-sale disclosure is not misclassified as a non-directional
  transaction, and, separately, so that no non-directional transaction
  (an exchange or a transfer) can reach the analysis miscoded as a
  purchase by omission.
- The disclosed transaction amount exceeded the $1,000 statutory
  reporting threshold (Section 3 above).
- The security had at least 60 trading days of price history prior to
  the transaction and a full forward window of price history following
  it, sufficient to compute every outcome variable at every horizon
  (Section 6 below).
- The filing was not a duplicate of an already-counted disclosure,
  deduplicated on the combination of member, ticker, transaction date,
  and disclosed amount band.

Every step in this funnel is logged with an exact count of transactions
entering and surviving it; that log is this paper's Table 1.

**The screening funnel (the paper's central methodological contribution).**
A raw finding that congressional sales predict negative subsequent returns
would not, on its own, be informative, because sales are confounded by
ordinary portfolio activity unrelated to information. Four sequential
screens were applied to the included sample, each removing a specific,
named category of non-informational sale, with the count surviving each
screen reported alongside the count entering it:

1. **Rebalancing.** A sale was excluded if the same member purchased the
   same security within 90 days before or after it, or if the sale
   occurred on a date on which the same member disclosed three or more
   simultaneous sales across distinct securities.
2. **Tax management.** A sale made in November or December was excluded
   if the position showed an unrealized loss relative to the member's
   most recent disclosed purchase of that security — the canonical
   signature of tax-loss harvesting rather than an information-driven
   exit.
3. **Liquidation events.** All transactions by a member were excluded
   within a window surrounding that member's apparent departure from
   Congress (approximated from the most recent known end of that
   member's term, where no subsequent term exists in the data) or
   around any date on which the member's cumulative disclosed net
   exposure indicates a sale of more than 60% of it. Two liquidation
   triggers named in the original plan — blind trust establishment and
   confirmation to an executive-branch position — have no available
   structured data source and were not implemented; this is a stated
   scope limitation, not a silent gap (see Limitations).
4. **Routine traders.** Following the routine-versus-opportunistic
   classification introduced for corporate insiders by Cohen, Malloy,
   and Pomorski (2012, Section 2 above), a member was classified as a
   routine trader if they traded the same security in the same calendar
   month in each of the three prior years; routine and opportunistic
   traders were analyzed separately as the direct test of H3.

Results are reported on both the unscreened and the screened sample at
every stage of this paper. The gap between the two is treated as evidence
in its own right, not discarded once the screened result is in hand.

---

## 6. Methodology

### 6.1 Outcome Variables

The primary outcome is the cumulative abnormal return (CAR) to the
underlying security over three post-transaction windows: [+1, +30],
[+1, +90], and [+1, +180] trading days, measured from the transaction
date for the paper's primary specification and, separately, from the
report date as a robustness check on the actionability question (Section
3 above; Section 6.4 below). Abnormal return was computed three
independent ways, with all three reported for every horizon:

- **Market-adjusted**, the security's return minus a market benchmark
  return over the same window.
- **Four-factor adjusted**, using coefficients from a Fama-French
  three-factor-plus-momentum model estimated over the [-250, -30]
  trading-day window preceding the transaction.
- **Size- and industry-matched**, against a control portfolio matched on
  trailing dollar-volume decile (a market-capitalization proxy; no
  shares-outstanding source was available — see Limitations) and
  Fama-French 12-industry classification, drawn from this study's own
  screened sample universe rather than the broader market.

Buy-and-hold abnormal return (BHAR) was computed at the same three
horizons, by the same three methods, as a secondary robustness check
against CAR's known sensitivity to compounding-order effects. For sales,
the informed-trading prediction is a negative abnormal return; for
purchases, positive. H2 (the asymmetry hypothesis) compares the absolute
magnitude of the two, not their sign.

### 6.2 Empirical Specification

Three models were pre-specified, with a single one designated primary
before any result existed.

**Model 1 (unconditional means).** The mean CAR for screened sales and,
separately, for purchases, was computed at each horizon and by each
method, with standard errors clustered at the member level and,
separately, at the calendar-month level — both reported, not one chosen
in preference to the other.

**Model 2 (pooled fixed-effects regression), the paper's pre-specified
primary specification.**

```
CAR_i = β0 + β1·Sale_i + β2·Opportunistic_i + β3·(Sale × Opportunistic)_i
        + β4·CommitteeMatch_i + β5·(Sale × CommitteeMatch)_i
        + γ·Controls_i + MemberFE + YearFE + IndustryFE + ε_i
```

β1 is this paper's single pre-registered primary test, evaluated at the
90-day horizon, four-factor-adjusted CAR, on the screened sample; β1
tests H1 and, via its magnitude relative to the corresponding purchase
coefficient, H2. β3 tests H3; β5 tests H4. Standard errors were clustered
at the member level. Controls included trailing dollar-volume (as a
log-transformed size proxy), prior 12-month return, transaction size
band, chamber, party, and seniority (terms served); book-to-market was
specified in the original plan but omitted here for lack of an available
data source (see Limitations). Chamber and party, while specified as
controls, are not separately identified alongside a member fixed effect,
since both are time-invariant within a member over the sample window and
are therefore mechanically absorbed by that fixed effect — a direct,
expected consequence of including MemberFE as specified, not a deviation
from it.

**Model 3 (calendar-time portfolio).** A monthly calendar-time portfolio
of shorted screened-sale names, held for a period approximated at three
calendar months (the standard convention in this literature, given that
a calendar-time portfolio is rebalanced monthly by construction and an
exact 90-trading-day count does not translate into it cleanly), was
regressed on the four factors; the intercept (alpha) is the reported
quantity. This addresses cross-sectional dependence across overlapping
event windows, which the CAR-based models handle poorly by design.

### 6.3 Statistical Discipline

The pre-specified primary test is β1 in Model 2, at the 90-day horizon,
four-factor adjusted, on the screened sample. Every other result in this
paper is secondary to it.

Three horizons, three adjustment methods, and two samples (unscreened
and screened) together produce 18 variants of the main test. A
Benjamini-Hochberg correction was applied across all 18, and the
corrected significance threshold is reported wherever a result from this
grid is discussed.

For each reported result, a random-control test resampled the same
number of transactions from the same tickers on random dates within the
same sample period, for 1,000 iterations, reporting where the actual
result falls within that simulated distribution — the single most
persuasive robustness check available given the design, and treated
accordingly.

No specification was added after seeing results. Any analysis conducted
after this point that was not pre-specified above is reported explicitly
as post-hoc exploratory work, not folded into the primary findings.

### 6.4 Robustness

Ten checks were pre-specified against the primary specification, each
reported regardless of outcome: excluding the 5 and 10 most active
traders; year-by-year results, to test whether any effect is general or
concentrated in 2020–2021; splitting by transaction size band; excluding
the 10 most-traded tickers; excluding technology-sector transactions;
re-anchoring entry at the report date rather than the transaction date
(the actionability question, Section 3 above); winsorizing returns at
the 1st and 99th percentiles; restricting to members serving three or
more terms; a Senate-versus-House split; and, run last and exactly once,
the 18-month holdout sample untouched by every result above it.

---

## 7. Results

*[Pending. Waits on resolution of the delisting-data question and the
full-universe run. No number in this section exists yet.]*

## 8. Discussion

*[Pending — depends on Section 7.]*

## 9. Conclusion

*[Pending — depends on Sections 7–8.]*

---

## Limitations

- **Survivorship bias.** No delisting-inclusive price source is in use as
  of this draft (Section 4 above); this is the paper's most consequential
  open limitation and is being actively addressed, not merely disclosed.
- **Screen 3 (liquidation events) scope.** Only the >60%-of-disclosed-
  portfolio-sold condition and a term-end-based retirement proxy are
  implemented. Blind trust establishment and confirmation to an
  executive-branch position have no available structured data source and
  are not detected.
- **Committee-assignment data is a current-only snapshot**, not a
  historical per-Congress record; H4's committee-match variable uses each
  member's most recently known assignment, not their assignment at the
  time of the transaction.
- **Size and industry matching** use trailing dollar volume as a proxy
  for market capitalization, matched within this study's own sample
  universe rather than the full market, for lack of a shares-outstanding
  data source.
- **Book-to-market is omitted** from Model 2's control set for lack of an
  available data source.
- **The 90-day Model 3 holding period is approximated as three calendar
  months**, the standard convention in the calendar-time-portfolio
  literature, not an exact trading-day count.
- **Model 3's reported standard errors are not Newey-West adjusted.**
  With overlapping monthly holding-period composition, this can
  understate the true standard error; the point estimate is unaffected,
  and the uncorrected estimator was kept as the pre-registered choice
  rather than switched after the fact.
- **All trade-level data is sourced from Quiver Quantitative**, not
  pulled directly from the House Clerk or Senate disclosure systems
  (Section 4 above); a small, non-bulk manual cross-check against the
  primary portals is part of this paper's verification protocol, not a
  substitute for full independent sourcing.
- **Every match in this study keys on the ticker symbol**, not a
  permanent security identifier; a ticker-reuse audit detects but does
  not remap cases of one CIK mapping to more than one historical symbol.
- **Buy-and-hold abnormal return (BHAR)** is computed at every horizon
  and by every method as specified, but is not separately tabulated in
  this draft's output list beyond its role as a robustness cross-check
  on CAR.

## What This Paper Does Not Claim

No causal claim about information sources is made — this paper observes
timing, not mechanism. No claim about any individual member is made. No
claim about the legality of any transaction is made. No investment
recommendation is made.

---

## References

Beaver, W., McNichols, M., and Price, R. (2007). Delisting Returns and
Their Effect on Accounting-Based Market Anomalies. *Journal of Accounting
and Economics*, 43(2–3), 341–368.

Chen, H., and Sacerdote, B. (2026). Capital in the Capitol: Congressional
Trades Resemble Uninformed Retail Trading. NBER Working Paper No. 35041.

Cohen, L., Malloy, C., and Pomorski, L. (2012). Decoding Inside
Information. *Journal of Finance*, 67(3), 1009–1043.

Eggers, A. C., and Hainmueller, J. (2013). Capitol Losses: The Mediocre
Performance of Congressional Stock Portfolios, 2004–2008. *Journal of
Politics*, 75(2), 535–551.

Eggers, A. C., and Hainmueller, J. (2014). Political Capital: Corporate
Connections and Stock Investments in the U.S. Congress, 2004–2008.
*Quarterly Journal of Political Science*, 9(2), 169–202.

Peez, L. (2026). The Impact of Committee Jurisdiction on Sell-Side
Information Asymmetry. Working paper, SSRN. *[Full citation pending —
see placeholder note, Section 2 above.]*

Pyun, C. (2025). Congressional Trading, Informational Advantages, and
Disclosure Timing. Working paper, SSRN.

Shumway, T. (1997). The Delisting Bias in CRSP Data. *Journal of
Finance*, 52(1), 327–340.

Shumway, T., and Warther, V. A. (1999). The Delisting Bias in CRSP's
Nasdaq Data and Its Implications for the Size Effect. *Journal of
Finance*, 54(6), 2361–2379.

Ziobrowski, A. J., Cheng, P., Boyd, J. W., and Ziobrowski, B. J. (2004).
Abnormal Returns from the Common Stock Investments of the United States
Senate. *Journal of Financial and Quantitative Analysis*, 39(4), 661–676.

Ziobrowski, A. J., Boyd, J. W., Cheng, P., and Ziobrowski, B. J. (2011).
Abnormal Returns from the Common Stock Investments of Members of the
U.S. House of Representatives. *Business and Politics*, 13(1).
