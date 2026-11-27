# Plan 2026-11-28 (Fable strategy review 5): after the REJECT review, Q1 and the delist venues

Goal unchanged: a simulated 147 USD account reaches >= 3x in 30 days after costs, beats a random control, rules locked before data.
Status: plan only. No project code and no data run was made for this file. Numbers are quoted from `research/studies/RESULTS.md`, `research/LESSONS.md`, `reports/LEADERBOARD.md` and the data branches read on 2026-11-27 (`data/notice-fwd`, `data/event-book`, `data/poly-rewards`, `data/l1f-margin`, `data/p1p4`); everything else is a **prior** and is labelled so.
Leaderboard today: 1,089 sweep rules tested, **0 passed**; closest `fundwin2/fw[thr=0.005,mode=fade_payer,entry=-60,exit=15,delay=0]` (9 of 10 criteria; its signal had look-ahead). With hand-built rules and event families: more than 1,300 tested, 0 passed.
Supersedes `PLAN_20261127_fable.md` sections 1 to 4 and 6 (its section 5 was already superseded by the owner). The stop lists of `PLAN_20261126b_fable.md` section 4 and `PLAN_20261127_fable.md` section 4 stay; section 4 below adds to them. The process rules of `PLAN_20261125_fable.md` stay except where section 2 tightens them.
Input: the adversarial review of 2026-11-27 (verdict REJECT). Every finding is mapped to a line of this plan in section 5.

Arithmetic used throughout: monthly x = N * s^2 at cluster level (notice, market or hour, never coin or fill); at half Kelly the median month is exp(0.375 x); months to 3x = 2.93 / x; a forward e-process that must reach a bar B needs about 2 ln(B) / x months of events (log wealth of the best bettor grows about x / 2 a month). That is a **floor**: rule F pairs every ledger against an independent control, which about doubles the time, so every forward-months figure in this file is a floor and the paired figure is about twice it.

| x (book, half Kelly) | median month | months to 3x | forward months (floor) to bar 20 (old) | to bar 80 | to bar 100 | to bar 200 |
|---|---|---|---|---|---|---|
| 0.18 (measured, unconfirmed) | 1.07x | 16.3 | 33 | 49 | 51 | 59 |
| 0.70 | 1.30x | 4.2 | 8.6 | 12.5 | 13.2 | 15.1 |
| 1.08 | 1.50x | 2.7 | 5.5 | 8.1 | 8.5 | 9.8 |
| 1.85 | 2.00x | 1.6 | 3.2 | 4.7 | 5.0 | 5.7 |
| 2.93 | 3.00x | 1.0 | 2.0 | 3.0 | 3.1 | 3.6 |

The earlier plans' "4 / x months to found" was a t of about 2 with no multiplicity control; it is withdrawn.

