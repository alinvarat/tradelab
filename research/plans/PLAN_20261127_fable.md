# Plan 2026-11-27 (Fable strategy review 4): after D1-D4, P1, P4, key-person and three news rounds

Goal unchanged: a simulated 147 USD account reaches >= 3x in 30 days after costs, beats a random control, rules locked before data.
Status: plan only. No data was run for this file. Every number not quoted from `research/studies/RESULTS.md`, `research/LESSONS.md`, `reports/LEADERBOARD.md` or a data branch is a **prior** and is labelled so.
Leaderboard today: 1,089 sweep rules tested, **0 passed**; closest `fundwin2/fw[thr=0.005,mode=fade_payer,entry=-60,exit=15,delay=0]` (9 of 10 criteria; its signal had look-ahead). With hand-built rules and event families: more than 1,300 tested, 0 passed.
Supersedes sections 3 and 5 of `PLAN_20261126b_fable.md` (P1-P4 and the order of work). Its sections 1, 2 and 4 stay; the stop list below adds to its section 4. The process rules of `PLAN_20261125_fable.md` stay.

Arithmetic used throughout: monthly x = N * s^2 at cluster level; at half Kelly the median month is exp(0.375 x); months to 3x = 2.93 / x; a forward "found" at t about 2 needs about 4 / x months of events.

| x (book, half Kelly) | median month | months to 3x | forward months to confirm |
|---|---|---|---|
| 0.33 (measured today) | 1.13x | 8.9 | 12 |
| 0.70 | 1.30x | 4.2 | 5.7 |
| 1.08 | 1.50x | 2.7 | 3.7 |
| 1.85 | 2.00x | 1.6 | 2.2 |
| 2.93 | 3.00x | 1.0 | 1.4 |

## 1. Honest state
The measured, tradable, cluster-level x is still 0.33 (l1f on perps 0.19 with a negative train mean, fut_delist 0.13, mon_tag 0.005), a median month of 1.13x against the 2.93 that a median 3x month needs, and nothing measured since 26 Nov added to it: D1-D4, P1, P4 and key-person all stopped at stage 0, three Haiku news rounds found no direction edge on public news (sealed crypto -0.42% and -0.36% a trade), the round-1 sealed delisting short lost 1.8% a trade (a 1 d, Haiku-selected rule, so consistent with l1f decay but not a measurement of l1f at 4 h on perps), the OKX funding ledger is negative after 5 settlements (-0.27% to -0.68% a trade, e-values near 1), and the event book has taken 0 trades. The common cause is the one already written down: public information is priced before our 60 s entry and liquid instruments are efficient at our cost. What has changed is the tooling, not the evidence: the pod can now see a notice within seconds, and that is the one handicap none of the 1,300 rules was tested without.

## 2. Next directions, ranked by expected x after the haircut
Haircut rule of `PLAN_20261126b_fable.md` section 1: a pure prior x 0.25, a measured lead with positive validation and test x 0.5. All four inputs below are priors.

| # | Direction | Type | Inputs a month (prior) | x raw | x after haircut | Ceiling half |
|---|---|---|---|---|---|---|
| Q1 | Exchange notice, entry 2-30 s after the jump starts | forward-only (pod), with a one-run historical kill | N 10-15 notices, s 0.15-0.30 | 0.23-1.35 | **0.06-0.34** | passes (perp) |
| Q2 | Follow point-in-time ranked public wallets (Polymarket, then Hyperliquid) | structural, untested | N 40-80 markets, s 0.06-0.12 | 0.14-1.15 | **0.04-0.29** | passes (binary payoff) |
| Q3 | Resting order inside a forced wick: P1's one dated fix, then a real liquidation-print tape | structural fix, then forward-only (pod) | N 50-100 hours, s 0.05-0.08 | 0.13-0.64 | **0.03-0.16** | passes (perp) |
| Q4 | Micro-cap wire press release seen in seconds | forward-only (pod), measure first | N <= 21 (one cash trade a day), s 0.08-0.12 | 0.13-0.30 | **0.03-0.08** | **fails** unless the mean win is >= 5.4% |
| R | Report months-to-3x and the cohort hit rate next to the monthly multiple | restructured target | uses the book's x | - | does not change x | - |

