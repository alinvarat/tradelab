# News playbook: what the Haiku analyst learned (2026-11-26)

Read this as a record of what was tried and what failed, not as a trading recommendation. Measurement: net P&L per offered item, abstain = 0, entry at publication + 93 s (proxy) + 5 s, costs 0.20% stocks / 0.40% crypto round trip. Protocol and addenda in this folder; per-version numbers in `research/studies/RESULTS.md`.

## Rules the analyst was given (v3/v4) and how they fared
1. **Delisting, removal and monitoring-tag notices on crypto: short for 1 h and 1 d.** Learned on clean train (2025-12..03): offered items fell 9.9% over a day on average, the analyst's shorts netted +10.5% a trade. Clean validation (2026-04..06): flat (-0.2%). Sealed (2026-08 on, v4, 48 trades at 1 d): -1.8% a trade, -0.9% per offered item. **The rule did not survive out of sample; treat it as a regime, not a law.**
2. **Funding-interval and other routine non-listing notices: short for 1 d only.** Offered items drifted down 3-5% in train and validation; the sealed 1 d result of the combined v4 is negative, so no support.
3. **New listings: abstain** (mixed sign across splits).
4. **US stock 8-Ks: abstain unless an unmistakable large surprise.** No stable text rule was found for earnings, officer changes or material agreements; the opening gap did not predict the day consistently (train +1.85% after gaps over 3%, validation +0.13%).

## What worked as a method
- **Pre-entry move as an input** is necessary for any "already priced" reasoning and is now recorded for every item.
- **Strict closed-before analog retrieval** works mechanically; analogs made the analyst more cautious, not more accurate.
- **Anonymization** (names, tickers, dates removed, sector descriptor kept) did not cost or add performance on the contaminated diagnostic (named minus anonymized on stock 1 d: -0.06%, +0.01%, -0.02% for v0, v1, v2): no sign that memory carried the results.

## Failure modes
- **Over-abstention:** the rubric prompt (v1) refused almost every trade (stock 0-1 trades, crypto 0-6), so it scored zero by doing nothing. A rubric that says "most news has no edge" must be balanced against a base rate.
- **Trading stock noise:** the plain reader (v0) traded 7% of stock items at about -0.4% a trade in clean validation.
- **Regime fit:** a rule learned in one 4-month window (a falling crypto market) fitted that window.
- **Costs:** a 0.2%-0.4% round trip eats almost every text-derivable move except forced-flow events.

## Limits
Stock 5 minute and 1 hour holds are unavailable historically. 38% of stock filings come during the session and cannot be labelled (no historical minute bars); the sealed set kept 625 of 1,014. The 93 s lag is a proxy for the real seen-minus-published time. Haiku's apparent knowledge cliff is about 2025-11 (leak probe), so everything before 2025-12 is a diagnostic, not a development set. The forward news-latency items (real `t_seen`, 1-minute paths) are not read by this study; they are the right sealed material for a later addendum.

## Round 2 (2026-11-26): intraday labels, GDELT headlines, calibrated abstention
Protocol `protocol_r2_20261126.md` + two addenda; data on `data/news-train-r2`; per-version numbers in `research/studies/RESULTS.md`.
- **The "38% of filings are in-session" blocker was a time-zone artefact.** The SEC `acceptanceDateTime` is UTC; round 1 read it as New York time. With the true time only about 4-5% of S&P 500 8-Ks are filed during the session (1-hour bars label all of them), so stock intraday labels were never the real constraint. Most 8-Ks are after the close or before the open and enter at the next open.
- **Calibrated abstention works mechanically:** asking for a signed expected move and trading only above a threshold fitted on train gave 18-37 stock trades and 43-192 crypto trades in validation instead of round 1's 0-6 or 40% of everything. It did not create an edge: every 8-K item class and every headline class had mean 1 h gross within +-0.3% on train, below the 0.2% / 0.4% costs.
- **Forced-flow tagging found almost nothing to tag:** the analyst tagged 99.9% of GDELT headlines and nearly all 8-Ks "none". Forced flow lives in exchange notices (round 1), not in news headlines.
- **Surprise-vs-expected, the already-priced check and analogs** (w1-w3) moved validation scores by hundredths of a percent per offered item; none was significant.
- **Result:** sealed crypto (GDELT 2026-08-01..11-26, w1, 214 traded at 1 h): -0.42% a trade, -0.045% per offered, all Holm p = 1. Stock forward set accumulates by schedule.
- Method lesson: write the selection rule with a trade floor (round 1 locked a version with 1 validation trade); decide the sealed trigger on decision counts, never outcomes.
