# Author's defense-prep notes

Internal only — not part of the paper. Moved out of `draft.md` on
2026-08-25 so the paper itself doesn't ship with self-quizzing notes in
it. Keep this for your own reference before meeting with the professor
or a referee.

A referee — or a professor asked to look at the identification strategy —
will ask about some subset of these. Each is a defensible, documented
choice, not an error, but "defensible" only helps if you can explain the
reasoning yourself, not just point at the code comment that made the call.

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
- The delisting-data patch (Addendum C) prefers each security's "Q"
  bankruptcy-suffix symbol over its plain ticker, and only falls back to
  the plain ticker's own data if it resumes within 30 days of the last
  known date. Know why "just re-query the plain ticker" was rejected: it
  is a real, confirmed failure mode (Bed Bath & Beyond's own reused
  ticker), not a hypothetical one, and a referee who knows the case may
  ask about it directly.
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

## New, since real results exist (2026-08-25)

- The single pre-registered primary test is a **null result** by this
  paper's own decision rule (Section 12): it survives neither
  Benjamini-Hochberg correction nor the random-control percentile bar.
  Say this plainly and first if asked "so did you find it or not" —
  don't lead with the secondary grid.
- H3's interaction runs the **opposite sign** from its prediction. This
  is a real non-confirmation, not a rounding issue. Have an honest answer
  ready for "why do you think that happened" that doesn't overreach past
  what the paper itself claims (observes timing, not mechanism).
- Model 3's calendar-time alpha is also signed opposite to H1's
  prediction, though not itself significant. Don't let this one surprise
  you if asked about it directly — it was caught and corrected once
  already during drafting (see git history, commit `96427bf`).
- The 18-month holdout has real, expected weak-identification issues
  (see Section 7.5) — several coefficients in that one fit have standard
  errors far larger than their point estimates. This is a small-sample
  property of the specification's parameter count relative to an
  18-month window, not a bug, and the pre-registered protocol required
  reporting it as-is rather than re-running.