Sum of Q1-Q4 after the haircut: 0.16-0.87; with the measured 0.33 the book would be **0.5-1.2**, a median month of 1.2x-1.57x, and the top end is not to be expected (the priors for D1-D4, P1 and P4 all landed at or below zero). The plan therefore rests on Q1 and Q2 reaching the upper half of their ranges; section 3 says what each stage needs.

### Q1. Seconds-level notice reaction
- **Mechanism.** A delist, monitoring-tag, futures-delist or listing notice forces holders and market makers to trade at once. D2 found the gross move is gone from +60 s; nothing has measured +2 to +30 s. The pod polls OKX every 3 s, Binance every 8-20 s and holds a newswire websocket.
- **Next to (closed, not redone):** D2, the notice tape, forced-flow, L1c, L1g all enter at +60 s or later from minute-level stamps. The one difference: entry is timed from the jump on the trade tape in seconds, and the forward leg uses the pod's real `t_seen`.
- **Data.** Frozen notice lists on `data/forced-flow` and `data/kr-listing` (names and times only), `data.binance.vision` USDT-M aggTrades (already used in the P1 audit), OKX for the rest. Forward: `data/news-ingest`. **Blocker 0:** when read for this plan (2026-11-26) that branch held only its README; no pod latency is quoted here because none has been read.
- **Kill tests.** (0) Outcome-free read once the branch has >= 20 notice rows: per source the median of `t_seen` minus the jump start on the tape. Kill the forward route for a source whose median is above 30 s. (1) One historical run, one protocol: jump start = first 1-second bucket within [notice - 5 min, notice + 10 min] that moves >= 1% in the event direction from the prior 60 s median on >= 5x the median 1 s notional; entry at start + 2 / 5 / 10 / 30 s at the next trade + 0.15% slip, holds 5 min / 60 min / 4 h (12 cells, Holm), 0.40% round trip + funding, 25% stop, cluster = notice. Controls: the same rule on equal-size jumps of the same coins with no notice, and the reversed side. Kill if the train net mean at +10 s is <= 0, if less than 0.8% (2x cost) of the 60 min move is left at +10 s, if the no-notice jump control is not beaten, or if notice-level x < 0.2. (2) Forward: a dated addendum to the event book with its own unit budget, entry at the pod's `t_seen` + 5 s.
- **Cost.** One module with offline tests and one Actions run (about 200 event-days of aggTrades). Forward leg: one pod reader of the ingest log plus an OKX quote snapshot; no LLM.
- **Time.** Test 0: days after the branch fills. Test 1 kill or pass: 2-3 days. Forward: kill at 30 events (about 10 weeks) if the mean is <= 0; found needs about 4 / x months (13 at x 0.3, 6 at x 0.7).

### Q2. Following public wallets, ranked point-in-time
- **Mechanism.** Every Polymarket fill and every Hyperliquid position is public per wallet. A wallet that has been right for 6 months may carry information that is not in the price bars. The signal is who traded, not a forecast of ours.
- **Next to (closed):** polymarket_llm, poly_fv, Thin B, L4, the temperature model: all forecast the outcome or the fair value. The one difference: no model of the outcome; the entry copies a ranked wallet after a delay.
- **Data.** Polymarket data API trade feed (answered from Actions in runs 45519602631, 45523514648); history depth per wallet and paging are **unverified: probe first**. Hyperliquid public info API had a reach limit in P4 (1 coin priced): second arm only if its probe clears.
- **Kill tests.** (0) Counts-only probe: >= 300 wallets with >= 100 resolved positions and a trade history that pages back >= 18 months; else kill. (1) Persistence, no rule P&L: rank wallets on months 1-6, read their realized return on months 7-12, rolling; kill if the rank correlation is <= 0 or the top 50 do not beat the median wallet in the next window. (2) One protocol: at each month start take the top 50 by trailing 6-month realized P&L (two-sided market-maker wallets excluded by a locked rule); follow every new position >= 500 USD at the worse of the next recorded trade >= 60 s later and their price + 1 cent; fixed stake; exit at their exit or at resolution; cluster = market. Controls: the same follow rule on random wallets of matched size in the same markets, and the bottom 50. Kill if the train net mean is <= 0, the random-wallet control is not beaten, market-level x < 0.2, more than 50% of train profit comes from the best 1% of entries, or duplicate rows exceed 5% (the Thin B B6 trap).
- **Cost.** Probe: one short run. Then one protocol, one sharded run. No LLM.
- **Time.** Probe 1 day; tests 1-2 in 3-4 days. Forward confirmation by the keeper, same 4 / x rule.

