# F7 US small-cap intraday LONG events (family 7)

Simulated money, public data, long only (no margin short). Locked before the first scan; changing a rule needs a new dated file.
Code: `core/smallcap_intraday.py` (pure rules, simulation, gate), `research/studies/smallcap_intraday.py` (collector), workflow
`.github/workflows/smallcap_intraday.yml`, keeper dispatch weekdays 21:45 UTC. Tests: `tests/test_smallcap_intraday.py`.
Earlier failed lines not repeated: L3 (small-cap news, daily bars), L7 first red day (short), L10 gap fade (short).

## Data probe (Actions run 2026-11-25)
- Yahoo 5m with pre/post: about 85 calendar days (from 2026-09-01), 1m only 7 days, 1h about 3 years. So 5m history cannot hold train/val/test.
- Alpaca IEX and Polygon: HTTP 401 without a key (no secret exists); Stooq needs JS/API key. No free multi-year intraday source found.
- Nasdaq halt RSS and NYSE halt JSON: current day only, no history, reachable from Actions -> forward archive only.
- Decision: forward collector (not a thin backtest). The 85-day Yahoo window is the first train data; events are archived so they outlive it.
  The sweep engine (`core/sweep_engine.py`) is hourly crypto bars with binance loaders and cannot express event-day gap universes, premarket gaps or halts, so it is not used; its `core/sweep_stats.py` (gate, block p, Holm, folds) is reused.

## Rules (family of 50; Holm over gate survivors)
- Universe, point in time: prior regular close 1-20 USD; mean dollar volume of the 20 prior sessions (>= 10) 0.5-50 MUSD (band low < 5M <= high); premarket activity: >= 3 five-minute bars with a print before 09:25 ET (Yahoo premarket volume is always 0, so premarket dollar volume cannot be measured; probe 2026-11-25) and dollar volume of the first regular 5m bar >= 50k USD (known at 09:35, before the earliest 09:40 entry); days within 3 sessions of a split skipped; SEC list of Nasdaq/NYSE/NYSE American/Cboe tickers (survivorship: delisted names are missing from Yahoo, so a long-side bias; the daily scan limits it to names alive on the event day).
- (a) 36 rules: premarket gap >= 20% or 40% x ORB 5/15/30 min x exit {stop at ORB low + 15:55, stop at ORB low + 11:30, 8% trailing + 15:55} x band {low, high}. Entry: first 5m close above the ORB high, filled at the next bar open, entry bar must start by 11:00 ET.
- (c) 10 rules: gap >= 20%, ORB 15, exits {stop+15:55, trail+15:55} x tag {contract, fda, earnings, offering, none}. Tag from 8-Ks accepted between the previous 16:00 ET and 09:25 ET (item numbers + keywords in the EX-99 / main document). No LLM: zero calls, nothing to log in `reports/COSTS.md` (Claude Haiku 5.5 only if ever added).
- (b) 4 rules, forward only: Nasdaq LUDP halt after a run-up >= 5% in the prior 15 min, buy the first 5m bar open after resumption, hold 15 or 60 min, with or without an 8% hard stop. NYSE halts archived raw only.
- At most 3 positions per day (best first-bar dollar volume), size 1/3 of the 147 USD account each.
- Costs: 0.5% per side slippage/half-spread (EST) + SEC 0.0000206 of sale + FINRA TAF 0.000166/share sold (EST) + CAT 0.000003/share per side; no commission. Stress = cost doubled.
- Control: paired random-entry trade on the same event day with the same exit.

## Gate and pass rule
Stage 0 (train only): >= 30 trades, mean > 0 and > reversed-side placebo, vol-to-cost >= 10, x = N*s^2 per 30 days >= 0.2, all-win ceiling >= 3x/month.
Splits by event date: train 2026-09-16..2026-12-31, validation 2027-01-01..2027-03-31, test 2027-04-01..2027-06-30. Validation and test are only computed after their window closed. Pass = `core/sweep_stats.criteria` (val/test net > 0, also at 2x cost, enough trades, Holm p < 0.05 on validation block bootstrap, >= 70% positive folds, last-12-month 2x positive) plus validation net above the paired control. Not found is a valid result.
