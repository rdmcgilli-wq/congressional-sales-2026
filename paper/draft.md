# Do Congressional Sales Carry More Information Than Purchases?

**Status of this draft.** Sections 2–6 and the Limitations section are
written from the pre-analysis plan (`PRE_ANALYSIS_PLAN.md` v1.0,
Addendum A, and Addendum B) and describe procedures that are implemented,
tested, and validated end to end against synthetic and narrow live data —
but not yet run at full scale. Nothing in this document should be read as
a finding. Sections 7–9 (Results, Discussion, Conclusion) are placeholders
and stay that way until two things happen, in order: resolution of the
delisting-inclusive price-data question (a faculty contact has agreed to
help; the specifics of that help, including a path to a delisting-
inclusive source, are still being worked out as of this draft), and the
full-universe run itself. Running the analysis on survivorship-biased
data now would spend the pre-registration on output that would have to be
discarded once a better price source is in hand.

**For the author, before this goes further.** A referee — or a professor
asked to look at the identification strategy — will ask about some subset
of these. Each is a defensible, documented choice, not an error, but
"defensible" only helps if you can explain the reasoning yourself, not
just point at the code comment that made the call.

- The $1,000 statutory threshold is applied as a strict *greater-than*.
  A transaction disclosed at exactly $1,000 is excluded. (Section 5.)
- Screen 1's "unrelated sectors" condition is implemented as
  *distinct tickers*, not distinct sectors — a weaker proxy than the plan's
  literal wording, because the screen is built as a pure function that
  does not depend on the industry classification join. (Section 5.)
- Screen 3's cumulative-exposure sub-condition is now reported two ways —
  with and without — because it is built entirely from this study's own
  disclosed transaction data and has no visibility into a member's true,
  pre-existing portfolio (Addendum B). Know why both numbers are in the
  paper, not just one.
- The committee-to-industry mapping behind H4 is a hand-built, thirteen-
  entry keyword table — an explicit research judgment about which
  committees plausibly have jurisdiction over which Fama-French sectors,
  not a fact pulled from an official source. It is the single most
  subjective piece of machinery in the paper and it feeds the
  falsification test directly.
- CAR is anchored on the transaction date for the primary specification
  and Models 1–2, but on the report date for Model 3's calendar-time
  portfolio. This looks inconsistent on a first read. It isn't: the two
  models are asking different questions (foreknowledge vs. actionability),
  and Model 3 cannot short a stock before its sale is public. Be ready to
  say that in one sentence, not five.
- Chamber and party are listed as Model 2 controls in the pre-analysis
  plan but never appear as estimated coefficients. This is forced by
  member fixed effects, not a deviation — a time-invariant covariate is
  perfectly collinear with a fixed effect on it — but "it's forced by the
  math" is a sentence you should be able to say cold.
- Two Section 7 controls are substituted or dropped: log market
  capitalization becomes log trailing dollar volume (no shares-outstanding
  source), and book-to-market is omitted entirely (no source at all).

---

## 1. Introduction

Congressional trading research has a lopsided history: nearly every study
of it looks at purchases. That is a reasonable place to start, because a
purchase is behaviorally legible — an affirmative decision to acquire
exposure — while a sale can mean almost anything: rebalancing a
concentrated position, harvesting a loss before year-end, liquidating
ahead of retirement, or genuinely acting on information nobody else has.
The result is a literature that has spent two decades asking whether
members of Congress buy well, and largely stopped asking whether they sell
well, on the tacit assumption that the sale side is too noisy to say
anything about.

This paper argues that assumption has the incentive backward. If a member
of Congress holds material nonpublic information, the *lower-risk* use of
it is not buying before good news — it is selling before bad news. A
well-timed purchase produces a winning trade that a journalist can find
years later and a reporter can headline. A well-timed sale that simply
avoids a loss produces nothing to find: no outsized gain, no visible
"beat the market" trade, nothing that stands out in a disclosure filing
next to hundreds of routine ones. If informed trading exists in Congress
at all, the sale side is where it should be hardest to see and easiest to
do — which is exactly why it has not been screened the way the purchase
side has.