## 1. Honest state and what the review changed
- **Confirmed x is 0.** No rule has passed stage 0 with validation and test, and none of the four forward ledgers read for this plan has an outcome yet (the other ledgers were not re-read): the event book has seen 1 event and taken 0 trades (3,006 polls, 6 notices stale at first sight), `notice_fwd` has 0 notice clusters in 393 items, the margin recorder has heartbeats only, the P3 tape has 0 completed days.
- **Measured, tradable, notice-level x is about 0.18, not 0.33.** The 0.33 of the last three plans added coin-level figures. At notice level: l1f on Binance perps 0.04 (set A, n 65, train mean -3.3%), fut_delist 0.13 (train n 6), mon_tag 0.005: 0.175 together. (Using the l1f perp set A+B, notice-level 0.18, instead of A would read 0.32 in total; B is 7 notices in 34 months with train n 4, so it is not used.) **Each part fails stage 0 on its own record**, so 0.18 is an unconfirmed in-sample reading: a 1.07x median month, 16.3 months to 3x, and at least 51 forward months to its bar under section 2 (about twice that when paired).
- **Not in the baseline:** the Binance margin short of the 39 no-perp delist coins (coin level x 2.23, notice level 0.96, validation n 3, about 1.15 events a month, borrow assumed). It is an upper bound until `data/l1f-margin` holds notice rows with a real borrowable flag and rate. A 25% stop at Kelly size on a 2.23 reading would also empty the account in a few losses; its size is set from the notice-level figure after a 50% shrink, never from 2.23.
- **Last plan's directions, disposition:**
  - Q1 (wallet follow): **dead** at stage 0 (train n 5,552, mean -2.56%, x -0.58, random wallets not beaten, p 0.81). Hyperliquid arm not runnable point-in-time.
  - Q2 (notice at seconds): historical test 1 has no entry in `RESULTS.md` and **is dropped** (about 5 notices a month caps x near 0.1; rule H2 below cannot be met). The forward ledger `notice_fwd` runs as locked (verdict "underpowered", deadline 2027-02-06). Pod lag read from `data/notice-fwd/summary.json` (2026-11-27 00:11 UTC): EquationNews 4.26 s median (n 90, p90 8.3 s); Binance 87.0 s (n 3) and 60.6 s on the fast path (n 1); OKX 93.9 s (n 3). The ledger's own kill is a source median above 25 s: Binance and OKX direct are on course for it once their n is readable (PR #281 added race paths; read again at 20 notice rows per source). EquationNews is the only fast route and its lag behind the exchange's own stamp is unmeasured (`pub_gap_s_eqn_minus_direct` is empty).
  - Q3 (resting order in a wick): stage A has no entry in `RESULTS.md`; **dropped on paper**. It could only kill or open a tape, never add to the book, and it would spend a family. The P1 summary already answers the question it asked from both sides: the resting fill loses to the 60 s late taker in every cell, and the reverse (follow-through) side, positive per fill in 18 of 18 validation and test cells, is not positive per cluster. Computed for this plan from `data/p1p4/p1_run/20261125T200129Z/summary.json` for all 18 cells (reversed cluster net = minus the cluster net, less two costs of 0.23%, plus the funding both ways; entry at the limit with no stop-order slip, so an upper bound): positive in **0 of 18 train cells, 0 of 18 validation cells and 4 of 18 test cells** (the four d 3% cells with 5 or 15 minute holds, +0.03% to +0.08%), and in no cell in both holdout splits; the d 8% ask cells read -0.15% validation and -0.04% test. The per-fill gain sits in a few mass-fill hours, which are one risk unit each. No run.
  - Q4 (micro-cap wire releases): **dropped**. The pod sees PR Newswire a median 103.7 s after the stamp (n 181, p90 170 s) and GlobeNewswire stamps have no seconds, so "seen in seconds" does not hold, and the ceiling half already failed (mean win >= 5.4% needed).
  - R (months to 3x, cohort hit rate): kept as the headline format, now with two rows: confirmed (x 0, months not defined) and unconfirmed (x 0.18, 16.3 months).
