# Congressional Trading Study: Project Summary

A reference document for applications, resumes, and interviews. Every
number below is real and verified, pulled directly from the study's own
output and this project's commit history, not rounded up or estimated.
Save this and pull from it as needed.

---

## The one-line version

Designed and ran a pre-registered empirical study testing whether stock
sales disclosed by members of Congress predict subsequent market
underperformance, analyzing 100,000+ real transactions spanning 10 years.

## The scale, in numbers

- **100,272** real disclosed congressional stock transactions analyzed
  (2014 to 2024, both House and Senate)
- **5,046** distinct securities in the full ingested universe
- **12 million+** daily stock price records processed
- **13,039** transactions survived a custom four-stage filtering process
  built to isolate the transactions most likely to reflect real
  information rather than routine portfolio activity
- **18** distinct pre-registered statistical tests, each independently
  corrected for multiple-testing error (Benjamini-Hochberg correction)
- **1,000-iteration** Monte Carlo-style permutation test as an
  additional robustness check
- **336** individual securities specifically patched for missing
  post-bankruptcy/acquisition price data, so the results aren't
  distorted by companies that quietly disappeared from the dataset
- **20** transactions independently hand-verified against real
  government disclosure filings (not just the data vendor), to confirm
  data accuracy
- **2** full independent end-to-end reproductions of the entire
  analysis, byte-for-byte identical output both times
- **18-month** untouched out-of-sample holdout period, held back and
  tested only once, after every other result was finalized

## What makes this rigorous, not just a school project

- **Pre-registered.** Every hypothesis, every statistical test, every
  data-exclusion rule, and every table/figure to be produced was written
  down and locked in before touching real data (dated 2026-08-08). This
  is the same discipline required of clinical trials and top-tier
  academic journals, specifically to prevent quietly changing your
  approach after seeing results that don't support your idea.
- **Built a real data pipeline from scratch**, integrating six separate
  data sources (a congressional trading data vendor, a stock price
  provider, an academic factor-model database, two government/academic
  legislator datasets, and SEC filings) into one coherent system.
- **Applied graduate-level financial econometrics**, including
  event-study methodology (cumulative and buy-and-hold abnormal
  returns), a four-factor asset-pricing model, fixed-effects panel
  regression with clustered standard errors, and a calendar-time
  portfolio regression, the same toolkit used in published finance
  research.
- **Reported the honest result, including where it didn't confirm the
  hypothesis.** The study's single most stringent pre-registered test
  came back statistically null, and one hypothesized effect ran opposite
  to its prediction. Both are reported plainly rather than hidden,
  reframed, or explained away.

## The finding, in plain language

Whether members of Congress buying stock might reflect inside knowledge
has been studied a lot. Almost nobody has carefully studied their
*sales*, even though selling before bad news would be the harder-to-spot,
lower-risk version of the same behavior. This study built a filtering
process to separate sales that look like ordinary portfolio management
(rebalancing, tax timing, retirement) from sales that don't have an
obvious innocent explanation, then tested whether that second group
predicted the stock later underperforming the market.

The single strictest, pre-registered test didn't reach statistical
significance, so this isn't a "gotcha, proven" result. But a broader,
consistent pattern across the rest of the pre-specified analysis points
the same direction, and one specific finding (sales in sectors a
member's committee oversees showing a stronger effect) lines up with an
independent study published around the same time using completely
different data handling. Reported honestly, both the significant and the
non-significant parts.

## Ready-to-use blurbs, by length

**Resume bullet (one line):**
> Conducted a pre-registered empirical study of informed trading in Congress, analyzing 100,000+ disclosed stock transactions (2014-2024) using event-study methodology and multiple-hypothesis statistical correction.

**Activity list / short application field (~150 characters):**
> Independent research: pre-registered study testing whether congressional stock sales predict market declines, analyzing 100K+ trades across 10 years.

**Two to three sentences (essay material, interview opener):**
> I designed and ran an independent research study asking whether stock sales disclosed by members of Congress predict that stock later underperforming the market, a question almost entirely unstudied compared to the attention given to their purchases. I pre-registered the entire methodology before touching real data, then analyzed over 100,000 real disclosed transactions from the past decade, building a full data pipeline, applying financial econometric methods, and independently verifying a sample of the results against actual government filings. The main result was a statistically honest mixed finding rather than a clean confirmation, which I think matters as much as the finding itself.

**Full paragraph (application essay, cover note):**
> For this project I wanted to test something that surprised me hadn't really been studied: almost all research on congressional stock trading looks at whether members' *purchases* seem suspiciously well-timed, but almost none looks carefully at their *sales*, even though selling ahead of bad news would be the smarter, quieter version of the same behavior. I built a full research pipeline from scratch, integrating six different data sources into a dataset of over 100,000 real disclosed transactions spanning 2014 to 2024, and designed a filtering system to separate sales that look like ordinary portfolio management from sales without an obvious innocent explanation. Before running any of it against real data, I pre-registered every hypothesis and statistical test I intended to run, exactly the discipline used in clinical research, specifically so I couldn't quietly change my approach after seeing results I didn't expect. The single strictest test I pre-registered came back statistically inconclusive, and I reported that honestly rather than reframing it, but a broader, consistent pattern in the rest of the analysis still points toward an interesting effect, and I independently verified a sample of the underlying data against real government records to confirm it was accurate. I'm currently working with a law professor to figure out where this could realistically be published.

---

*Last updated 2026-08-25. Pulled from the real, verified output of
`congressional-sales-2026`; every figure here traces to a specific
number in the study's own results, not a rounded or estimated one.*