Screening is this paper's actual contribution, not a footnote to it. A raw
comparison of sales to purchases is close to uninformative, because the
sale side is dominated by transactions that have nothing to do with
information: a member selling to buy something else, selling in December
for tax reasons, or selling because they are retiring and liquidating a
portfolio. Section 5 builds a four-screen funnel that removes each of
these categories in turn, reports the count excluded at every step, and —
critically — reports results on the unscreened and screened samples side
by side, so the size of the gap between them is itself part of the
evidence rather than a number that disappears once the "real" result is
in hand.

Four hypotheses follow directly from this design. **H1** predicts that
screened sales are followed by negative abnormal returns. **H2** predicts
that the magnitude of that effect, if it exists, exceeds the corresponding
purchase-side effect — the asymmetry the introduction opened with, stated
as a testable claim. **H3** predicts that any sale-side effect is
concentrated among members trading off their own routine schedule
("opportunistic" sellers) and absent among members who trade the same way
every year regardless of what is happening around them. **H4** is a
falsification test: if the effect is genuinely information-driven, it
should be stronger for sales in sectors a member's committee assignment
gives them some plausible access to, and weak or absent elsewhere; if it
shows up uniformly across every sector a member trades in, an
information-based story is a harder story to tell.

This paper does not claim to observe why a member sold, only when, and it
does not make any claim about a specific member, the legality of any
transaction, or an investment strategy — Section 9 states these boundaries
explicitly and they are binding, not throat-clearing. The hypotheses,
screens, models, and complete output list above were fixed in
`PRE_ANALYSIS_PLAN.md`, timestamped 2026-08-08, before any of this
paper's code was run against real data.

---

## 2. Literature Review

The empirical literature on congressional trading splits along a line
this paper is built to sit across: studies that find abnormal returns on
the purchase side, and studies that test trading broadly, without
screening it, and find none.

**Ziobrowski, Cheng, Boyd, and Ziobrowski (2004)** set the field's central
stylized fact. Using disclosed transactions of U.S. Senators, they found a
portfolio mimicking Senate purchases beat the market by roughly 85 basis
points a month, while a portfolio mimicking Senate sales lagged the market
by about 12 basis points a month. The purchase-side number became the
result nearly every later paper, academic or popular, has reproduced or
argued with. The sale-side number — an order of magnitude smaller,
oppositely signed relative to a naive informed-selling prediction, and
never itself broken into rebalancing, tax, liquidity, and
information-driven components — was reported once and largely left alone.
**Ziobrowski, Boyd, Cheng, and Ziobrowski (2011)** extended the same
design to the House (roughly 16,000 transactions, 1985–2001) and again
found a significant purchase-side result, smaller than the Senate
estimate, again without separately pursuing the sale side. Later work
applying alternative specifications to the original Senate sample found
the purchase-side result significant in as few as three of eight tested
specifications — a reminder that raw, unscreened congressional returns are
sensitive to modeling choices in a way a single headline coefficient
does not show.

**Eggers and Hainmueller (2013)**, working from 2004–2008 disclosures,
found the opposite: no evidence of informed trading or above-market
returns for Congress as a whole or for any subset of members they tested,
with the average member underperforming the market by 2–3% a year over
the period — summarized in their own words as political insider trading
being "more myth than reality" for that window. Set next to Ziobrowski et
al., the disagreement is itself informative: two credible designs, applied
to overlapping populations in different periods, reach opposite headline
conclusions without either one screening sales for the confounds this
paper treats as the central problem. A companion paper, **Eggers and
Hainmueller (2014)**, found that members' *politically connected*
holdings — positions in firms with a geographic or committee-based tie to
the member — outperformed their unconnected holdings, and that the
unconnected holdings accounted for most of the aggregate underperformance.
That result matters here specifically: it shows connection-based
informational advantage can be real and detectable in one dimension of a
congressional portfolio even when aggregate trading shows no edge at all,
which is the same logic behind this paper's H4. Connection should matter
for returns even when undifferentiated trading does not.