- **Stage 1 has no candidate.** Section 3 exists to produce one.
- **P3** is "pending the trade-through tape" (PR #283), not `standalone_pass`: the 6-13% a day is a one-snapshot upper bound with a touch-fill model, and nothing is quoted as a return until the tape has 60 days.
- **Capital is not free and components do not simply add.** Perp components share one margin wallet and add only while their summed Kelly notional fits the leverage the venue gives 147 USD; unlevered venues (Polymarket, Kalshi, a DEX pool) lock cash, so each gets a stated slice of the wallet and its growth is scaled by that slice. No table in this plan sums across wallets.

## 2. Cross-family multiple-testing budget
More than 1,300 rules in about 60 protocol families have read outcomes with no control across families. From this plan on:

**Definitions.** A *family* is one dated protocol file with its addenda whose run reads any outcome (a price path, a return, P&L), including runs that end at a stage-0 kill. A counts-only or reach probe (names, timestamps, fees, book depth, no outcome) is not a family. A *forward ledger* is one forward test with its own e-process. Both are numbered in start order in `research/studies/FAMILIES.md` (first step of lane D); until that file fixes the exact count, K0 = 60 families already spent (46 protocol files under `research/studies/`, the news_train and bot protocols, 7 evaluated sweep configs) and 19 forward ledgers already started.

**H. History only nominates.** No historical result is "found" or "confirmed". Family number k (k = 61 for the next one) is *nominated* for a forward ledger only if its pre-registered headline cell passes stage 0 on train, and its pooled validation + test one-sided p at cluster level, after Holm inside the family, is <= alpha_k = 0.10 / (k (k + 1)).

| k | alpha_k | z needed | x_holdout * holdout months needed (= z^2) |
|---|---|---|---|
| 61 | 2.6e-5 | 4.04 | 16.3 |
| 80 | 1.5e-5 | 4.17 | 17.4 |
| 100 | 9.9e-6 | 4.27 | 18.2 |
| 150 | 4.4e-6 | 4.44 | 19.7 |

**H2. Check before the run.** Since t^2 is about x * months, a family whose prior x times its holdout months is below z^2 cannot be nominated even if it is real: it is either not run on history (go forward-only under F, or drop) or redesigned for more independent events. Example: x 0.5 needs 33 holdout months; x 1.5 needs 11. This is the arithmetic reason to prefer high-N ideas, and it removes every 1-to-5-events-a-month notice family from historical work.

**F. Forward confirms, with one shared account of evidence.** "Confirmed" means the master e-value E = sum of w_j * E_j reaches 20, where E_j is ledger j's e-process against its random control (`core/sequential.py`, paired) and the weights w_j are fixed before ledger j's first event and sum to at most 1 over every ledger ever started. A weighted average of e-values is an e-value, so the false-confirmation rate over all ledgers, past and future, stays <= 5%. Equivalently ledger j alone needs E_j >= 20 / w_j.

| Ledger | w_j | Bar 20 / w_j |
|---|---|---|
| Event book (the owner's claim; new components enter it by dated addendum before their first event, which needs no new weight) | 0.20 | 100 |
| L1f margin arm (`data/l1f-margin`) | 0.10 | 200 |
| P3 reward tape; `notice_fwd` | 0.05 each | 400 |
| The other forward ledgers already started (OKX funding, L4f, two spike ledgers, two option ledgers, LLM earnings, round-2 stock forward, news latency, CMP, Thin A F1-F3, smallcap scan, bot tags), equal shares | 0.10 in total | about 3,000 each (15 ledgers) |
| New standalone ledger number m (m = 1, 2, ...) | 0.5 / (m (m + 1)) | 40 m (m + 1): 80, 240, 480, 800, 1,200 |

Ledgers that already hold outcomes restart at E_j = 1 on the day this plan merges; their own locked kill rules are untouched. **Locked protocols are not edited** (AGENTS rule 5): the bar of each existing ledger is attached by its own dated addendum before its next event (the event book's protocol is SHA-locked at bar 20, so its addendum states bar 100 for the "confirmed" label and leaves every other rule as it is). A ledger that decides by a bootstrap p and not by an e-process (P3, the bot) uses the equivalent p <= 0.05 * w_j (P3: 0.0025). A killed ledger's weight is spent, not returned. Kills and futility stops are free: stopping early for "no edge" never needs a bar.

**S. What spending means in practice.** (1) Stage-0 arithmetic and counts-only probes come first because they are free. (2) Every outcome-reading run adds 1 to k and raises z for all later families, so a post-hoc slice of a dead family (a coin-only rerun, a stop variant) costs the same as a new idea and is taken only if it outranks the queue. (3) The session report carries three numbers next to the leaderboard: k, the next alpha_k, and the master e-value with its largest term.

## 3. Next directions
### 3.1 Calibration of the priors on the record
| Plan | Direction | Prior x after that plan's haircut | Realised |
|---|---|---|---|
| 25 Nov | event book (l1f, l1, l1g, news reader) | 1.4-2.6 | 0.18 notice level, unconfirmed, every part fails stage 0 |
| 26 Nov | D1 / D2 / D3 / D4 | 0.15-0.5 / 0.15-0.5 / 0.05-0.2 / 0.05-0.15 | zero gross edge / about zero / negative in test / 13 train clusters |
| 26 Nov b | P1 / P4 | 0.03-0.29 / 0.015-0.08 | 0 of 18, negative / Binance leg capped 0.09 (under the 0.2 line, as predicted), other venues negative, kill 2 |
| 27 Nov | Q1 | 0.04-0.29 | -0.58 on train, killed |
| not scored | P2, Q3, Q4 never run; P3, Q2 pending | | |

Eight scored directions: one reached the low end of its own range (P4's Binance leg) and **none passed** stage 0 with x >= 0.2. A multiplicative haircut (0.5, then 0.25) was the wrong shape: the record is "most are zero or negative", not "all are a quarter of the prior". From now: **expected x = P(pass) * 0.5 * x if it passes**, where 0.5 is the forward shrink and x-if-pass is the geometric mean of the raw prior range. P(pass) = 0.05 for a pure prior (between the Laplace estimate of 1/10 on the eight planned directions and 1/62 on all families) and 0.10 for a measured lead with a positive holdout mean. At these rates a first pass is expected after 10 to 20 families, so the working number is stage-0 verdicts a week, and a killed direction is replaced from the queue the same day under the template below.

### 3.2 Ranked table
All five new directions are pure priors; none uses an LLM. Two of them (the anchored perps and the stale quote) fail the gate's sd / cost line at the only cost on record and pass only if the probe measures a lower cost or a larger move, so their P(pass) is halved to 0.025. The differences between the five are inside the noise of the priors; the order fixes the forward weights now (new ledger m = rank, bars 80 to 1,200 in the last column, whatever the start date), and the five stage-0 probes start together.

**All five are forward-only under rule H2.** None has the holdout that a nomination needs (x * holdout months >= 16.3): the anchored perps have at most 60 days of joint bars, the stale quote's bar arm has recent months only, the other three have no history at all. So the path of each is: paper arithmetic, a counts-only kill, a locked forward ledger with a kill at a fixed number of clusters, and confirmation only at its forward bar.

| # | Direction | Wallet | N a month (prior) | s (prior) | x raw | x if pass (geo mean) | P(pass) | Expected x | Ceiling arithmetic (all trades win) | Gate sd / cost >= 10, on paper | Forward bar |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | Hyperliquid public liquidation ladder: trade into a visible forced-order cluster | perp | 30-100 | 0.05-0.12 | 0.075-1.44 | 0.33 | 0.05 | **0.008** | needs net 0.74% a trade at N 50 | about 16 at a 60 minute hold (P1 measured 9.8-10.1 at 15 minutes and 0.23%) | 80 |
| S2 | DEX pools entering a public trending list, exact AMM fills | DEX cash, 3 slots | 300-1,000 | 0.01-0.04 | 0.03-1.6 | 0.22 | 0.05 | **0.006** | no leverage, 1/3 stake: net 1.1% a trade at N 300, 0.33% at N 1,000 | passes if hourly sd is 15-35% at a 1.5-3.5% round trip | 240 |
| S3 | Tokenized stock, index, FX and commodity perps on small venues against the real underlying | perp | 100-300 | 0.03-0.08 | 0.09-1.9 | 0.41 | 0.025 | **0.005** | at 3x notional needs net 0.37% a trade at N 100, 0.12% at N 300 | **3.6 at the 0.28% on record: fails**; passes only at a measured round trip near 0.10% | 480 |
| S4 | Same event on Kalshi and Polymarket, locked spread, resolving within 48 h | two cash venues | 20-100 pairs a day | not used (near-zero variance) | 0.08-0.4 (growth / 0.375) | 0.18 | 0.05 | **0.005** | no leverage: 3.73% a day locked for a standalone 3x; 0.5% a day is a 1.16x month | not applicable: replaced by locked return a day on capital and the share of pairs with one resolution source | 800 |
| S5 | Stale quote on the slow venue after a 1 s jump on the fast venue (absorbs P2) | perp | 100-400 | 0.02-0.06 | 0.04-1.44 | 0.24 | 0.025 | **0.003** | needs net 0.18% a trade at N 200 | **about 4-6 at holds of 1-5 minutes: fails** (P1 measured 5.0-7.5 at 0.23%); passes only on larger jumps, which cuts N | 1,200 |
| carried | L1f Binance margin short (measured, in-sample, notice level 0.96) | margin | 1.15 | 0.9 | 0.96 | 0.96 | 0.10 | **0.048** | passes on price; borrow unverified | passes on price | 200 |
| carried | P3 Polymarket reward quoting | Polymarket cash | - | - | - | not estimated | - | not estimated | one-snapshot upper bound 6-13% a day gross | not applicable | 400 (p <= 0.0025) |

Expected x by wallet (never summed across wallets): perp wallet 0.016 (S1 + S3 + S5), DEX slice 0.006, Kalshi and Polymarket slice 0.005, margin arm 0.048; the target needs 2.93 on one wallet. P(at least one of the five survives to a forward pass) is about 18% at these rates. The slate is therefore built for speed of verdicts and for what a pass would be worth: S2, S3 and S5 have N in the hundreds, so a survivor reaches its forward kill count in weeks and, if it is real at x near 1, its bar in under two years paired (bar 240 at x 1.08: floor 10.1 months); a survivor with x under 0.35 cannot be confirmed in a useful time (floor 25 months at bar 80) and is not given a ledger.

Template for every direction and every replacement: mechanism; the nearest closed family and the one difference; data with a run id or "probe first"; ceiling and cost arithmetic on paper; the gate's sd / cost line on paper; a stage-0 kill computed from counts, fees and book depth before any outcome is read; then at most one outcome-reading family, forward-only unless rule H2 is met.

### S1. Hyperliquid public liquidation ladder
- **Mechanism.** Hyperliquid shows every address's position, leverage and liquidation price. On a thin coin, a cluster of liquidation prices just beyond the market is a block of forced orders with a known trigger. The untested information class is "where forced orders sit", read before they fire, instead of a volume proxy after the fact (D1) or a blind resting bid (P1).
- **Next to (closed):** D1 (fade 60 s after a spike), P1 (blind resting orders), H2 (open-interest flush), Q1's Hyperliquid arm (wallet skill, closed for want of a historical frame). The one difference: the signal is the published ladder itself, forward-only, so today's address frame is enough.
- **Data.** Hyperliquid info API answered from Actions in the Q1 probe (run 45863435914); whether the trade stream carries both addresses, the request weight needed to refresh 2,000 addresses, and pod reach are **probe first**. Forward-only (no historical ladder).
- **Ceiling and cost on paper.** Taker both ways plus 0.15% slip is about 0.25-0.30% (fee read in the probe). At 3x, all-win needs net 0.74% a trade at N 50, so a cluster must be worth a gross move of about 1% once touched. Minimum order 10 USD: no notional limit at 147 USD.
- **Stage-0 kill (counts only).** Pod collector for 7 days, 30 coins outside the top 20 by volume: count approach events (mid within 1% of a ladder cluster whose notional is >= 3 times the visible depth to it). Kill if fewer than 30 a month extrapolated, if more than half come from fewer than 5 coins, if the ladder cannot be refreshed inside 60 s under the public rate limit, or if the 60 minute sd of those coins over the measured round trip is under 10.
- **Then.** Protocol locked before the first outcome: enter toward the cluster at the approach, take profit at the far end of the cluster, time exit 60 minutes (a 15 minute hold reads sd / cost near 8 at 0.28%, under the gate's 10), stop at entry - 1.5%; control = the same order at a random time on the same coin; cluster = coin-hour. Kill at 60 clusters if the net mean is <= 0 or the control is not beaten; bar 80.
- **First step.** The reach and rate-limit probe (one Actions run), then the pod collector. **Time.** 1 day to reach, 7 days to the counts kill.

### S2. DEX pools entering a public trending list, with exact AMM fills
- **Mechanism.** A pool that enters a public trending list receives buyers who arrive through that list. Pools with 20-100 thousand USD of liquidity are too small for funded players and large for a 49 USD clip. A constant-product pool gives an exact simulated fill from its reserves, which removes the fill-model doubt that voided other results.
- **Next to (closed):** the notice tape and D2 (exchange notices priced inside 60 s), L1 listings, L8/L9 daily gainers and losers. The one difference: the event is a list entry on a venue never tested, N is in the hundreds, and the fill is computed, not assumed. The 60 s finding is expected to bite here too; the probe measures it first.
- **Data.** A public pool-data API with trending lists, reserves and 1-minute pool candles (GeckoTerminal or DexScreener): **probe first** from Actions and the pod (rate limits, history depth). No keys, no chain node. Forward-only (lists have no history).
- **Ceiling and cost on paper.** No leverage, three slots of 49 USD: all-win needs net 1.1% a trade at N 300 or 0.33% at N 1,000. Round trip = 2 pool fees (0.25-1% each) + 2 price impacts (49 / reserve) + network fees: about 1.5-3.5%. The gate's sd / cost >= 10 needs an hourly sd of 15-35%, which such pools have; the open question is the mean.
- **Stage-0 kill (counts and costs only).** Poll for 3 days: kill if fewer than 100 entrants a month have a pool where the computed round trip is <= 3%, if the median delay between first sight and the previous poll exceeds 60 s, or if more than 20% of entrants show a pool with no sells from distinct wallets in the prior hour (a pool that cannot be exited makes a simulated sale false).
- **Then.** Protocol locked before any candle is read: buy at first sight + 30 s at the reserve price plus impact, holds 15 and 60 minutes, exit at the reserve price; control = pools of matched age and liquidity not on the list at the same minute; cluster = UTC hour. Kill at 200 clusters if net mean <= 0 or the control is not beaten; bar 240.
- **First step.** The reach probe. **Time.** 1 day reach, 3 days counts, about 2 weeks to 200 clusters.

### S3. Tokenized stock, index, FX and commodity perps against the real underlying
- **Mechanism.** MEXC and Gate listed hundreds of perps on stocks, ETFs, indices, FX pairs and commodities in 2026 (P4 step 1: 386 of 852 test clusters are named STOCK, many more are bare tickers such as AAPL, EURUSD, GOLD). Their fair value is printed elsewhere every second, and closing the gap properly needs a broker leg that a crypto desk does not have, so a gap between the perp and the real price can last minutes on a book too thin for a funded player. The trade is one leg: the perp, toward the real price, flat within the hour.
- **Next to (closed):** H1 perp-against-index snapback on Binance (-0.075% on 35,018 test events), P4 on the same instruments (a 7-day short, sd 13.7%), P2 (never run). The one difference: the anchor is an external regulated price, on venues and instruments no earlier family priced intraday.
- **Data.** MEXC and Gate futures 1-minute klines: answered in the P4 step-2 run (`data/p1p4/p4_step2`, 490 and 308 clusters priced; MEXC serves the latest months only). Underlying: Yahoo 1-minute (probes 45754281422 and 45754840324: 65 of 65 bars for AAPL from the runner; 7 days of history, 5-minute bars for 60 days; bulk small-cap pulls answered 429, so at most 40 large underlyings). Top of book and fee schedule of the two venues: **probe first**.
- **Ceiling and cost on paper.** At 3x notional (the gate's w) all-win needs N ln(1 + 3 (g - c)) >= 1.10: with c = 0.28% (the P4 cost) that is a mean captured gap of 0.65% at N 100 or 0.40% at N 300. The gate also needs sd of gross / cost >= 10: an hour of a stock perp has sd near 1%, so at c 0.28% the ratio is about 3.6 and **the direction fails unless the measured round trip is near 0.10%**. That one number decides it.
- **Stage-0 kill (counts, fees, depth; no P&L).** One probe run over the 40 underlyings with the most perp volume, regular sessions of the last 60 days at 5 minutes and the last 7 days at 1 minute: (a) measured round trip = 2 taker fees + median quoted spread for 150 USD; kill if hourly sd / round trip < 10; (b) count episodes with |perp / underlying - 1| >= round trip + 0.37% lasting 2 bars; kill if fewer than 100 a month or more than half from fewer than 5 symbols; (c) kill if the median gap is the same sign for the whole session in more than half the symbol-days (a standing funding basis, not a convergence).
- **Then (forward-only).** One protocol locked before the first outcome, one gap threshold and one hold, control = random-time entry on the same symbol and side, cluster = symbol-hour, N capped by the wallet. Kill at 200 clusters if the net mean is <= 0 or the control is not beaten; bar 480.
- **First step.** The probe above. **Cost.** One counts module with offline tests, one Actions run. **Time.** 2 days to the kill.

### S4. Same event on Kalshi and Polymarket, locked spread, resolving within 48 h
- **Mechanism.** Both venues list the same daily crypto level, temperature, sports and data-release events. Buying YES on one and NO on the other for less than 1.00 in total after fees locks the difference with no forecast. Funded players need size; a 20 USD pair does not. This is structural, not a forecast (the closed class).
- **Next to (closed):** poly_fv, Thin B, L4, the temperature model (all forecast or fair-value), FB1 (basket sums inside Polymarket, unwritten). The one difference: two venues, one event, both legs held to a resolution at most 48 h away.
- **Data.** Polymarket gamma and CLOB books (run 45884810025). Kalshi public market and book endpoints answered in earlier runs per `PLAN_20261126b_fable.md`, no run id on record: **probe first**, with the fee schedule.
- **Ceiling and cost on paper.** Capital turns are at most 15-30 a month, both legs funded. A standalone 3x needs 3.73% a day locked on the whole wallet; 0.5% a day is a 1.16x month as a component. With a fee of 1-2 cents a contract on one leg, the quoted gap must be about 5 cents at mid prices for the standalone case.
- **Stage-0 kill (one snapshot run, repeated hourly for 2 days; no outcome).** Match pairs by a locked rule (same underlying, level, date and resolution hour; the resolution source of each is stored); compute the locked return after fees for 20 USD a pair at the top of both books. Kill as a standalone if the best 147 USD allocation locks less than 3.73% a day; kill completely if under 0.5% a day, under 10 matched pairs a day, or if more than 20% of matched pairs name different resolution sources.
- **Then.** Forward tape with trade-through fills only (the P3 lesson), control = the same pairs with the legs taken at mid; unit = a UTC day. x and sd / cost do not apply to a locked spread; the measures are locked return a day on the capital used and the realised loss from resolution mismatches. Kill at 14 days if the net locked return is <= 0; bar 800.
- **First step.** The matching and snapshot probe. **Time.** 3 days to the kill.

### S5. Stale quote on the slow venue after a jump on the fast venue (absorbs P2)
- **Mechanism.** The same thin coin trades as a perp on several venues. When one book jumps 1% in a second, the others' quotes follow with a delay; a 147 USD taker fits inside a top of book that a funded desk ignores. P2 (gaps on 1-minute closes) is this idea at bar resolution and becomes its historical arm.
- **Next to (closed):** H4 (BTC leads alts on bars, same venue), D2 (notice at +60 s), Q2 (notices at seconds, about 5 a month). The one difference: the trigger is a price jump on another venue's tape, hundreds a month, measured in seconds on the pod.
- **Data.** Bar arm: the venue loaders of L1f venues and P4 (OKX, Gate, MEXC, KuCoin futures; recent months only on several). Seconds arm: pod websockets; OKX is reachable from the pod (it polls OKX every 3 s), Binance market data from the pod and the slow venues' sockets are **probe first** (Binance API answers 451 from Actions).
- **Ceiling and cost on paper.** One leg on the slow venue at 0.28%: all-win at 3x needs a captured gap of 0.46% at N 200. So the measure is the gap still open at our latency, net of 0.28%.
- **Stage-0 kill (no rule P&L).** (a) Bar arm, counts only (the P2 step): events with |ln(Pa / Pb)| >= 1.5% on two consecutive 1-minute closes with volume on both; kill the bar arm if fewer than 60 a month or more than half from fewer than 5 symbols. (b) Seconds arm, 7 pod days: at each 1 s jump >= 1% on the fast venue, store the slow venue's best bid and ask at +0.5, 1, 2 and 5 s; kill if the median gap still open at +2 s is under 0.56% (2 x cost) or there are fewer than 100 jumps a month with a slow-venue quote. (c) The gate line: sd of the slow venue's return over the planned hold after a jump, over the measured round trip; if it is under 10 at 1% jumps, raise the jump size until it is 10 and recount (b) at that size; kill if no size keeps 100 jumps a month.
- **Then (forward-only).** One protocol for the surviving arm; control = the same entry at a random time on the same pair; cluster = coin-hour. Kill at 200 clusters if the net mean is <= 0 or the control is not beaten; bar 1,200.
- **First step.** Bar-arm counts run on the existing loaders; pod reach probe for the sockets. **Time.** 2 days for (a), 8 days for (b).

### Carried, not new
- **L1f margin arm.** The recorder is live on `data/l1f-margin` (heartbeats only so far). It must show, per notice: a borrowable flag and rate at the notice, a short filled on the spot book at +60 s, and after 10 notices a mean above 0 with borrowable share >= 50%; otherwise it is closed. About 1.15 events a month means the first reading is in about 9 months; nothing is added to the book before it. No other exchange joins it (Bybit: x 0.73 in-sample but the ceiling is 1.95x and the test split is -2.6% on n 9).
- **P3.** Merge the honest tape (PR #283), run as locked: 14 days can only kill, 60 days for a verdict against the matched no-reward control.
- **`notice_fwd` and the event book.** Run as locked; read the per-source lag at 20 notice rows; no new feed work.

## 4. Stop spending compute on (adds to the two earlier lists)
1. **Any historical family whose prior x times holdout months is below z^2** (rule H2): every notice family at 1-5 events a month, including Q2 test 1 and a rerun of L1f, fut_delist or mon_tag on history.
2. **Q1 and every wallet-follow variant** (other ranking windows, maker rows, other venues): the gross edge of ranked wallets is below that of random wallets.
3. **Q3 stage A, the P1 follow-through side, and any stop or threshold variant of P1 or D1**: section 1: the reverse side is positive per cluster in 0 of 18 train, 0 of 18 validation and 4 of 18 test cells, before stop-order slip.
4. **Q4 and any wire-release rule**: 104 s median lag at the pod.
5. **Other exchanges' spot delists as margin shorts** (Bybit, OKX, KuCoin, Bitget, Gate, MEXC): one passed nothing, five are unreachable, and none can be verified for borrow.
6. **Model comparisons for news.** Sonnet against Haiku showed no direction difference (stock sign test 30 against 29); Sonnet's faster call (about 2.2 s against 3.5 s) does not matter when no text edge exists. The forward arm finishes as locked; the bot stays on Haiku.
7. **Faster notice feeds** beyond what PR #281 shipped, until `notice_fwd` has 20 notice rows per source.
8. **Post-hoc slices of dead families** unless they outrank the queue (rule S, point 2): the coin-only P4 rerun, Bybit delists with a relaxed ceiling, a Sonnet-only news rule.
9. **Quoting coin-level, fill-level or single-snapshot figures as x or as a return** anywhere in STATUS, RESULTS or a session report.

## 5. The live bot and the review findings
- **Tag rule (owner, 2026-11-27).** A protocol tag stays unchanged until it has **>= 30 closed pairs or >= 4 weeks**, whichever comes first. The weekly loop (`bot_weekly.yml`) keeps running but only files proposals; they are applied together at the next tag. At the cap of 3 entries a day, 30 closed pairs take at least 10 trading days, so the count can be reached.
- **One fix tag now.** PR #282 (v4.20) is the place for the review's code findings; before merge it must show a failing test first for each of: scale-in widening the stop of the whole position (High 5), adds to the 7 grandfathered positions bypassing the limits (High 6), the drawdown brake resetting its peak, the daily loss halt lifting on a bounce, R6 ignoring leverage, R8 dodged by a null, and a USDC-perp delist of a large coin read as a forced short. The tag clock starts at that deploy.
- **Rules from seen data (High 3).** A tag's rules are judged only on pairs closed after its deploy, against the random control, by the locked criterion (30 pairs, positive model mean, positive paired difference, bootstrap p < 0.10). The bot ledger keeps its small share of forward weight (section 2); it is not a research component.

| Review finding | Where this plan answers it |
|---|---|
| High 1: 0.33 mixes coin and notice level | section 1 (0.18, confirmed 0); section 4 item 9 |
| High 2: plan stale, Q1 dead, no stage-1 candidate | section 1 dispositions; section 3 |
| High 3: bot can never get a verdict | section 5 tag rule |
| High 4: margin 2.23 is coin level and in-sample | section 1 "not in the baseline"; carried item |
| High 5, 6 and the five bot mediums | section 5, PR #282 |
| Medium: P3 pass rests on one snapshot and touch fills | section 1; carried item (PR #283) |
| Medium: no multiple-testing control | section 2 |
| Medium: components add, capital free | section 1 last bullet; the Wallet column of 3.2 |
| Medium: STATUS.md stale (DeepSeek, local timers) | lane D below |

## 6. Staged path and order of work
"Nominated" and "confirmed" as in section 2. A stage is reached when a component is nominated on history or, for a forward-only component, survives its forward kill count with a positive mean above its control; it is kept only if confirmation follows.

| Stage | Median month | Book x | What has to be true | Earliest |
|---|---|---|---|---|
| 0 (today) | 1.00x confirmed (1.07x unconfirmed) | 0 (0.18) | the event book takes its first trades | running |
| 1 | 1.3x | 0.70 | one of S1-S5 or a replacement survives its counts kill and its forward kill count with a forward x >= 0.7, or two at 0.35 | counts kills in 2-8 days; forward ledgers of the survivors inside 2 weeks; forward kill counts (60-200 clusters) in 2-6 weeks after that; confirmation floor 12.5 months at bar 80 and 15.7 at bar 240, about twice that when paired |
| 2 | 1.5x | 1.08 | a second independent component; daily P&L correlation inside +-0.1 | after stage 1 |
| 3 | 2x | 1.85 | three or four components, or a confirmed stage 2 moved to 0.75 Kelly by a new dated protocol | after stage 2 is confirmed |
| 4 | 3x | 2.93 | stage 3 confirmed and a component with N >= 100 a month at s >= 0.1 | not datable from today's evidence |

| Lane | Now | Next |
|---|---|---|
| A. Probes on Actions, outcome-free | S3 fee, spread and gap counts; S5 bar-arm counts; S4 matching snapshot; S1 and S2 reach probes | the one forward protocol of each survivor |
| B. Pod collectors, outcome-free | S1 ladder counts (7 days); S5 seconds arm (7 days); S2 list poll (3 days) | forward ledgers of the survivors, weights by rank (section 3.2) |
| C. Forward, as locked | event book, `notice_fwd`, L1f margin recorder, P3 tape after PR #283 | readings at their locked counts |
| D. Book keeping | `research/studies/FAMILIES.md` (families and ledgers numbered, weights fixed); rewrite `reports/STATUS.md` (Claude Haiku, Actions and pod only, no local timers, x 0.18 unconfirmed); report k, alpha_k and the master e-value each session | bot reading at 30 closed pairs or 4 weeks under v4.20 |

Rules kept: one dated protocol each, locked before the first outcome; one run and at most one dated fix, each counted as a family; simulated money, public endpoints, no keys; nothing runs on the owner's computer (Actions and the pod only); every LLM call is Claude Haiku; "not found" goes to `RESULTS.md` and `LESSONS.md` the same day, and the direction is replaced from the idea queue under the section 3 template.
