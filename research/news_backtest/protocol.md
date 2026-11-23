# Filing drift: does an SEC filing still pay after cost?

Locked 2026-11-24, before the first result exists. Simulated money and public data only; no orders.

**Question.** If a trader can only act at the first session open after the SEC publishes a filing (8-K first, Form 4 later), does buying and holding 1/3/5 sessions beat a random stock of the same asset class bought at the same moment, after costs?

**Why this test.** The 14 research notes leave exactly one replicated edge — slow text/event drift — while headline chasing dies at cost. SEC EDGAR is the only free source with a second-precision acceptance timestamp (`acceptanceDateTime`), so the test can be point-in-time without hindsight.

**Data.** SEC submissions API (`data.sec.gov/submissions/CIK##########.json`) for form type and acceptance time; SEC ticker map for CIK. Yahoo daily bars (`10y`, `1d`) for entry open and exit close. First run: 40 liquid US large caps from `core/universe.py`; later expand to every universe symbol that has both SEC filings and bars.

**Rules (fixed before looking).**
- Event: any 8-K (8-K/A included) accepted after 2018-01-01.
- Entry: open of the first daily session whose timestamp is at/after the acceptance time. A filing accepted during a session therefore waits for the next open (conservative; no same-day close entry).
- Hold: 1, 3 or 5 sessions; exit at that session's close. Long only.
- Each event is one independent observation. No compounding, no position limit, no overlapping-trade netting; this is an event study, not an equity curve.
- Costs per side: 0.05% fee + 0.02% slippage + half the class spread (stock 0.02%) ≈ 0.09%; round trip ≈ 0.18%. Report gross and net, plus a 2× cost run.
- Control: a random other stock from the studied set, bought at the same open and sold at the same close; deterministic per (symbol, timestamp). No event filter on the control.

**Splits.** train ≤ 2022-12-31, validation 2023–2024, test 2025-01-01 onward. Horizons, filters and any "best item type" are chosen on train/validation only; the test slice is reported once.

**Evaluation.** Per horizon: number of events, mean net, mean control, mean paired difference, share positive, bootstrap p (2,000 resamples, seed 20261124) for mean net > 0 and for mean paired difference > 0. The first 40-symbol run is a **pilot, descriptive only**. No conclusion before 300 complete events per horizon, and never on the pilot alone; an edge candidate must also be positive in the test slice and survive 2× costs.

**Known limits.** 8-K includes routine filings (Reg FD, exhibits) that are not catalysts; events cluster by firm and by market regime, so observations are not independent; Yahoo prices are split-adjusted, dividends ignored; current tickers only (survivorship); no intraday queue, borrow or shorting; the acceptance timestamp is when EDGAR accepted the file, not the moment the market learned the content; the control is not matched on sector, size or volatility. A null result rejects this rule, not every filing strategy.

**Reporting.** Table by horizon and split (n, mean net, mean control, paired diff, hit rate, p), the worst/best contributors, the 2× cost result, and the raw rows as JSON next to this file.