**Chen and Sacerdote (2026)**, in an NBER working paper covering
2012–2023 disclosures — the post-STOCK Act period this paper's own sample
falls within — reach a conclusion closer to Eggers and Hainmueller than to
Ziobrowski et al.: legislators' portfolios match or underperform market
benchmarks on average, and members' trade timing tracks retail-investor
sentiment more than it anticipates subsequent market moves. This is the
most recent and most direct evidence that whatever edge congressional
trading carries is not visible in an aggregate, unscreened
portfolio-mimicking design. It is not, however, evidence against this
paper's hypotheses, which are stated specifically about *screened* sales,
not congressional trading in general. If anything, an aggregate null
result sharpens the question: whether it survives, reverses, or
strengthens once rebalancing-, tax-, and liquidation-driven sales are
removed is exactly what this paper's screened-versus-unscreened comparison
is built to answer directly rather than assume.

**Pyun (2025)** is the paper in this literature closest to this study's
robustness design, rather than its central hypothesis. Exploiting the
STOCK Act's gap between transaction date and report date, Pyun finds
return predictability is stronger measured from the transaction date than
from the report date — consistent with informed insiders moving first —
but that predictability remains economically meaningful even measured
from the later, publicly knowable report date, concentrated in large-cap
firms and in purchases by Representatives, and strengthening after 2020.
This paper's primary specification anchors on the transaction date for
the same reason Pyun's does: it is testing foreknowledge, not public
actionability. The report-date robustness check (Section 6.4, item 6) is
a direct analogue of Pyun's own comparison, run here on the screened sale
side rather than on purchases.

**Peez (2026)** is the paper closest to this study's H4, and now that the
full text is in hand rather than only the abstract, the comparison can be
made precisely rather than provisionally. Peez classifies each
congressional sale (and, separately, purchase) as jurisdictional or
non-jurisdictional using a committee-industry crosswalk built at the
level of the official committee code, mapped to granular Yahoo Finance
industry categories rather than a broader sector scheme, with
session-by-session dynamic assignment so a member's jurisdiction is
evaluated as of the transaction rather than fixed over their career.
Committees with broad, non-sector-specific mandates (Appropriations, the
Budget Committee) are coded as general jurisdiction and excluded from
matching entirely, rather than defaulted into a catch-all sector. Using
Quiver Quantitative — the same vendor this study draws on — over a
2013–2025 sample of 336 trading members and roughly 108,500 directional
transactions, Peez evaluates jurisdictional and non-jurisdictional
portfolios through calendar-time regressions on the Carhart four-factor
model at 20-, 130-, and 255-trading-day horizons, and reports the
paper's central result at the shortest of the three: a jurisdictional
sell spread (non-jurisdictional minus jurisdictional sell alpha) of 7.23%
over 20 trading days (t = 2.14), concentrated in the House (8.61%,
t = 2.29) and not significant in the Senate (5.36%, t = 0.67). The spread
narrows to marginal significance at 130 days and is indistinguishable
from zero by 255 days — a decay pattern that bears directly on this
paper's own horizon choice: if a comparable effect exists in this study's
own sample, Peez's result suggests it should be strongest near this
paper's 30-day window and largely gone by 180, not uniform across all
three.

