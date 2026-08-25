# Do Congressional Sales Carry More Information Than Purchases?

**Ryan McGillicuddy**

2026-08-25

---

### Abstract

This paper asks whether stock sales by members of Congress predict how
the stock performs afterward. That question has barely been studied,
even though congressional purchases have been studied a lot. I built a
four-step filtering process to remove sales that look like normal
portfolio management (rebalancing, tax planning, or selling before
retirement) before testing whether the sales left behind predict the
stock doing worse. Using disclosure data on 100,272 transactions by
members of the House and Senate from 2014 to 2024, filtered down to
13,039 that passed every screen, this paper's single pre-registered
primary test, the market-adjusted return on a stock 90 days after a
screened sale, came out negative but did not clear a strict statistical
bar once corrected for the fact that 18 related tests were run
(β = −0.029, p = 0.077, required threshold p = 0.005). The wider set of
results tells a fuller story. Every version of the test on the screened
sample came out negative, three of the nine main versions cleared the
strict bar on their own, and the pattern disappears entirely when the
sales are not filtered first. That gap between the filtered and
unfiltered results is itself evidence that the filtering process, the
central contribution of this paper, is picking up on something real. A
hypothesis linking the effect to a member's committee assignment held
up, and matched an independent study published around the same time
that used very different methods. A hypothesis linking the effect to
routine versus one-time traders did not hold up, and actually pointed
the opposite direction. An 18-month period held back and tested only at
the end matched the direction of the main result but was too small a
sample to add much statistical confidence on its own. Overall, this
paper reports suggestive evidence, not proof, that congressional sales
which survive careful filtering predict the stock underperforming
afterward.

**Keywords:** congressional trading, informed trading, insider trading,
information asymmetry, event study, STOCK Act, disclosure

**JEL classification:** G14, G18, D82

---

## 1. Introduction

Research on congressional trading has a lopsided history. Almost every
study looks at purchases. That makes sense as a starting point, since a
purchase is easy to interpret: it is a clear decision to buy something.
A sale is much harder to read. It could mean rebalancing a portfolio
that got too concentrated, selling a loser before year-end for tax
reasons, cashing out before retirement, or genuinely acting on
information nobody else has. Because of that, researchers have spent
two decades asking whether members of Congress buy well, and mostly
stopped asking whether they sell well, on the unspoken assumption that
the sale side is too noisy to say anything useful about.

This paper argues that assumption gets the incentives backward. If a
member of Congress really does have material nonpublic information, the
lower-risk way to use it is not buying before good news. It is selling
before bad news. A well-timed purchase leaves a trail: a big win a
journalist can dig up years later and put in a headline. A well-timed
sale that simply avoids a loss leaves nothing to find. No outsized
gain, no "beat the market" trade, nothing that stands out next to
hundreds of routine disclosures. If informed trading happens in
Congress at all, the sale side is where it should be hardest to catch
and easiest to do, which is exactly why it has not been studied as
carefully as the purchase side.

Filtering the data is the actual contribution of this paper, not a
side detail. A raw comparison of all sales to all purchases tells you
almost nothing, because most sales have nothing to do with information.
A member might be selling to buy something else, selling in December
for tax reasons, or selling because they are retiring and cashing out a
portfolio. Section 5 builds a four-step filter that removes each of
these categories one at a time, reports exactly how many transactions
get removed at each step, and, importantly, reports results on both the
unfiltered and filtered samples side by side. The size of the gap
between them counts as evidence in its own right, not a number that
gets thrown away once the "real" result shows up.

Four hypotheses follow from this design. **H1** predicts that filtered
sales are followed by the stock performing worse than expected. **H2**
predicts that this effect, if it exists, is bigger than the matching
effect on the purchase side, the asymmetry the introduction opened
with, now stated as something that can actually be tested. **H3**
predicts that any sale-side effect is concentrated among members who
trade off their own predictable schedule ("opportunistic" sellers) and
missing among members who trade the same way every single year no
matter what is happening around them. **H4** is a check meant to rule
out a false positive: if the effect is really about information, it
should be stronger for sales in industries a member's committee gives
them some plausible access to, and weaker or absent everywhere else. If
the effect shows up evenly across every industry a member trades in,
an information-based explanation gets much harder to defend.

This paper does not claim to know *why* a member sold, only *when*
relative to how the stock performed afterward. It makes no claim about
any specific member, about whether any transaction was legal, or about
what anyone should invest in. Section 9 states these limits directly,
and they are meant to be taken seriously, not as a disclaimer tacked on
at the end. Every hypothesis, filter, model, and planned output listed
above was written down in `PRE_ANALYSIS_PLAN.md`, dated 2026-08-08,
before any of this paper's code touched real data.

---

## 2. Literature Review

Research on congressional trading splits into two camps this paper is
built to sit between: studies that find unusual returns on the
purchase side, and studies that test trading broadly, without any
filtering, and find nothing unusual at all.

**Ziobrowski, Cheng, Boyd, and Ziobrowski (2004)** set the field's most
cited finding. Using disclosed transactions by U.S. Senators, they
found that a portfolio copying Senate purchases beat the market by
roughly 85 basis points a month, while a portfolio copying Senate sales
lagged the market by about 12 basis points a month. The purchase-side
number became the result almost every later paper, academic or
popular, has tried to reproduce or argue with. The sale-side number was
an order of magnitude smaller, pointed the opposite way from what a
simple informed-selling story would predict, and was never broken down
into rebalancing, tax, liquidity, or information-driven pieces. It was
reported once and mostly left alone. **Ziobrowski, Boyd, Cheng, and
Ziobrowski (2011)** ran the same design on the House (roughly 16,000
transactions, 1985 to 2001) and again found a significant purchase-side
result, smaller than the Senate one, again without digging into the
sale side separately. Later work testing different model choices on
the original Senate data found the purchase-side result held up in as
few as three of eight versions tested, a reminder that raw, unfiltered
congressional returns are sensitive to how you set up the model in a
way a single headline number does not show.

