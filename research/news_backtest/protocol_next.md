# Next event/anomaly tests: rules locked before any run

Locked 2026-11-24. No code for (a)–(c) has been run, and no result exists. Simulated money, public data only, and no LLM scores on past data (training-data lookahead). The general rules in `protocol.md` also apply here: entry at the open of the first session at/after the timestamp, exit at the close, 0.09% cost per side (0.18% round trip), a 2× cost run, gross and net both reported, splits train ≤ 2022 / validation 2023–24 / test 2025+, a test slice that is reported once, and a seed of 20261124.

**Statistics, the same for every test below.** Mean net, mean control and the mean paired difference, each with an iid bootstrap p and a **block bootstrap p** that resamples symbol-month clusters (`core.news_backtest.block_bootstrap_p`). Only the block p counts. The iid p is reported for comparison.

**Pass rule for an edge candidate.** It must meet all five conditions: (1) block p_diff < 0.05 on train+validation pooled; (2) mean diff > 0 in **both** train and validation; (3) mean diff > 0 in test, reported once; (4) mean net > 0 at 2× cost; (5) no single symbol accounts for more than 25% of the summed paired difference. Failing any one of these means "no edge shown". Thresholds are not changed after a run.

## (a) 8-K filtered by item code
- Event: an 8-K whose header lists item **2.02** (results), **1.01** (material agreement) or **5.02** (officer change). Each item is tested separately. Item codes come from the EDGAR filing index/full submission header (`Archives/edgar/data/<cik>/<accession>/`), not from the text body and not from an LLM.
- An 8-K with several items counts under each of its listed items. The pooled "any of the three" result is reported, but it is not a pass by itself.
- Horizons 1/3/5, long-only, with the same random same-class control. Universe: the same 40 large caps as the pilot, then all universe stocks that have filings.
- Not allowed: picking the best item after looking at test, or adding a sign rule ("only when the 8-K is good news"). A direction rule would need its own new protocol.

## (b) Form 4 open-market insider purchases
- Event: a Form 4 with transaction code **P** (open-market purchase) by an officer or director, accepted after 2018-01-01. Value ≥ 50,000 USD per filing. Code A/M/G grants and option exercises are excluded.
- Long 1/3/5 sessions, same control. Primary universe: the current 217-symbol universe (large caps). **Known limit:** the documented insider-purchase drift is concentrated in small and micro caps, which this universe lacks. A null result here therefore says nothing about microcaps. A microcap run needs a new universe, real spread data and its own protocol, using a cost of at least 0.5% per side.
- Expect few events in large caps. Below 300 events per horizon, the result is descriptive only.

## (c) Cross-sectional momentum 12-1, long/flat
- Each month-end, rank the universe stocks by return from t−12 months to t−1 month (skipping the last month). Hold the top decile equal-weight for one month, flat otherwise. Entry is the next session open and exit is the next month-end close. Turnover is charged at 0.09% per side.
- Control: buy-and-hold, equal weight, of the **same** stock basket, rebalanced monthly at the same cost. Report monthly paired differences, with blocks = calendar months (for one portfolio, a symbol-month block collapses to a month).
- Pass rule as above, except (5) becomes: no single month accounts for more than 25% of the summed difference.
- Known limits: current tickers only (survivorship bias favours momentum), Yahoo split-adjusted prices, dividends ignored.

## (d) Negative control: turn of month
- Purpose: check the harness, not find an edge. Event: the last trading session of each month, for every universe stock. Enter at that session's open and exit at the close of the 3rd session of the next month. Control: a random non-turn-of-month session for the same stock, drawn deterministically with `random.Random(f"{symbol}:{ts}")`.
- Expectation written before the run: in large caps after 2018, the gross paired difference should be small (|diff| < 0.15%), and net after cost should not pass. If it **passes** the rule above, treat that first as a harness bug (lookahead, a timestamp shift, control leakage) and look for one before believing it.
- Also run a **placebo**: event timestamps shifted by a random 20–60 sessions. Its paired difference must not pass. If it does, the harness is wrong.

## Order
Run (d) first: if the harness fails it, stop. Then (a), then (c). Run (b) last, and only together with the microcap protocol if the large-cap count is under 300.

## Addendum 2026-11-24: implementation details fixed before the first run
Code: `core/studies.py` (pure, tested in `tests/test_studies.py`) and `research/studies/run.py`, run on GitHub Actions (`.github/workflows/research.yml`). None of these rules adds a filter.
- (a) Item codes come from the `items` field of the SEC submissions API. That field is EDGAR's parsed copy of the filing header and needs no per-filing download. Form type is `8-K` only, as in the pilot code. The universe is every universe stock; the 40 pilot symbols are also reported, descriptively.
- (b) Source: the SEC "Insider Transactions Data Sets" (quarterly `form345.zip`, tables SUBMISSION / REPORTINGOWNER / NONDERIV_TRANS), from 2018Q1 onward. Document type `4` only. Relationship must contain Director or Officer. Code P and acquired, summed per accession, ≥ 50,000 USD. Timestamp: the EDGAR acceptance time when the issuer's recent-filings list has that accession. Otherwise 04:00 UTC on the day after the filing date, which is never earlier than the real acceptance, since Section 16 filings accepted up to 22:00 ET keep their date. The universe is the 148 universe stocks; ETFs, FX, commodities and crypto have no Form 4.
- (c) Formation uses month-end closes. The basket is every stock that has a score that month, and fewer than 10 stocks means no position. Both portfolios pay a full round trip each month, because the rule exits at the close and re-enters at the next open.
- (d) The control window may come from any non-turn-of-month session of the same stock in the data, before or after the event. The placebo shift goes forward. A placebo window past the end of the data is skipped.
- The SEC timestamp (`acceptanceDateTime`, suffix Z) was confirmed to be UTC: Apple's 2.02 8-Ks are stamped 20:30Z in summer and 21:30Z in winter, which is 16:30 ET in both cases.