Two design choices separate the papers directly. First, Peez does not
screen sales before testing them — there is no rebalancing, tax-timing,
or liquidation exclusion anywhere in its sample construction; the raw
sell side is tested as disclosed. Peez's own discussion section
acknowledges this directly, naming sector composition, crisis-period
concentration, and active-trader concentration as competing explanations
it "cannot remove completely," addressed only by splitting the sample
after the fact (sub-periods, trader-frequency quartiles) rather than by
excluding the confounded transactions before the primary test — precisely
the gap this paper's four-screen funnel is built to close, and precisely
why a raw, unscreened sell-side finding needs the screened comparison
this paper reports alongside it. Second, Peez's own robustness checks are
run against the aggregate jurisdictional-sell alpha, not the sell spread
that is the paper's actual claimed result — an honest limitation Peez
states outright ("they do not by themselves constitute a full robustness
test of the incremental jurisdiction effect"), and one this paper avoids
structurally, since its own primary test (β1 in Model 2) is already a
within-model contrast, not a difference of two separately-run portfolios.

Peez's trading-frequency split (top-quartile vs. bottom-quartile members
by raw lifetime trade count, adapted from Barber and Odean's proxy for
deliberate active management) tests a different mechanism than this
paper's H3: it asks whether informed trading requires high overall
activity, not whether a specific trade breaks a member's own predictable
pattern. The two are not competing tests of the same claim. Peez also
states only two ex ante hypotheses — the jurisdictional sell effect and
House-versus-Senate heterogeneity — with the party and frequency splits
explicitly framed as exploratory; nothing in the paper describes a
pre-registration. On both counts this paper's scope is broader: four
pre-registered hypotheses including the purchase-side asymmetry Peez does
not formally test, and every screen, model, and output fixed before any
result existed.

Finally, H3 — the split between opportunistic and routine traders — is not
new to congressional trading; it is imported from the corporate
insider-trading literature. **Cohen, Malloy, and Pomorski (2012)**, using
SEC Form 4 filings, showed that more than half of all corporate insider
trades follow a predictable, recurring personal pattern — "routine"
trades — whose abnormal returns are statistically indistinguishable from
zero. Removing routine trades isolates "opportunistic" trades that carry
essentially all of the insider-trading universe's predictive power, with
the most informative opportunistic traders concentrated among local,
non-executive insiders at geographically concentrated, poorly governed
firms. Screen 4 — a member is classified as routine if they traded the
same security in the same calendar month in each of the three prior
years — transplants this classification directly onto congressional
insiders, and H3 restates the same prediction in the new setting: an
information-driven sale effect should be concentrated among opportunistic
sellers and absent among routine ones.

**Where this paper sits.** No paper in this set does all of the following
at once: treats the sale side as the primary object of study rather than
a residual comparison to purchases; builds and defends a sequential
screening funnel that removes rebalancing, tax-loss harvesting, and
liquidation-driven sales before testing for an information effect;
reports both the unscreened and screened samples so the gap between them
counts as evidence; and pre-registers every hypothesis, screen, model, and
output before running anything against real data. Ziobrowski et al. and
Peez find sale- or jurisdiction-side signal without this paper's screening
step; Eggers and Hainmueller and Chen and Sacerdote find no aggregate
signal without asking whether a screened subsample would look different;
Pyun and Cohen, Malloy, and Pomorski supply, respectively, the
disclosure-timing and routine/opportunistic machinery this paper adapts to
the sale side. The gap those four leave — a pre-registered, sale-focused,
fully screened test of informed selling in Congress — is this paper's
contribution. Peez, appearing five weeks before this study's own
pre-registration, is independent convergence on the same underlying
question, not a scoop: an unscreened design finding a real short-horizon
sell-side signal, on the same vendor's data this study also uses, is
exactly the result that makes a screened test of the same question worth
running rather than redundant with it.

---

## 3. Institutional Background: The STOCK Act

The Stop Trading on Congressional Knowledge Act ("STOCK Act") became law
in April 2012. Before it, members of Congress already filed annual
financial disclosures, but nothing required prompt, transaction-level
public disclosure — a sale in January might not surface publicly until
the following year's annual filing. The Act's central mechanical change
was the Periodic Transaction Report (PTR): covered individuals, including
members of Congress and their spouses and dependent children, must report
a covered transaction within 30 days of being notified of it and no later
than 45 days after the transaction itself. Covered transactions are
purchases, sales, and exchanges of stocks, bonds, commodity futures, and
other securities above $1,000 in value; mutual funds and other widely held
vehicles are exempt from the accelerated PTR requirement, though not from
annual disclosure.