### Q3. Resting order inside a forced wick
- **Mechanism.** Same as P1: an order that rests before the move is filled only by a forced seller and does not depend on reaction time. P1's locked run also stopped out on the fill bar, which removes exactly the fills where the wick goes deep and returns (24-49% of fills booked at -5.5%; the unstopped fills averaged about +0.9% gross in the train cell). The plan's rule (stop on later bars only) was never run.
- **Next to (closed):** P1 (one run used, one dated fix left), D1, H3. The one difference in stage A: the stop is checked from the bar after the fill. In stage B: real liquidation prints instead of the volume proxy.
- **Data.** Stage A: the P1 rows and loader (`data/p1p4`, 888 perps, 0 failed months). Stage B: OKX `liquidation-orders` and top-of-book for 30 thin swaps, collected by the pod (history is hours only, so forward-only).
- **Kill tests.** (A) New dated addendum, the 18 cells unchanged except the stop; a hard loss cap at the 1-minute low of the fill bar is reported as a stress column. Kill the family for good if validation and test means are still negative in the three d 8% bid cells, or the resting fill still loses to the 60 s late taker. (B) Only if A clears: tape protocol locked before the first row, a bid d% below the mid placed when the first print appears, filled only if a trade prints through it, cluster = instrument-hour, control = the same order at random times. Kill at 200 clusters if the net mean is <= 0 or the control is not beaten.
- **Cost.** A: one re-run on stored rows. B: one pod collector and a publisher line.
- **Time.** A: 1 day. B: 200 clusters in about 2-4 weeks (prior), kill only; found by the 4 / x rule.

### Q4. Micro-cap wire press releases seen in seconds
- **Mechanism.** A press release of a company too small for funded desks moves the stock over minutes, not milliseconds. The pod now reads PR Newswire every 3 s and GlobeNewswire and Business Wire every 5 s; from Actions they were 70-100 s late or blocked.
- **Next to (closed):** news_train rounds 1-3 (S&P 500 8-Ks, next-open or 1 h entry, Haiku picks the side), Track B1 (no archive), smallcap_intraday, L3. The one difference: forward-only wire items with a real `t_seen`, micro caps only, and no LLM side call (a locked item-class rule).
- **Ceiling.** A 147 USD cash account settles the next day, so at most one full-equity trade a session: 21 a month. All wins at +4% is 2.28x; the ceiling half needs a mean win of >= 5.4%. This direction can add to a book; it cannot carry the target.
- **Kill tests (measure only, no rule yet).** Counts and timing from the ingest log for 15 sessions: kill if fewer than 40 in-session items a month map to a ticker under a locked market-cap line, if Yahoo 1-minute bars answer for < 80% of them from the pod, or if the median share of the 60 min move already done at `t_seen` + 5 s is >= 0.5. A trading rule needs its own dated protocol after that read and before any P&L.
- **Cost.** One counts job on the existing log. **Time.** 3 weeks to the kill read.