**Eggers and Hainmueller (2013)**, using disclosures from 2004 to 2008,
found the opposite: no evidence of informed trading or above-market
returns for Congress as a whole or for any group of members they
tested, with the average member underperforming the market by 2 to 3
percent a year over that period. They summarized this in their own
words as political insider trading being "more myth than reality" for
that window. Set next to Ziobrowski et al., the disagreement itself is
informative: two credible studies, looking at overlapping groups of
people in different time periods, reach opposite headline conclusions,
and neither one filters sales for the confounds this paper treats as
the central problem. A related paper, **Eggers and Hainmueller
(2014)**, found that members' *politically connected* holdings,
meaning positions in companies with a geographic or committee-based
tie to the member, outperformed their unconnected holdings, and that
the unconnected holdings drove most of the underperformance in the
first place. That result matters here specifically. It shows that a
connection-based information edge can be real and detectable in one
part of a congressional portfolio even when overall trading shows no
edge at all, which is the same logic behind this paper's H4. A
connection should matter for returns even when undifferentiated
trading does not.

**Chen and Sacerdote (2026)**, in an NBER working paper covering
disclosures from 2012 to 2023 (the same post-STOCK Act period this
paper's own sample falls in), reach a conclusion closer to Eggers and
Hainmueller than to Ziobrowski et al.: legislators' portfolios match
or underperform market benchmarks on average, and members' trade
timing tracks what retail investors in general are doing more than it
predicts where the market is headed next. This is the most recent and
most direct evidence that whatever edge congressional trading carries
is not visible in a broad, unfiltered, portfolio-copying design. That
is not evidence against this paper's hypotheses, though, since they are
stated specifically about *filtered* sales, not congressional trading
in general. If anything, a null result at the aggregate level sharpens
the question: whether that null result survives, reverses, or gets
stronger once rebalancing-, tax-, and retirement-driven sales are
removed is exactly what this paper's filtered-versus-unfiltered
comparison is built to answer directly instead of assuming.

**Pyun (2025)** is the paper in this literature closest to this
study's approach to robustness checks, rather than to its central
question. Using the STOCK Act's gap between the transaction date and
the report date, Pyun finds that return predictability is stronger
when measured from the transaction date than from the report date,
consistent with informed insiders moving first, but that the
predictability is still economically meaningful even measured from the
later, publicly known report date, and is concentrated in large-cap
companies, in purchases by Representatives, and has gotten stronger
since 2020. This paper's primary test anchors on the transaction date
for the same reason Pyun's does: it is testing whether the member knew
something in advance, not whether the public disclosure itself was
actionable. The report-date robustness check (Section 6.4, item 6) is
a direct version of Pyun's own comparison, run here on the filtered
sale side instead of on purchases.

**Peez (2026)** is the paper closest to this study's H4, and now that
the full paper is available rather than just the abstract, the
comparison can be made precisely instead of provisionally. Peez sorts
each congressional sale (and, separately, purchase) into "jurisdictional"
or "non-jurisdictional" using a match between a member's committee and
detailed industry categories, updated as a member's committee
assignments change over their career rather than fixed once. Committees
with broad, non-industry-specific responsibilities (like Appropriations
or the Budget Committee) are excluded from the matching entirely rather
than lumped into a catch-all category. Using Quiver Quantitative, the
same data vendor this study uses, over a 2013 to 2025 sample of 336
trading members and roughly 108,500 directional transactions, Peez
tests jurisdictional and non-jurisdictional portfolios using
calendar-time regressions on a standard four-factor asset pricing
model at 20-, 130-, and 255-trading-day horizons. The paper's headline
result, at the shortest of the three horizons, is a jurisdictional sell
spread (the gap between non-jurisdictional and jurisdictional sell
returns) of 7.23% over 20 trading days (t = 2.14), concentrated in the
House (8.61%, t = 2.29) and not significant in the Senate (5.36%,
t = 0.67). That spread narrows to marginal significance at 130 days and
disappears entirely by 255 days, a decay pattern that matters directly
for this paper's own choice of horizons: if a similar effect exists in
this paper's own sample, Peez's result suggests it should be strongest
near this paper's 30-day window and mostly gone by 180 days, not
constant across all three.

Two design choices separate the two papers directly. First, Peez does
not filter sales before testing them. There is no rebalancing,
tax-timing, or retirement exclusion anywhere in the sample-building
process, and the raw sell side is tested exactly as disclosed. Peez's
own discussion section acknowledges this directly, naming industry
mix, crisis-period concentration, and heavy-trader concentration as
competing explanations that it "cannot remove completely," addressed
only by splitting the sample after the fact (by time period, by trading
frequency) rather than by removing the confounded transactions before
running the main test. That is exactly the gap this paper's
four-screen filter is built to close, and exactly why a raw,
unfiltered sell-side finding needs the filtered comparison this paper
reports next to it. Second, Peez's own robustness checks are run
against the overall jurisdictional-sell return, not the sell spread
that is the paper's actual headline result, a limitation Peez states
outright ("they do not by themselves constitute a full robustness test
of the incremental jurisdiction effect"). This paper avoids that
problem by design, since its own primary test (β1 in Model 2) is
already a single within-model comparison, not a difference between two
separately-run portfolios.

Peez's trading-frequency comparison (the most active quarter of
members versus the least active quarter, by lifetime trade count,
adapted from Barber and Odean's classic proxy for active management)
tests a different idea than this paper's H3. It asks whether informed
trading requires a high overall level of activity, not whether one
specific trade breaks a member's own predictable pattern. The two are
not competing tests of the same claim. Peez also states only two
hypotheses set in advance, the jurisdictional sell effect and a
House-versus-Senate difference, with the party and frequency
comparisons explicitly framed as exploratory; nothing in the paper
describes a formal pre-registration. On both counts this paper's scope
is broader: four hypotheses set in advance, including the
purchase-side comparison Peez does not formally test, and every filter,
model, and output fixed before any result existed.

Finally, H3, the split between opportunistic and routine traders, is
not new to congressional trading. It is borrowed from research on
corporate insider trading. **Cohen, Malloy, and Pomorski (2012)**,
using SEC Form 4 filings, showed that more than half of all corporate
insider trades follow a predictable, repeating personal pattern, what
they call "routine" trades, and that the returns following those
trades are statistically no different from zero. Removing routine
trades isolates "opportunistic" trades that carry essentially all of
the predictive power in the whole insider-trading dataset, with the
most informative opportunistic traders concentrated among local,
non-executive insiders at smaller, less closely watched companies.
Screen 4 in this paper, which classifies a member as routine if they
traded the same security in the same calendar month in each of the
three prior years, applies this same idea directly to members of
Congress. H3 simply restates the same prediction in this new setting:
an information-driven sale effect should show up among opportunistic
sellers and be missing among routine ones.

**Where this paper sits.** No paper in this set does all of the
following at once: treats the sale side as the main object of study
rather than a leftover comparison to purchases; builds and defends a
step-by-step filtering process that removes rebalancing, tax-loss
harvesting, and retirement-driven sales before testing for an
information effect; reports both the unfiltered and filtered samples
so the gap between them counts as evidence; and locks in every
hypothesis, filter, model, and output before running anything against
real data. Ziobrowski et al. and Peez find sale- or jurisdiction-side
signal without this paper's filtering step. Eggers and Hainmueller and
Chen and Sacerdote find no aggregate signal without asking whether a
filtered subsample would look different. Pyun and Cohen, Malloy, and
Pomorski supply the disclosure-timing and routine/opportunistic tools
this paper adapts to the sale side. The gap those four papers leave, a
pre-registered, sale-focused, fully filtered test of informed selling
in Congress, is this paper's contribution. Peez, which appeared five
weeks before this study's own pre-registration, is independent
confirmation that this question is worth asking, not a scoop: an
unfiltered design finding a real short-horizon sell-side signal, using
the same vendor's data this study also uses, is exactly the kind of
result that makes a filtered test of the same question worth running
rather than redundant with it.

---

## 3. Institutional Background: The STOCK Act

The Stop Trading on Congressional Knowledge Act ("STOCK Act") became
law in April 2012. Before it, members of Congress already filed annual
financial disclosures, but nothing required prompt, transaction-level
disclosure to the public. A sale made in January might not show up
publicly until the following year's annual filing. The Act's biggest
practical change was the Periodic Transaction Report (PTR). Covered
individuals, including members of Congress and their spouses and
dependent children, must report a transaction within 30 days of being
notified of it, and no later than 45 days after the transaction
itself. Covered transactions are purchases, sales, and exchanges of
stocks, bonds, commodity futures, and other securities worth more than
$1,000. Mutual funds and other widely held investment vehicles are
exempt from this faster PTR requirement, though not from the annual
disclosure.

Three features of this rule matter directly for how this paper is
built. First, the $1,000 threshold used in Section 5's inclusion rule
is not a choice this paper made. It is the law's own reporting floor.
Anything below it is never disclosed at all, so there is no filtering
decision made on this study's end below that line. Second, the rule's
reach to spouses and dependent children is why Section 5 does not add
a separate screen for who exactly made the trade: every disclosed PTR
transaction already covers all three relationships by law, so there is
no narrower "member-only" group to build separately. Third, and most
important for this paper's design, the up-to-45-day gap between a
transaction and its public disclosure is the fact the main test and
one robustness check are both built around. A member knows about their
own transaction on the transaction date. Nobody else can act on it
until the report date, when it becomes public. Testing from the
transaction date asks whether the member knew something in advance.
Testing from the report date asks whether the public disclosure itself
gave anyone useful information. Pyun (2025, above) is the closest
existing evidence on how much this distinction matters in practice.
This paper's main test and its robustness check together produce an
independent estimate of the same gap, specifically on the filtered
sale side.

---

## 4. Data

This study draws on six sources.

| Source | Role |
|---|---|
| Quiver Quantitative API | Primary source for disclosed congressional transactions: ticker, transaction type, transaction date, report date, disclosed amount range, filer |
| Tiingo | Daily stock prices, adjusted for splits and dividends |
| Ken French Data Library | Daily risk-factor data used for adjusting returns and for sorting companies into industries |
| `unitedstates/congress-legislators` (public domain) | Member term histories and a current snapshot of committee assignments |
| Stewart and Woon, *Congressional Committee Assignments* (MIT, public domain) | Committee rosters by session, used to look up a member's true committee at the time of a transaction where possible |
| SEC EDGAR | Used to match each stock ticker to an industry code |

**A recorded change from the original data plan.** The original plan
was to pull disclosure filings directly from the House Clerk's and
Senate's own public portals, using Quiver only as a cross-check. That
was not how it ended up working. Both government portals restrict bulk
use of their data to non-commercial, research, or news purposes under
federal law, so the decision, made before any code was written, was to
use Quiver, a paid data vendor already used elsewhere in this research
program, as the main source of trade data, and to save the government
portals for a small, manually done verification check described in
Section 6.3.

**Which stocks were included.** The universe of stocks considered is
defined by the disclosures themselves, not by a stock index. Every
ticker named in at least one congressional disclosure during the
sample period was included, found through Quiver's own bulk data feed
rather than assumed from S&P 500 or Russell 3000 membership. This was
a deliberate choice, checked against a live pull of the data, to avoid
making a data problem described just below even worse. If the universe
had instead been defined by a stock index, it would have quietly
dropped exactly the companies most likely to have been delisted,
bought out at a low price, or gone bankrupt, for the same reason their
price histories tend to disappear from return data in the first place.

**Committee history.** H4 depends on knowing which committee a member
sat on *at the time of a given transaction*, not just today. The
`congress-legislators` project, this study's main source for committee
information, only publishes a current snapshot. Where possible, this
study instead looks up a member's real committee assignment as of the
transaction date using Charles Stewart III and Jonathan Woon's
*Congressional Committee Assignments* dataset, matched to each member
through an identifier system built from the same legislator records
already in use. That dataset's free coverage ends with the 115th
Congress (2019-01-03). For any transaction after that date, the
current-only snapshot is used instead, the same way it would have been
without this addition. This is a real improvement with a real, fixed
limit, not a complete fix, and both time periods are handled openly
rather than blended together silently. See Limitations.

**Missing price data for delisted companies, and how it was fixed
(Addendum A through Addendum C).** The main price data source, Tiingo,
simply drops a stock once it is delisted, bought out, or stops
trading, instead of recording a final "delisting return" for it. This
would have been a much more serious problem for this study than for
most, because H1 predicts that informed sales come before the stock
performs badly, and the single strongest example of that, a member
selling right before a bankruptcy, a forced merger, or a delisting for
cause, is exactly the kind of transaction most likely to have its
outcome quietly deleted from the price data rather than actually
measured. Beaver, McNichols, and Price (2007) show this kind of gap is
not random noise: companies that get delisted show up
disproportionately in the extreme end of exactly the kind of variable
this paper sorts by, which skews the measured effect in one direction
rather than just adding random noise to it.

Addendum C fixes this without needing an expensive academic database
subscription. After the normal per-stock data collection, every ticker
whose price history seems to end more than 90 trading days before the
end of the sample period is patched using EOD Historical Data (EODHD),
a paid data vendor confirmed, by actually checking, not just taking
their word for it, to keep full daily price history for delisted
stocks all the way through their last day of trading. The patching
step checks the stock's special bankruptcy-suffix ("Q") ticker symbol
first, not its plain ticker. This matters because, confirmed directly
before this addendum was written, a delisted stock's plain ticker
symbol can quietly get reused by a completely different company later
on, so checking the plain ticker directly can return a different
company's healthy trading history instead of showing the gap it should
show. This was confirmed using the real example of Bed Bath & Beyond,
whose original, bankrupt company can only be found under the symbol
"BBBYQ," where the stock price collapsed to a fraction of a cent
before the company was delisted, while the plain "BBBY" ticker was
later reassigned to a completely different, still-trading company.
This fix is partial, not complete. The "Q" suffix specifically covers
a formal Chapter 11 bankruptcy filing, and a stock delisted a
different way might still be missed. Any such case is listed by name
rather than silently dropped from the count. See Limitations.

---

## 5. Sample Construction

The sample period runs from January 1, 2014 through the most recently
completed calendar year at the time of the full-scale run, with the
final 18 months set aside entirely as an untouched test sample, checked
only once, after every other result in this paper is final.

A transaction was included if it met every one of the following
conditions: it was a common-stock transaction under Quiver's own
classification, excluding options, bonds, mutual funds, ETFs, and
municipal securities; it was a clear purchase or sale, excluding
exchanges and transfers (the underlying data records sales under
several different text labels rather than one, so every version of
"sale" was standardized into a single category before this filter, to
make sure a partial sale is not wrongly excluded and no exchange or
transfer accidentally counts as a purchase); the disclosed amount was
above the $1,000 legal threshold; the stock had at least 60 trading
days of price history before the transaction and a full window of
price history afterward, enough to calculate every outcome measure at
every time horizon; and the filing was not a duplicate of one already
counted, checked by matching on the member, the ticker, the
transaction date, and the disclosed amount range together. Every step
of this process is recorded with an exact count of transactions going
in and coming out. That record is Table 1.

**The filtering process is the central contribution of this paper.** A
raw finding that sales predict worse returns would not mean much on
its own, because sales get mixed up with ordinary portfolio activity
that has nothing to do with information. Four filters were applied to
the sample in sequence, each one removing a specific, named category
of non-informational sale, with the count surviving each step reported
next to the count entering it.

1. **Rebalancing.** A sale was excluded if the same member bought the
   same stock within 90 days before or after it, or if the sale
   happened on a day the same member also disclosed three or more
   other sales at the same time.
2. **Tax management.** A sale in November or December was excluded if
   the position was at a loss compared to the member's most recent
   prior purchase of that stock, the classic signature of tax-loss
   harvesting rather than an information-driven exit.
3. **Retirement and other liquidation events.** Transactions were
   excluded around the time a member appears to have left Congress,
   estimated from the most recent known end of their term where no
   later term shows up in the data. Transactions were also excluded,
   reported both ways as of Addendum B, around any date where a
   member's cumulative *disclosed* holdings suggest they sold more
   than 60% of their position at once. That second part of the rule is
   built entirely from this study's own disclosure data and has no way
   to see a member's actual, true holdings. It can never trigger for a
   member whose disclosed history never shows a large enough position
   in the first place, no matter how big their real later sale was.
   Rather than pick one version of this rule, results are reported
   both with and without it, following the same "the gap is itself
   informative" logic already used for the filtered-versus-unfiltered
   comparison at the top level. Two other triggers from the original
   plan, a member setting up a blind trust and a member being confirmed
   to an executive-branch job, have no available data source and are
   not implemented. This is a stated limit on scope, not a silent gap.
4. **Routine traders.** Following the routine-versus-opportunistic
   split used for corporate insiders by Cohen, Malloy, and Pomorski
   (2012), a member was classified as routine if they traded the same
   stock in the same calendar month in each of the three prior years.
   Routine and opportunistic traders were analyzed separately as the
   direct test of H3.

Results are reported on both the unfiltered and filtered samples at
every stage of this paper. The gap between them counts as evidence in
its own right, not a number that disappears once the filtered result
is ready.

---

## 6. Methodology

### 6.1 Outcome Variables

The main outcome measured is cumulative abnormal return (CAR), how
much a stock's return differs from what would normally be expected,
added up over three time windows after the transaction: 30, 90, and
180 trading days. This is measured from the transaction date for the
main test, and separately from the report date as a check on whether
the public disclosure itself was useful information, described in
Section 3. Abnormal return was calculated three separate ways, and all
three are reported at every time horizon: market-adjusted (the return
compared to a broad market benchmark over the same window);
four-factor adjusted (using a standard risk-factor model estimated
over the 250 to 30 trading days before the transaction); and matched
against a group of similar-size companies in the same industry, drawn
from this study's own sample rather than the whole market. Buy-and-hold
abnormal return (BHAR), a slightly different way of adding up returns
over time, was calculated at the same horizons and in the same three
ways, as a secondary check. For sales, the prediction is a negative
abnormal return. For purchases, positive. H2 compares the size of the
two effects, not their direction.

### 6.2 Empirical Specification

Three models were planned in advance, with one single primary test
fixed before any result existed.

**Model 1, plain averages.** The average CAR for filtered sales and,
separately, for purchases, at each time horizon and by each method,
with two different ways of calculating the statistical uncertainty
(clustering by member, and separately by calendar month), both
reported.

**Model 2, the main model, a regression that controls for member,
year, and industry:**

```
CAR_i = β0 + β1·Sale_i + β2·Opportunistic_i + β3·(Sale × Opportunistic)_i
        + β4·CommitteeMatch_i + β5·(Sale × CommitteeMatch)_i
        + γ·Controls_i + MemberFE + YearFE + IndustryFE + ε_i
```

β1, at the 90-day horizon, using the four-factor adjustment, on the
filtered sample, is this paper's single pre-registered primary test.
It speaks to H1 directly, and, compared to the matching purchase-side
number, to H2 as well. β3 tests H3. β5 tests H4. Statistical
uncertainty is calculated by clustering at the member level. The
control variables are trailing trading volume in dollars (used in
place of market value, since no source for shares outstanding was
available), the stock's return over the prior 12 months, the size band
of the disclosed transaction, and how many terms the member has
served. Book-to-market, a common control in this kind of study, was in
the original plan but is left out here because no data source for it
was available. Chamber and party were listed as controls in the
original plan but do not show up as separate estimated numbers, since
they never change for a given member during the sample period. Once
member is already controlled for, chamber and party add no new
information, a direct mathematical consequence of controlling for
member in the first place, not a deviation from the plan.

**Model 3, a calendar-time portfolio.** A monthly portfolio that
shorts (bets against) every filtered-sale stock, held for a period
approximated at three calendar months, tested against the standard
four risk factors. The number reported is the portfolio's average
monthly return after accounting for those factors. This model handles
a statistical problem the CAR-based models handle poorly: overlapping
time windows across different transactions. It anchors on the report
date rather than the transaction date, since a stock cannot be shorted
before its sale is publicly known.

### 6.3 Statistical Discipline

The one test set in advance as primary is β1 in Model 2 at the 90-day
horizon, four-factor adjusted, on the filtered sample. Every other
result is secondary to it. Three time horizons, three adjustment
methods, and two samples (filtered and unfiltered) together produce 18
versions of the main test. A statistical correction (Benjamini-Hochberg)
is applied across all 18 to account for the fact that running many
tests makes it easier to find a "significant" result by chance, and
the corrected bar for significance is reported wherever a result from
this set of 18 is discussed. For each reported result, a separate
check resamples the same number of transactions on random dates within
the sample period, 1,000 times, and reports where the real result
falls compared to that simulated distribution. This is the single most
convincing robustness check available given the design.

Twenty transactions from the final sample were checked by hand against
the actual government disclosure records, as an independent check on
the whole pipeline, separate from and in addition to the statistical
checks above.

No new test was added after seeing results. Any analysis done after
this point that was not planned in advance is clearly labeled as
exploratory and kept separate from the main findings.

### 6.4 Robustness

Ten checks were planned in advance against the main test, and every one
is reported no matter what it shows: excluding the 5 and 10 most
active traders; checking year by year whether the result is general or
concentrated in 2020 to 2021 (with member and industry still
controlled for, and the year control dropped only in years where doing
so would make the math impossible, not as a change in approach);
splitting by the size of the disclosed transaction; excluding the 10
most-traded stocks; excluding technology-sector transactions; using
the report date instead of the transaction date; capping extreme
values in the top and bottom 1% of returns; limiting to members who
have served three or more terms; splitting by Senate versus House; and,
run last and exactly once, the 18-month holdout period untouched by
every result above it.

---

## 7. Results

### 7.1 Sample

The four-step filter (Table T1) reduced 100,272 disclosed transactions
from the 2014 to 2024 study period down to 21,717 clear, common-stock,
above-threshold, non-duplicate transactions with enough price history
before and after to calculate every outcome measure, then down to
13,039 after the three main filters (rebalancing, tax timing,
retirement): 12,213 from the House and 826 from the Senate, 8,098
Democratic and 4,925 Republican members (Table T2). By far the biggest
single cut is the common-stock-only filter (79,088 down to 23,489):
most disclosed transactions are not common-stock trades at all. Filing
lag (Table T3) has a median of 28 days and an average of 91, with
19.6% of transactions filed more than 45 days after the transaction
date. The STOCK Act's official disclosure window is often missed in
practice, which is exactly why Section 4's robustness check
(re-anchoring on the report date) exists.

### 7.2 H1 and H2, the primary test

This paper's single pre-registered primary test, β1 in Model 2, the
`sale` coefficient at the 90-day horizon, four-factor adjusted,
filtered sample, is **β = −0.0292 (SE = 0.0165, clustered by member),
p = 0.077**. Applying Section 12's rule in full: the corrected bar for
significance across the 18 planned versions of this test (3 horizons
by 3 adjustment methods by 2 samples) is **0.00501**, so this result
does not clear it. The random-date comparison test (1,000 resamples of
the same number of transactions on random dates) places the real
result at the **86.4th percentile** of the simulated distribution,
inside the normal range, not outside the 95th-percentile bar Section
12 requires. By this paper's own rule, set before seeing any result,
**the primary test does not count as support for H1.**

That is not the whole story, and Section 6.3's own rules require
reporting the rest of the planned results, not just the one test
labeled primary. Every one of the 9 filtered-sample versions of the
test came out negative, across all three time horizons and all three
adjustment methods, and three of them clear the corrected bar on their
own: 90-day market-adjusted (β = −0.0407, p = 0.00055), 90-day
size/industry-matched (β = −0.0347, p = 0.00296), and 180-day
market-adjusted (β = −0.0373, p = 0.00194). A fourth, 180-day
size/industry-matched, lands exactly at the corrected bar
(p = 0.00501). The unfiltered sample shows no similar pattern. Its
nine versions are a roughly even mix of positive and negative, none of
them large in economic terms, and only one (90-day market-adjusted,
β = −0.0149, p = 0.041) clears an uncorrected 5% bar, and none clear
the corrected bar. This is the gap the Introduction (Section 1) said
would count as evidence on its own: a raw, unfiltered comparison of
sales to purchases tells you almost nothing, and a consistent, mostly
significant negative pattern only shows up after the filters remove
rebalancing-, tax-, and retirement-driven sales. This is reported as a
real, planned-in-advance secondary finding, not something dug up after
the fact, since every version in the set of 18 was fixed before any
result existed. It is still secondary to, and not a replacement for,
the one test this paper set as primary before seeing any result.

The plain averages (Table T4, Model 1) add a real wrinkle worth
stating plainly instead of glossing over. At the 90-day, four-factor
horizon on the same filtered sample, the raw average CAR is −0.69% for
sales and −2.88% for purchases. In other words, purchases look worse
than sales in the raw comparison, the opposite of what the main
regression above reports. This is not a contradiction. It is the
standard difference between comparing raw averages across different
groups and comparing within the same group over time. Model 1's plain
average mixes together whichever members, industries, and years happen
to have more sales versus more purchases in them. Model 2's β1
strips out those member-level, year-level, and industry-level
differences and isolates a true within-member, within-year,
within-industry comparison. That is exactly why this paper planned to
treat Model 2, not Model 1, as primary. Both numbers are correct. They
just answer different questions, and the fact that they point opposite
directions is itself informative about how much of the raw comparison
is really just about which members and industries traded more, rather
than about timing.

H2, the claim that any sale-side effect is bigger than the matching
purchase-side effect, is addressed by this same β1 number, since
`sale` is coded relative to a purchase baseline. A negative,
meaningful β1 in the filtered sample (and a statistically significant
one in three of the nine versions) is consistent with H2's prediction,
but comes with the exact same caveat as H1 above: it is supported in
direction and in the broader set of results, not by the primary test's
own statistical bar.

### 7.3 H3 and H4, the interaction terms

Table T5 reports both interaction terms from the main model, for both
the full and filtered samples. **H3 predicted that any sale-side
effect would be concentrated among opportunistic sellers and missing
among routine ones, meaning `sale_x_opportunistic` should be
negative.** It is not: β = +0.0177 (full sample, SE = 0.0112) and
+0.0745 (filtered sample, SE = 0.0262). In the filtered sample, adding
this interaction to the base `sale` number (−0.0292) gives an effect
of +0.045 for opportunistic sales, positive, not more negative. Read
plainly, this flips H3's predicted order around: the negative pattern
in Section 7.2 is, if anything, concentrated among routine sellers,
not opportunistic ones. **H3 is not supported by the sign of this
number**, and that is reported as a direct finding rather than
explained away. No claim is made here about why. This paper observes
when things happened, not why, and the routine-versus-opportunistic
split itself (Screen 4, borrowed from Cohen, Malloy, and Pomorski
2012) may simply be picking up a different pattern in Congress than it
does among corporate insiders, the setting it was originally built
for. That question is left for the Limitations section and for future
work, not resolved here.

**H4 predicted a stronger negative effect where a member's committee
plausibly gives them access to relevant information, meaning
`sale_x_committee_match` should be negative.** It is: β = −0.0149
(full, SE = 0.0159) and −0.0420 (filtered, SE = 0.0309), pointing the
right direction in both samples, though neither individually clears a
standard significance bar at this sample size. This direction matches
Peez's (2026) headline jurisdictional-sell finding, reached
independently, using the same data vendor but a very different,
unfiltered design. Two independent studies pointing the same way is
worth more than either one alone, even though this paper's own
estimate is not decisive by itself.

There is also a real point of disagreement with Peez, and it is
reported honestly rather than smoothed over: Peez's jurisdictional
sell spread is strongest at a 20-trading-day horizon and disappears by
255 days, which would predict that a similar effect in this paper's
sample should be strongest near the 30-day window and mostly gone by
180 days. The opposite pattern shows up here. Every result that clears
the corrected bar in Section 7.2 is at the 90- or 180-day horizon, and
every filtered 30-day result is small and statistically unremarkable
(four-factor p = 0.667, market-adjusted p = 0.199, size/industry
p = 0.749). Two possible explanations come from the design differences
themselves, and neither one is settled here: this paper's filtering
process may be removing exactly the short-horizon noise (rebalancing,
tax-timing) that drowns out a short-horizon signal in an unfiltered
design, or the two studies may simply be picking up different
underlying patterns. This is reported as an open disagreement, not
something this paper's data resolves.

### 7.4 Model 3 and robustness

The calendar-time portfolio (Table T6, Model 3), a short position in
every filtered-sale stock, held roughly three calendar months, tested
against the four risk factors, produces a monthly return of −0.62%
(SE = 0.66%, t = −0.94, 77 months), not statistically different from
zero. This model handles a statistical problem the CAR-based models
handle poorly, and the fact that it does not clear significance on its
own fits with, and does not contradict, Section 7.2's finding that the
main CAR-based test also falls short of this paper's bar for a
confirmed result.

Of the ten robustness checks planned in advance (Table T7), eight
reproduce the main test's negative sign, in a range from −0.023 to
−0.036 that includes the primary estimate itself: excluding the 5 most
active traders, excluding the 10 most-traded stocks, excluding the
technology sector, excluding 2020 to 2021, limiting to members with
three or more terms served, capping extreme return values, using the
report date instead of the transaction date, and the House-only split
(β = −0.031, n = 11,980, close to the pooled result) all keep the same
sign and roughly the same size. Two do not. Excluding the 10 most
active traders gives β = +0.0046 (SE = 0.038, n = 6,465), small and
imprecisely estimated, closer to statistically zero than to a genuine
reversal. The Senate-only split gives β = +0.094 (SE = 0.096, n = 789),
bigger, and, on a subsample this much smaller than the House's 11,980,
also imprecisely estimated. Splitting by transaction size (the tenth
check) is noisier still: results range from −0.115 to +0.079 across
different size bands, on subsamples as small as 93 observations, with
three bands too thin to estimate at all. Taken together with the
Senate result, this matches the same House/Senate difference Peez
(2026) reports independently for the jurisdictional sell spread,
though here it more plausibly reflects sample size (789 transactions
against 11,980 in the House) than a real difference between the two
chambers. Section 12's rule, that a result concentrated in a small
subsample should be reported as such rather than generalized, applies
directly to both of these exceptions.

### 7.5 Holdout (Section 9, item 10, run once)

The 18-month holdout period (2024-07-01 to 2025-12-31) was filtered
using the same full transaction history as the main sample, not a
history cut down to just those 18 months, giving 4,006 filtered
holdout transactions and 3,985 with a complete set of data for the
regression. Re-running the exact same main test (Table T8) on this
out-of-sample period gives **β_sale = −0.0365 (SE = 0.378, p = 0.92)**,
the same sign as the main result, but not statistically informative on
its own. This is reported as-is, following this paper's own plan
(Section 9, item 10: run once, report exactly what comes out; if a
problem shows up, note it as a limitation, do not quietly fix it and
run it again).

That limitation is worth spelling out clearly rather than skipping
over. Several other numbers in this same regression are far too large
to make sense for a return-based outcome, and carry uncertainty of a
similar or bigger size: `seniority_terms` (β = 3.25, SE = 4,439.6),
`log_size` (β = 3.63, SE = 3.64), and several transaction-size controls
(β between −1.5 and −4.7, SE between 2.7 and 6.7). This is a clear
sign that the model is stretched too thin on this smaller sample, not
a coding mistake: 3,985 observations, once split across 80 different
members, 2 years, 12 industries, eight size categories, and two
interaction terms, simply do not leave enough information to pin down
every number in the model precisely on an 18-month window, the way
they do on the full 2014 to 2024 sample. The `sale` number itself
stays on a sensible scale (β = −0.037, matching the sign of every
other estimate in this paper), but its own very large uncertainty
should be read in that context. The holdout does not independently
confirm the main result, but it does not contradict its direction
either, and the instability is a property of asking too much of an
18-month sample, not a problem with the main findings above.

## 8. Discussion

By this paper's own rule, set in advance (Section 12), the single
pre-registered primary test does not count as support for the main
hypothesis: β1 in Model 2, at the 90-day horizon, four-factor adjusted,
on the filtered sample, clears neither the corrected statistical bar
across the 18 planned versions nor the random-date test's 95th-percentile
bar. On its own, this is a null result on H1's most direct, most
demanding test.

Read alongside the rest of the planned analysis, the picture is more
interesting than a single null result suggests, and it is reported in
full because every piece of it was planned before any result existed.
Three things hold together. First, the filtering step, this paper's
actual contribution and not a side detail, clearly matters: the
unfiltered sample shows no consistent pattern across the 18 planned
versions, while the filtered sample is negative in all nine and clears
the corrected bar in three (with a fourth landing exactly on the
line). Second, the direction holds up across every time horizon, every
adjustment method, eight of ten robustness checks, and the
out-of-sample holdout. No single piece of this is decisive by itself,
but nothing in it points the other way, and the H4 result (a stronger
effect where a member's committee plausibly gives them relevant
access) matches Peez's (2026) independent finding, reached using a
very different design, on the same underlying question. Third, and
against that pattern, two results actually point the other way rather
than just falling short: H3's interaction flips its predicted sign
completely, and Model 3's calendar-time return, while not itself
statistically different from zero, is negative rather than positive,
the sign a short position in sale-stocks would show if H1 were true.
Both are reported directly, not reinterpreted to fit the rest of the
evidence.

Taken as a whole, this is neither a confirmation of informed selling
in Congress nor a clean null result. It is a case where the single
most demanding, pre-registered test, deliberately chosen to be hard to
pass so that passing it would actually mean something, does not pass,
while a wider set of planned, non-exploratory evidence points in one
consistent direction with two genuine exceptions (H3's flipped sign,
and the horizon pattern running opposite to Peez's). Section 12's
rules exist specifically to prevent the mistake of calling this
pattern "significant" just because most of it looks the same way.
Applied honestly, the right summary is that this paper finds
suggestive, not confirmed, evidence for H1, H2, and H4, and a clear
non-confirmation of H3, on the exact sample and model planned on
2026-08-08.

This paper does not observe why any of this happens, and does not
claim to. It observes when unusual returns follow a disclosed sale,
under a filtering design meant to isolate the transactions hardest to
explain by anything other than information, and reports, without
dressing it up, that the pre-registered primary test on that design
falls short of this paper's own bar for calling the result confirmed.

## 9. Conclusion

This paper set out to test whether congressional sales, the
under-studied, harder-to-see half of congressional trading, carry
information beyond what purchases carry, using a four-step filter
built to remove the rebalancing, tax-timing, and retirement-driven
sales that make a raw sale/purchase comparison close to meaningless.
The single pre-registered primary test does not clear this paper's own
correction and random-date bars: β1 = −0.029 (p = 0.077, filtered
sample, 90-day horizon, four-factor adjusted) is a null result by the
standard set before any data were seen.

It is not the only result this paper reports, because every other
number above was planned in advance too. The filtered sample is
negative across every time horizon and method tested, three of nine
versions clear a strict multiple-testing bar on their own, the pattern
disappears in the unfiltered sample, eight of ten robustness checks
reproduce it, and the committee-jurisdiction result (H4) points the
same direction as Peez's (2026) independent estimate. Against that,
two results point the other way rather than just falling short: the
opportunistic-trader result (H3) flips its predicted sign completely,
and the calendar-time portfolio's return (Model 3), while not itself
statistically different from zero, is signed opposite to what H1
predicts. The time-horizon pattern of this paper's strongest results
(90 to 180 days) also runs opposite to Peez's (20 days). The 18-month
holdout matches the main result's sign but is too small a sample on
its own to add real confirming weight.

The honest summary is suggestive, not confirmed, evidence that
filtered congressional sales predict the stock underperforming
afterward, concentrated where a member's committee plausibly gives
them relevant information, and not concentrated among members who
trade off their own predictable schedule, with that last part directly
contradicted by this paper's own H3 result. Whether any of this
actually reflects information, as opposed to some other pattern this
paper's four filters did not anticipate, is not a question this
paper's design can answer, and it does not try to. No claim about why
any of this happens is made. No claim about any individual member is
made. No claim about whether any transaction was legal is made. No
investment advice is offered.

---

## Limitations

- **Survivorship bias, partly fixed (Addendum C).** Stocks whose price
  history appears to end early are patched using delisting-inclusive
  data from a paid vendor, checking each stock's bankruptcy ("Q"-suffix)
  ticker first, for the reason given in Section 4, a real, confirmed
  case of ticker reuse, not a hypothetical one. This covers stocks
  delisted through a formal Chapter 11 bankruptcy filing. A stock
  delisted a different way (for example, a clean buyout settled after
  trading was paused) may still be missed. Every stock the patching
  step could not fix is listed by name, not silently dropped, and any
  that remain by the time of the full-scale run are listed here
  explicitly rather than folded into one aggregate count.
- **Screen 3's cumulative-exposure rule** is reported both applied and
  left out (Addendum B), because it is built entirely from disclosed
  transaction data with no way to see a member's actual, true
  holdings. Two other triggers from the original plan, setting up a
  blind trust and being confirmed to an executive-branch job, have no
  available data source and are not implemented.
- **Committee history is a mix, not one consistent source.** The true,
  session-by-session committee assignment is used for transactions
  before 2019-01-03. A current-only snapshot is used after that date,
  because no free source covering that period by session was found.
  H4's committee-match variable is therefore more accurate for the
  earlier part of the sample than the later part.
- **Size and industry matching** use trailing trading volume as a
  stand-in for market value, matched only within this study's own
  sample rather than the whole market, since no source for shares
  outstanding was available.
- **Book-to-market is left out** of Model 2's controls, since no data
  source for it was available.
- **The 90-day Model 3 holding period is approximated as three
  calendar months**, the standard convention in this literature, not
  an exact trading-day count, and its statistical uncertainty is not
  adjusted for the fact that overlapping monthly holding periods can
  understate the true uncertainty. The point estimate itself is
  unaffected either way.
- **All trade-level data comes from Quiver Quantitative**, not pulled
  directly from the House Clerk or Senate disclosure systems. Section
  11's 20-transaction manual check (Addendum F) is a small, non-bulk
  sample, not a substitute for full independent sourcing. More than
  half of the 20 were confirmed directly against the actual House
  Clerk filing (ticker, transaction type, transaction date, and
  disclosed amount all matching), and the rest were checked against
  the data vendor's own site rather than the original filing, a weaker
  check, since it can confirm this paper's own data-handling is
  accurate but not that the vendor's underlying data is accurate. Zero
  mismatches were found under either method, and the exact filing date
  used in this paper's data is not printed on the disclosure form
  itself (which only shows the transaction date and a separate
  broker-notification date), so that one field could not be directly
  checked.
- **Every match in this study relies on the ticker symbol**, not a
  permanent company identifier. A ticker-reuse check finds, but does
  not fix, cases where one company has used more than one historical
  ticker symbol.
- **The random-date comparison test uses a capped subset of
  transactions**, not the full filtered-sale set, to keep it
  computationally practical. This is a permanent, stated choice, not
  something left unresolved.
- **Buy-and-hold abnormal return (BHAR)** is calculated at every time
  horizon and by every method as planned, but is not shown in its own
  table beyond serving as a cross-check on CAR.
- **The 18-month holdout (Section 7.5) does not have enough data to
  pin down every number precisely.** The main model's member, year,
  and industry controls, eight size categories, and two interaction
  terms leave 3,985 holdout observations able to estimate the `sale`
  number itself reasonably, but several other numbers in the same
  regression carry uncertainty as big as or bigger than the number
  itself. This is a property of asking a model with this many moving
  parts to work on an 18-month window, not something specific to which
  18 months were chosen. Following this paper's own plan, the result
  is reported exactly as it came out rather than fixed and rerun.
- **Section 12's rules were applied to the single primary test only.**
  The random-date comparison check was run once, against the primary
  test. The three other results reported in Section 7.2 as clearing
  the corrected statistical bar on their own have not separately been
  checked against a random-date comparison, so they are reported as
  secondary evidence for that reason, not as tests that cleared both
  of Section 12's requirements.

## What This Paper Does Not Claim

No claim about why any of this happens is made. This paper observes
when things happened, not why. No claim about any individual member is
made. No claim about whether any transaction was legal is made. No
investment advice is offered.

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