Three features of this design carry directly into this paper's
construction. First, the $1,000 threshold in Section 5's inclusion rule is
not an analytical choice but the statute's own reporting floor — anything
below it is never disclosed at all, so there is no filtering decision on
this study's part below that line. Second, the requirement's reach to
spouses and dependent children is why Section 5 does not implement a
separate filer-relationship screen: every disclosed PTR transaction
already covers all three relationships by legal definition, so there is no
narrower "member-only" population to construct. Third, and most
consequentially for this paper's design, the up-to-45-day gap between a
transaction and its disclosure is the fact the primary specification and
one robustness check are both built around. A transaction is knowable to
the member on the transaction date; it becomes knowable to anyone else,
and therefore actionable by anyone else, only on the report date. Testing
from the transaction date asks whether a member had foreknowledge; testing
from the report date asks whether the disclosure itself was actionable.
Pyun (2025, above) is the closest existing evidence on how much this
distinction matters in practice; this paper's primary/robustness split
produces an independent estimate of the same gap on the screened sale
side specifically.

---

## 4. Data

This study draws on six sources.

| Source | Role |
|---|---|
| Quiver Quantitative API | Primary source for disclosed congressional transactions — ticker, transaction type, transaction date, report date, disclosed amount range, filer |
| Tiingo | Daily equity end-of-day prices, split- and dividend-adjusted |
| Ken French Data Library | Daily Fama-French three-factor and momentum data, for risk adjustment and the 12-industry classification |
| `unitedstates/congress-legislators` (public domain) | Member term histories and current-only committee assignments |
| Stewart and Woon, *Congressional Committee Assignments* (MIT, public domain) | Session-level committee rosters, for a true as-of-transaction-date committee lookup where it is available |
| SEC EDGAR | Ticker-to-SIC-code resolution, feeding the Fama-French industry classification |

**A recorded deviation from the original data plan.** The plan specified
pulling primary PTR filings directly from the House Clerk's and Senate's
own disclosure portals, using Quiver only as a cross-check. That was not
implemented. Both primary portals restrict bulk use of their data to
non-commercial, research, or news purposes under federal statute, and the
decision — made before any code was written — was to treat Quiver, a paid
aggregator already in use elsewhere in this research program, as the
primary trade-level source, reserving the primary portals for a small,
manually triggered verification pull supporting the hand-check described
in Section 6.3.

**Ticker universe.** The universe of securities considered is
disclosure-defined, not index-defined: every ticker named in at least one
congressional disclosure filed within the sample period was included,
discovered through Quiver's bulk congressional-trading endpoint rather
than assumed from S&P 500 or Russell 3000 membership. This was decided,
and verified against a live pull of the endpoint, to avoid compounding the
survivorship problem described below at the sample-construction stage as
well as the price-data stage — an index-defined universe would silently
drop exactly the companies most likely to have been delisted, acquired at
a discount, or gone bankrupt, for the same reason their price histories
disappear from the return data.

**Committee history.** H4 depends on knowing which committee a member sat
on *at the time of a given transaction*, not just today. The
`congress-legislators` project, this study's primary committee source,
only publishes a current snapshot. Where possible, this study instead
looks up a member's true committee assignment as of the transaction date
from Charles Stewart III and Jonathan Woon's *Congressional Committee
Assignments* dataset, resolved to each member through an identifier
crosswalk built from the same legislator records already in use. That
source's free coverage ends with the 115th Congress (2019-01-03); for any
transaction after that date, the current-only snapshot is used instead,
exactly as it was before this addition. This is a genuine improvement with
a real, permanent boundary, not a complete fix, and both regimes are
disclosed rather than blended silently — see Limitations.