### R. Restructured target (keeps the owner's need: 147 USD becomes 441 USD, repeatedly)
- **Headline number per session: months to 3x = 2.93 / x of the confirmed book**, next to the monthly multiple. The 3x and the 147 USD stay; the time is what is measured and driven down (8.9 months at today's 0.33, 4.2 at 0.70, 1.0 at 2.93).
- **Cohort hit rate, already locked in the event book protocol:** weekly 30-day cohorts, bank at 3x, halt at 0.4x, 200 control ledgers with the same sizing. Convex sizing does not raise x; it turns a 1.3x median into some 3x months. Normal approximations at x 0.70, month-end, no halt: full Kelly ends >= 3x in about 19% of months against about 4% for a zero-edge control with the same sizing; half Kelly about 2% against about 0.2%. The claim allowed is the gap to that control, confirmed by the e-process; a single 3x cohort is not a result (AGENTS rule 6).

## 3. Staged target path
"Pass" = a locked protocol clears stage 0 and the sweep criteria on validation and test (positive at 2x cost, Holm, cluster-level x counted after a 50% forward shrink). "Confirmed" = the forward e-process reaches 20 against the random control. A stage is reached on pass and kept only if confirmation follows.

| Stage | Median month | Book x needed | What has to be true | Evidence | Earliest |
|---|---|---|---|---|---|
| 0 (today) | 1.13x | 0.33 | l1f perps, fut_delist, mon_tag hold forward | event book e-process not negative after 30 events | running |
| 1 | 1.3x | 0.70 | one new component at x >= 0.35 after shrink (Q1 or Q2 at the top of its range) | first locked rule passes historically; forward kill-free at 30 events | pass in 1-2 weeks; confirmed in about 6 months |
| 2 | 1.5x | 1.08 | a second independent component at x >= 0.35; daily-P&L correlation with stage 1 inside +-0.1 | second pass; cohort hit rate above the control's in the table | 1-2 months to pass |
| 3 | 2x | 1.85 | three to four components, or stage 2 confirmed and moved from half to 0.75 Kelly by a new dated protocol (growth 0.47 x: 2x at x 1.48) | stage 2 confirmed (e-value 20) before any size-up | 4-6 months |
| 4 | 3x | 2.93 (2.2 at full Kelly) | stage 3 confirmed and a high-N component (N >= 100 a month at s >= 0.1) | cohort table: real banks in >= half of the cohorts and the e-process edge | not datable from today's evidence |

Rules: sum only x measured on instruments tradable at the event time, at cluster level; a component enters by `components_addendum_<date>.json`; an existing component's size never changes by addendum; if Q1 and Q2 both die at their historical kill, stage 1 has no candidate and the next plan starts from the Q3/Q4 reads.

## 4. Stop spending compute on (adds to `PLAN_20261126b_fable.md` section 4)
1. **Any LLM reading public news for direction**, stock or crypto, any language: three rounds, sealed -0.42%, -0.36%, -1.8% a trade. No round 4, no new prompts. The round-2 stock forward set and the Sonnet-vs-Haiku comparison finish as locked; no further model comparison.
2. **Haiku's size estimate as a signal**: sealed partial rho 0.145 but it does not beat the pre-entry move and falls to 0.047 with a filing-type flag.
3. **D1 thresholds, D2-D4, P4 and its other-venue replication, key-person 5.02, the notice tape at +60 s**: all closed at stage 0. P1 gets its one dated fix (Q3 stage A) and nothing else.
4. **New funding-window variants.** The OKX ledger runs to its locked decision; it is negative so far.
5. **Notice polling from Actions for new components.** A 30 s poll inside a 10-minute job cannot test a seconds-level rule; new notice components read the pod log.
6. **Pod infrastructure beyond what Q1 and Q3 name** (AGENTS rule 10): no new feeds, dashboards or latency work until test 0 of Q1 has been read.

## 5. The live bot (Haiku, v4.18)
Numbers from the brief, not re-read here (`/api/llm_trader` did not return JSON to a plain read-only request): model 4,875 THB, random control 5,051 THB, so -2.5% against +1.0%. The locked criterion (`research/llm_trader/protocol.md`) concludes nothing before 30 closed pairs and then needs a positive model mean, a positive paired difference and bootstrap p < 0.10; the model is behind its control, which is the same sign as the three news rounds.
- **Keep it running, frozen.** No new version tag, role, prompt or feed: every bump restarts the pair count, and the news ingest stays measure-only.
- **One reading, then a decision.** Read the locked criterion at 30 closed pairs under v4.18 or on 2026-12-26, whichever is first. If it is not an edge candidate, pause the LLM cycles (the ledger and its statistics stay) and give the pod's Claude quota to research; if it is, the protocol's second non-overlapping window starts unchanged.
- **Quota.** If the bot's calls and a research run contend for the Max plan before then, the research run has priority (AGENTS rule 10).

## 6. Order of work (parallel lanes)
| Lane | Now | Next |
|---|---|---|
| A. Historical, one run each | Q1 test 1 (aggTrades around frozen notices); Q3 stage A (P1 stop fix on stored rows) | Q2 tests 1-2 after its probe |
| B. Probes, outcome-free | Q2 counts probe; confirm `data/news-ingest` is filling, then Q1 test 0 and the Q4 counts | Hyperliquid reach probe |
| C. Forward (pod, keeper) | nothing new until a lane-A pass | Q1 addendum to the event book; Q3 stage B tape |
| D. Book keeping | report months-to-3x and the cohort table each session | bot reading at 30 pairs or 2026-12-26 |

One dated protocol or addendum each, locked before the first price; one run and at most one dated fix; simulated money, public endpoints, no keys; "not found" is written to `RESULTS.md` and `LESSONS.md` the same day.