**Known deviation, recorded before analysis: survivorship bias in price
data.** No delisting-inclusive price source is in use as of this draft.
The daily price feed drops a security once it is delisted, acquired, or
ceases trading, rather than carrying a delisting return for it (the
academic convention, following Shumway 1997 and its refinement in Shumway
and Warther 1999, imputes a return — conventionally −30% to −55%
depending on exchange and delisting reason — for the final period a
delisting security is held). This is a materially more serious limitation
for this study than for most: H1 predicts informed sales precede negative
subsequent returns, and the single strongest instance of that
prediction — a member selling ahead of a bankruptcy, a forced merger, or a
delisting for cause — is exactly the transaction most likely to have its
outcome deleted from a survivorship-biased feed rather than measured by
it. Beaver, McNichols, and Price (2007) show this kind of omission is not
random noise: delisting firm-years cluster disproportionately in the
extreme decile of exactly the kind of variable this paper sorts on, which
biases measured effect sizes systematically rather than merely adding
variance to them. Resolving this — most plausibly through CRSP
delisting-inclusive returns via an institutional affiliation — is a
precondition for the full-scale run this paper reports on, not a caveat
added after the fact.

---

## 5. Sample Construction

The sample period runs from January 1, 2014 through the most recently
completed calendar year at the time of the full-scale run, with the final
18 months held out entirely as an untouched validation sample, evaluated
once, after every other result in this paper is final.

A transaction was included if it met all of the following: it was a
common-stock transaction under Quiver's own instrument classification,
excluding options, bonds, mutual funds, ETFs, and municipal securities; it
was a directional purchase or sale, excluding exchanges and transfers —
because the underlying disclosure data records sales under several literal
strings rather than one canonical label, any value denoting a sale was
normalized to a single category before this filter, so a partial-sale
disclosure is not misclassified as non-directional and no exchange or
transfer reaches the analysis miscoded as a purchase by omission; the
disclosed amount exceeded the $1,000 statutory threshold; the security had
at least 60 trading days of price history before the transaction and a
full forward window of price history after it, sufficient to compute every
outcome variable at every horizon; and the filing was not a duplicate of
an already-counted disclosure, deduplicated on the combination of member,
ticker, transaction date, and disclosed amount band. Every step in this
funnel is logged with an exact count entering and surviving it — this log
is Table 1.

**The screening funnel is this paper's central methodological
contribution.** A raw finding that sales predict negative returns would
not, by itself, mean much, because sales are confounded by ordinary
portfolio activity that has nothing to do with information. Four
sequential screens were applied to the included sample, each removing a
named category of non-informational sale, with the count surviving each
screen reported alongside the count entering it.

1. **Rebalancing.** A sale was excluded if the same member purchased the
   same security within 90 days before or after it, or if the sale
   occurred on a date on which the same member disclosed three or more
   simultaneous sales of distinct securities.
2. **Tax management.** A sale in November or December was excluded if the
   position showed a loss relative to the member's most recent prior
   purchase of that security — the canonical signature of tax-loss
   harvesting rather than an information-driven exit.
3. **Liquidation events.** Transactions were excluded within a window
   around a member's apparent departure from Congress, approximated from
   the most recent known end of their term where no subsequent term
   exists in the data, and — reported two ways, as of Addendum B — around
   any date on which a member's cumulative *disclosed* net exposure
   indicates a sale exceeding 60% of it. That second sub-condition is
   built entirely from this study's own disclosed transaction data and
   has no visibility into a member's true, pre-existing holdings; it can
   structurally never fire for a member whose disclosed history never
   shows positive cumulative exposure, regardless of the true size of a
   later sale. Rather than resolve this by applying it or not, the
   screened sample is reported under both specifications, matching the
   same "the gap is itself informative" logic already applied to the
   unscreened-versus-screened comparison one level up. Two liquidation
   triggers in the original plan — blind trust establishment and
   confirmation to an executive-branch position — have no available
   structured data source and are not implemented; this is a stated scope
   limitation, not a silent gap.
4. **Routine traders.** Following the routine-versus-opportunistic
   classification introduced for corporate insiders by Cohen, Malloy, and
   Pomorski (2012), a member was classified as routine if they traded the
   same security in the same calendar month in each of the three prior
   years; routine and opportunistic traders were analyzed separately as
   the direct test of H3.

Results are reported on the unscreened and screened samples at every
stage of this paper. The gap between them is evidence in its own right,
not a number discarded once the screened result is available.

---

## 6. Methodology

### 6.1 Outcome Variables

The primary outcome is cumulative abnormal return (CAR) over three
post-transaction windows — [+1, +30], [+1, +90], and [+1, +180] trading
days — measured from the transaction date for the primary specification
and, separately, from the report date as the actionability robustness
check described in Section 3. Abnormal return was computed three
independent ways, all three reported at every horizon: market-adjusted
(return net of a market benchmark over the same window); four-factor
adjusted (using Fama-French three-factor-plus-momentum coefficients
estimated over the [-250, -30] trading-day window before the transaction);
and size- and industry-matched against a control portfolio matched on
trailing dollar-volume decile and Fama-French 12-industry classification,
drawn from this study's own sample universe rather than the broader
market. Buy-and-hold abnormal return (BHAR) was computed at the same
horizons and by the same three methods, as a secondary check on CAR's
known sensitivity to compounding order. For sales, the informed-trading
prediction is a negative abnormal return; for purchases, positive. H2
compares the absolute magnitude of the two, not their sign.

### 6.2 Empirical Specification

Three models were pre-specified, with a single primary test fixed before
any result existed.

**Model 1 — unconditional means.** Mean CAR for screened sales and,
separately, for purchases, at each horizon and by each method, with
standard errors clustered at the member level and, separately, at the
calendar-month level, both reported.

**Model 2 — pooled fixed-effects regression, the primary specification:**

```
CAR_i = β0 + β1·Sale_i + β2·Opportunistic_i + β3·(Sale × Opportunistic)_i
        + β4·CommitteeMatch_i + β5·(Sale × CommitteeMatch)_i
        + γ·Controls_i + MemberFE + YearFE + IndustryFE + ε_i
```

β1, at the 90-day horizon, four-factor-adjusted CAR, on the screened
sample, is this paper's single pre-registered primary test — it bears on
H1 directly and, relative to the corresponding purchase-side coefficient,
on H2. β3 tests H3; β5 tests H4. Standard errors are clustered at the
member level. Controls are trailing log dollar-volume (in place of log
market capitalization, for lack of a shares-outstanding source), prior
12-month return, transaction size band, and seniority in terms served;
book-to-market was specified in the original plan but is omitted here for
lack of an available source. Chamber and party are listed as controls in
the original specification but are not separately identified once member
fixed effects are included — both are constant within a member over the
sample window, so each is mechanically absorbed by the member effect, a
direct consequence of including MemberFE as specified rather than a
deviation from it.

**Model 3 — calendar-time portfolio.** A monthly calendar-time portfolio
of shorted screened-sale names, held for a period approximated at three
calendar months, regressed on the four factors; the intercept is the
reported quantity. This addresses cross-sectional dependence across
overlapping event windows, which the CAR-based models handle poorly by
design, and it necessarily anchors on the report date rather than the
transaction date — a position cannot be shorted before its sale is
publicly disclosed.

### 6.3 Statistical Discipline

The pre-specified primary test is β1 in Model 2 at the 90-day horizon,
four-factor adjusted, on the screened sample; every other result is
secondary to it. Three horizons, three adjustment methods, and two
samples produce 18 variants of the main test; a Benjamini-Hochberg
correction is applied across all 18, and the corrected significance
threshold is reported wherever a result from this grid is discussed. For
each reported result, a random-control test resamples the same number of
transactions on random dates within the sample period, 1,000 times,
reporting where the actual result falls in that simulated distribution —
the single most persuasive robustness check available given the design.

Twenty transactions from the final sample will be hand-verified against
the primary disclosure portals as an independent check on the pipeline,
separate from and in addition to the statistical checks above.

No specification is added after seeing results. Any analysis conducted
after this point that was not pre-specified is reported explicitly as
post-hoc exploratory work, kept separate from the primary findings.

### 6.4 Robustness

Ten checks were pre-specified against the primary specification, each
reported regardless of outcome: excluding the 5 and 10 most active
traders; year-by-year effects, to test whether any result is general or
concentrated in 2020–2021 — estimated with the member and industry
effects intact and the year effect dropped only where a single-year
subset makes it structurally constant, not as a change of specification;
splitting by transaction size band; excluding the 10 most-traded tickers;
excluding technology-sector transactions; re-anchoring entry at the report
date rather than the transaction date; winsorizing returns at the 1st and
99th percentiles; restricting to members serving three or more terms; a
Senate-versus-House split; and, run last and exactly once, the 18-month
holdout sample untouched by every result above it.

---

## 7. Results

*Pending. Waits on resolution of the delisting-data question and the
full-universe run. No number in this section exists yet.*

## 8. Discussion

*Pending — depends on Section 7.*

## 9. Conclusion

*Pending — depends on Sections 7–8.*

---

## Limitations

- **Survivorship bias.** No delisting-inclusive price source is in use as
  of this draft; this is the paper's most consequential open limitation
  and is being actively addressed, not merely disclosed.
- **Screen 3's cumulative-exposure sub-condition** is reported both
  applied and omitted (Addendum B), because it is built from disclosed
  transaction data with no visibility into a member's true pre-existing
  portfolio. Two liquidation triggers in the original design — blind
  trust establishment and executive-branch confirmation — have no
  available structured data source and are not implemented.
- **Committee history is hybrid, not uniform.** True session-level
  committee assignment is used for transactions before 2019-01-03; a
  current-only snapshot is used after that date, because no free
  session-level source covering it was found. H4's committee-match
  variable is therefore more accurate for the earlier part of the sample
  period than the later part.
- **Size and industry matching** use trailing dollar volume as a proxy for
  market capitalization, matched within this study's own sample universe
  rather than the full market, for lack of a shares-outstanding source.
- **Book-to-market is omitted** from Model 2's controls for lack of an
  available source.
- **The 90-day Model 3 holding period is approximated as three calendar
  months**, the standard convention in this literature, not an exact
  trading-day count, and its standard errors are not Newey-West adjusted —
  with overlapping monthly holding-period composition this can understate
  the true standard error, though the point estimate itself is unaffected.
- **All trade-level data is sourced from Quiver Quantitative**, not pulled
  directly from the House Clerk or Senate disclosure systems; a small,
  non-bulk manual cross-check against the primary portals is part of this
  paper's verification protocol, not a substitute for full independent
  sourcing.
- **Every match in this study keys on the ticker symbol**, not a
  permanent security identifier; a ticker-reuse audit detects, but does
  not correct for, a CIK mapping to more than one historical symbol.
- **The random-control permutation test resamples a capped subset of
  transactions**, not the full screened-sale set, for tractability — a
  permanent, documented deviation rather than an open item.
- **Buy-and-hold abnormal return (BHAR)** is computed at every horizon and
  by every method as specified, but is not separately tabulated beyond
  its role as a cross-check on CAR.

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

Peez, L. (2026). Informed Trading in the U.S. Congress: The Impact of
Committee Jurisdiction on Sell-Side Information Asymmetry. Esade Business
School & OTH Regensburg working paper, SSRN, July 2026.

Pyun, C. (2025). Congressional Trading, Informational Advantages, and
Disclosure Timing. Working paper, SSRN.

Shumway, T. (1997). The Delisting Bias in CRSP Data. *Journal of
Finance*, 52(1), 327–340.

Shumway, T., and Warther, V. A. (1999). The Delisting Bias in CRSP's
Nasdaq Data and Its Implications for the Size Effect. *Journal of
Finance*, 54(6), 2361–2379.

Stewart, C. III, and Woon, J. Congressional Committee Assignments,
103rd–115th Congresses, 1993–2019. Massachusetts Institute of Technology.

Ziobrowski, A. J., Cheng, P., Boyd, J. W., and Ziobrowski, B. J. (2004).
Abnormal Returns from the Common Stock Investments of the United States
Senate. *Journal of Financial and Quantitative Analysis*, 39(4), 661–676.

Ziobrowski, A. J., Boyd, J. W., Cheng, P., and Ziobrowski, B. J. (2011).
Abnormal Returns from the Common Stock Investments of Members of the
U.S. House of Representatives. *Business and Politics*, 13(1).
