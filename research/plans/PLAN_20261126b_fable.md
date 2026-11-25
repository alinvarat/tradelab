# Plan 2026-11-26b (Fable strategy review 3): after D1-D4, what is structurally left

Goal unchanged: a simulated 147 USD account reaches >= 3x in 30 days after costs, beats a random control, rules locked before data.
Status: plan only. No data was run for this file. Every number not quoted from `research/studies/RESULTS.md`, `research/LESSONS.md` or `reports/LEADERBOARD.md` is a **prior**, and is labelled so.
Leaderboard today: 1,089 sweep rules tested, **0 passed**; closest `fundwin2/fw[thr=0.005,mode=fade_payer,entry=-60,exit=15,delay=0]` (9 of 10 criteria; its signal had look-ahead). With hand-built rules and event families: more than 1,300 tested, 0 passed.
Supersedes section 2 (D1-D4) and section 5 of `PLAN_20261126_fable.md`. Its sections 1, 3 and 4 (diagnosis, stacking arithmetic, L1f handling) and the process rules of `PLAN_20261125_fable.md` stay.

## 1. What the measurements say (structure, not a verdict)
Arithmetic kept from the earlier plans: monthly x = N * s^2 at cluster level; a median 3x month at half Kelly needs x about 2.9 (growth = 0.375 x), which is a monthly Sharpe of about 1.7.

1. **Tradable, cluster-level, measured x is 0.33 in total** (l1f on Binance perps 0.19 with a negative train mean, fut_delist 0.13, mon_tag 0.005). That buys a median month of about 1.13x at half Kelly. The required 2.9 is about nine times larger.
2. **Every s above 0.3 failed one of three audits.** Not tradable at the event time (L1f 1.98 on spot rows -> 0.19 where a perp exists; Thin A MEXC-only winners), selected in-sample (4 h hold of L1e/L1f), or a code/look-ahead bug (fundwin2, L8, L4 run 3, momentum on a 2026 universe).
3. **A public notice is priced inside our 60 s.** D2: gross move after a KRW listing notice is about zero from +60 s (train -0.08% to -0.22% net). Notice tape: 0 of 192 cells. D1: the fade from 60 s after a volume/taker spike has zero gross edge on 21,821 events (net = minus the 0.41% cost). The forced-flow that does persist (mon_tag +2.7%, fut_delist +6.2%) arrives 2-3 times a month.
4. **Slow public features do not time anything.** D3: delist hazard is 0.04-0.7% per coin-day against the 10% bar; the tag leads the delist by a median of 54 days. D4: 13 train clusters.
5. **My priors overshoot.** D1-D4 "after haircut" priors were 0.15-0.5, 0.15-0.5, 0.05-0.2, 0.05-0.15. Measured: negative, about zero, negative in test, too few events. From now a pure prior is multiplied by 0.25 (not 0.5), a lead with a measured positive validation and test mean by 0.5, and a measured lead is always tried before a prior of similar size.
6. **What therefore has to be different** (these three properties select section 3):
   - **Fills that do not depend on reaction time.** An order that rests before the move, or income paid for resting, removes the 60 s handicap. A faster reaction to a notice does not: Actions/Kuber polling cannot get under seconds.
   - **Places too small for funded players.** The one structural advantage of 147 USD is that a venue, pool or book that can absorb only a few hundred USD is still large for us. Every liquid instrument tested was efficient at our cost.
   - **Data that has no history.** Books, reward pools, liquidation prints and borrow flags cannot be backtested (D1 probe: OKX keeps hours, Binance Vision has no USDT-M liquidation file). Those tests are forward tapes with rules locked now; they run in parallel with the backtestable lanes and nobody waits for them.

## 2. The six approach classes named in the brief: disposition
| Class | Already measured | Disposition |
|---|---|---|
| Payoff convexity (options, short-dated leverage) | opt_vrp: 16 of 16 stopped at the ceiling, at most 0.94 episodes a week. Sixfold weekly BTC/ETH option oracle: with perfect foresight 3x in 11 of 22 months. LESSONS trap 6: 20x gives 6x in 18-25% of months and a wipe in 54-66%. DVOL strangle and LLM-options forwards are running, locked. | **Not a source of edge.** Convexity leaves x = N s^2 unchanged; it moves only the ceiling half of the gate and the share of months that end >= 3x. With zero edge that share is at most 1/3, and at most 23% with the 0.4x halt, before costs. Use it as the sizing layer of whatever book exists and judge it by the hit-rate gap against a zero-edge control with the same payoff shape (the cohort table of `PLAN_20261125_fable.md`). No new option study; the two forwards finish as locked. |
| Market making, maker rebates | H3: passive quotes 1-8 ticks from the last trade, net negative in every split, worse than the time-reversed day. L4: selling 2-10c long shots as an assumed maker is break-even. | Near-touch quoting is closed. Two shapes are untested: being **paid** to quote (N1) and **deep** resting orders that only fill inside a forced move (N2). |
| Cross-venue basis | H1 perp-vs-index snapback decayed to -0.075% on 35,018 test events. Funding-window fades are real but small (fundwin3 x 0.27, ceiling 1.68x); the OKX funding ledger is running. Thin A F2 stores spot gaps only, and spot gaps need transfers. | Same-venue basis is closed. Perp-against-perp across venues on thin coins is untested (N4); the ceiling half is the likely limit. |
| Prediction markets with an informational edge | polymarket_llm no edge; poly_fv 0 of 54 on 862,575 rows; Thin B B1 -6.2%, B2 -6.9%; NYC temperature model 0 of 32 in 2025 and 0 of 15 on fresh 2026 quotes; F1 menu oracle 3x in 3 of 22 months. Baskets B3/B4/B6/B7 have no data yet; collector FB1 is registered and not written. | Forecast-type edges are closed (model, fair value, LLM, weather). What is left is structural: reward income (N1) and synchronous basket sums (FB1), both read from one book tape. |
| New-listing perps on small venues | calendar_flow R2 (short a new Binance perp in its first week, BTC-hedged): train +4.75% (n 159), validation +3.39% (n 230, p 0.018), test +1.94% (n 511), beats the control, positive at double cost; failed Bonferroni and the frequency gate, best month 1.45x. L1c and KuCoin/OKX listing notices: nothing. | The only lead with positive validation and test and no audit failure. Re-measure at cluster level and replicate on other venues (N3). |
| Forward-only collection | Running: event book, OKX funding ledger, L4f, crypto spikes, options, LLM earnings, Thin A F1-F3 (last write 2026-11-25 18:23 UTC). Registered, not written: FB1. Not started: real liquidation prints, borrow flags. | Add only tapes that have a locked rule waiting for them: the Polymarket book tape (N1 + FB1) and, if N2 clears its backtest, an OKX book/liquidation tape. |

## 3. Next directions, ranked by expected x after the section 1 haircut
Both halves of the gate are stated for each (x >= 0.2 at cluster level, and an all-win ceiling >= 3x a month at the size 147 USD can reach). Reachability is quoted from a past Actions run or marked "probe first". Live Binance API answers 451 from Actions; `data.binance.vision`, OKX, Polymarket gamma/clob/data API and Kalshi answered in earlier runs; Bybit API, Upbit and BitMEX are blocked.

| # | Direction | Evidence type | x after haircut | Ceiling half |
|---|---|---|---|---|
| N1 | Paid-to-quote on Polymarket reward markets (+ FB1 baskets on the same tape) | prior | **0.2-0.7** | unknown; it is kill test 1 |
| N2 | Deep resting orders on small perps (fill inside the wick, not after it) | prior, backtestable now | **0.05-0.25** | passes (perp leverage) |
| N3 | New-perp first-week short, pooled over venues, cluster level | measured lead | **0.05-0.15** | binds at 2 wallet units |
| N4 | Perp-against-perp gap convergence across venues, thin coins | prior | **0.05-0.2** | borderline |

Sum at the ends: 0.35-1.3, plus the measured 0.33 = **0.7-1.6**; a median month of 1.3x-1.8x at half Kelly if everything at the top end held, which section 1 item 5 says not to expect. N1 is first because it is the only shape here whose income is daily and does not come from predicting price, so it is the only one that could carry x >= 1 alone.

### N1. Paid to quote: Polymarket liquidity-reward markets
- **Mechanism.** The venue pays a fixed daily pool per market to orders resting inside a maximum spread, split by a published score. A pool of a few USD a day is not worth a funded desk's attention, so the share earned by 147 USD can be large relative to the capital. The income needs neither speed nor a forecast. The cost is being filled just before news (the H3 finding) and holding that inventory.
- **Gate on paper.** No leverage, so the ceiling half is direct: reward income / capital deployed must reach 3.73% a day (3^(1/30) - 1) before any fill loss for a standalone 3x; at 0.5% a day it is a 1.16x month. x prior: daily net 0.2-0.5% on a daily sd of 1-2% gives raw x 0.3-7; the wide top is the reason for the 0.25 haircut and for doing the probe first.
- **Data.** Gamma market lists and the data API trade feed answered from Actions (runs 45519602631, 45523514648). The reward fields per market and the CLOB book endpoint are **unverified: probe first**.
- **Kill test.** (1) Probe, one run, no P&L: snapshot every rewarded market's reward rate, maximum spread, minimum size and the book inside that spread; compute the share a two-sided minimum-size quote would earn. Kill as a standalone if the best 147 USD allocation earns < 3.73% a day gross; kill completely if < 0.5% a day or fewer than 10 markets qualify. (2) Forward tape for 14 days, one-minute snapshots of the 50 markets with the highest reward per USD of resting size, protocol locked before the first row: fixed quote rule; **we are filled in full whenever a trade prints at or through our price**; inventory marked at the bid; inventory older than 24 h is sold at the bid. Controls: the same quotes with the reward set to zero (isolates adverse selection) and the same rule on matched markets without rewards. Kill if the daily net mean is <= 0, if s per day < 0.08 (x < 0.2), or if the reward does not cover the zero-reward control's loss in validation days.
- **Cost.** Probe: one short run. Collector: one module and one keeper line; it also delivers FB1 (basket sums from the same snapshots), which is registered and unwritten. No LLM.

### N2. Deep resting orders on small perps
- **Mechanism.** D1 measured a taker who arrives 60 s after a one-sided burst and found nothing. The untested side is the order that was already resting: a bid d% below the price of two minutes ago is filled only when a forced seller trades through it, and it gets the wick price instead of the price a minute later. Latency does not matter because the order precedes the event. H3 warns that fills precede further moves; the test measures exactly that, since a bar that keeps falling is a filled loser.
- **Gate on paper.** Prior 30-80 market-wide clusters a month, net +0.3-0.8% on sd 4-6%: raw x 0.1-1.0. Perp leverage of 5-10x is reachable, so the ceiling passes.
- **Data.** `data.binance.vision` USDT-M 1-minute klines for the 888 small perps of D1 (run 45672776669: 16 shards, 0 failed months); aggTrades for a 5% audit sample.
- **Kill test.** One family, 18 cells, Holm: d in {3, 5, 8}% x hold {1, 5, 15} min x side {bid, ask}. Reference = close of bar t-2; order live in bar t; filled at the limit only if bar t trades at least 0.1% through it and has >= 5,000 USDT volume; exit at the open of bar t+1+hold; 0.40% round trip + funding as D1; 5% stop on later bars. Controls: the D1 late taker on the same bars (what the resting fill adds) and the follow-through side from the same price. Cluster = all fills in one UTC hour. Kill if the train net mean is <= 0, if cluster-level x < 0.2, if the rule does not beat the late-taker control by >= 0.2% a trade, if > 50% of train profit comes from the best 1% of fills, or if the aggTrades audit shows less than 5 clips of 30 USD traded below the limit in more than 20% of sampled fills.
- **Cost.** One fill module with offline tests, one sharded run on the D1 loader. If it clears: an OKX book + liquidation-print tape on 30 thin perps as the forward confirmation (OKX `liquidation-orders` answered in probe 45670184510).

### N3. New-perp first-week short, pooled over venues
- **Mechanism.** A new perp opens with one-sided long demand and no borrow; early holders and market makers sell into it over the first week. R2 is positive in train, validation and test but decays (+4.75%, +3.39%, +1.94%).
- **Gate on paper.** sd was never read. If it is 25-35%, s is 0.06-0.14 and coin-level x is 0.07-0.2 (about 10 events a month in validation, 23 in test). The 7-day hold with 2 wallet units caps the usable N near 8 a month, and the best validation month was 1.45x: the ceiling half binds unless the hold shortens.
- **Data.** Step 0 needs no new data: read sd, by-year means and the monthly counts from the rows of run 45556054691. Other venues: use the coverage output of the running `protocol_l1f_venues_20261125.md` probe (OKX, Gate, MEXC, Bitget, KuCoin futures, Hyperliquid); do not probe them again.
- **Kill test.** (0) Kill if coin-level x < 0.15 or the 2026 mean is <= 0. (1) Counts only: first-bar dates of perps on the non-Binance venues, one cluster per coin (first venue to list); kill if < 60 clusters that Binance did not list in the same week. (2) New dated protocol, rule V1 unchanged, non-Binance clusters only (an out-of-sample replication, no retuning of the Binance rows). Kill if the mean is <= 0, if it does not beat the random-perp control, or if x < 0.2 with N capped by the 2-unit wallet.
- **Cost.** Step 0 is a read. Steps 1-2: one protocol and one run on loaders that the L1f venues work already built.

### N4. Perp-against-perp gap convergence across venues
- **Mechanism.** The same coin trades as a USDT perp on several venues with separate books, separate liquidation engines and separate funding. On thin coins a forced move on one venue opens a gap that needs no transfer to trade: short the dear perp, long the cheap one.
- **Gate on paper.** 147 USD split over two venues at 5x each is 2.5x notional; the ceiling needs N x net >= 44% a month (for example 60 trades at +0.73% net after four taker legs). That only exists if gaps of >= 1.5% that last two bars are common. Persistent gaps are usually the funding difference, not free money.
- **Data.** 1-minute klines per venue, from the L1f venues coverage output. Synchronous quotes do not exist historically.
- **Kill test.** (1) Counts only: non-overlapping events with |ln(Pa/Pb)| >= 1.5% on two consecutive 1-minute closes with volume on both venues. Kill if < 60 a month, or if more than half come from fewer than 5 symbols (the Thin A ticker-collision trap). (2) One protocol: thresholds 1.0% and 2.0%, exit at |gap| <= 0.2% or 8 h, cost 0.64% for four legs plus the venues' funding difference, control = random-time entry on the same pair and hold. Kill if train mean <= 0, control not beaten, or x < 0.2. (3) A pass is provisional until a dated addendum to Thin A F2 stores synchronous perp top-of-book gaps for 4 weeks.
- **Cost.** One counts run, then one protocol; no new infrastructure beyond the venue loaders.

### Still open, unchanged
- **L1f on reachable venues:** read the `protocol_l1f_venues_20261125.md` result when it lands; a qualifying set enters the book only by dated addendum. Prior for the non-Binance set: x 0.05-0.15. Margin borrow stays a labelled upper bound; log the public borrowable flags at each notice from now on.
- **Forward tests** (event book, OKX funding ledger, L4f, spikes, options, LLM earnings, DVOL, Thin A): finish as locked. They cost nothing new and take no new compute.

## 4. Stop spending compute on
1. **Any new rule on bars of liquid instruments**: indicators, breakouts, trend, mean reversion, session and calendar rules on majors, FX, gold, index ETFs, US large caps. 1,089 sweep rules plus indicators_1 (0 of 54), fxcom_1, fxgold_tick (179 of 180 train cells <= 0), factory 1-3.
2. **More sweep families over the same Binance perp panel** (funding-window, crowd, taker, mix, price-action variants). The best honest ones sit at x 0.2-0.27 and are stopped by the ceiling; the OKX ledger already tests the funding one forward.
3. **Reacting to a public notice at +60 s or later**, any exchange, any direction: listings, delists, tags, cautions, futures launches (notice tape, forced-flow 0 of 54, D2 0 of 9, L1c, L1g). This includes more Wayback scraping of Upbit, Bithumb and Bybit.
4. **Pre-notice hazard baskets and tag-based timing** (D3, D4), and the volume-spike liquidation proxy with other thresholds (D1).
5. **Forecasting prediction-market outcomes**: LLM forecasts, digital fair value, thin favourites, jump-follow, long-shot selling, temperature models.
6. **LLM readers of US filings and news as a trade trigger** (N1 news_v3 H5 -1.39%, non-earnings 8-K -1.81%, wide earnings no edge at H1). The locked earnings and options forwards finish; no new reader.
7. **Defined-risk option selling and any new option backtest** (ceiling and oracle results above).
8. **Small-cap US intraday and gap shorts** (L7, L10, smallcap_intraday) and same-venue basis snapback (H1).
9. **Near-touch passive quoting on trade prints** (H3). N1 and N2 are different fills; they are not a licence to rerun H3.

## 5. Order of work (parallel lanes, none waits for another)
| Lane | Now | Next when it finishes |
|---|---|---|
| A. Sharded backtest | N2 protocol + fill module, one run | N4 counts run as soon as the L1f venues coverage exists |
| B. Forward tape (keeper) | N1 probe; if it clears, lock the N1 protocol and start the 14-day tape with FB1 | N2 OKX book/liquidation tape only if lane A clears |
| C. Reads, no data | N3 step 0 (sd and by-year from existing rows); L1f venues result | N3 counts and replication protocol if step 0 clears |
| D. Book keeping | A component enters the event book only by dated addendum with its own unit budget | Cohort hit-rate table against the zero-edge control once any component is added |

Rules that apply to all four: one dated protocol or sweep config each, locked before the first price; one run and at most one dated fix; x counted at cluster level on instruments tradable at the event time; simulated money, public endpoints, no keys; Claude Haiku only if an LLM is ever needed (none is here); "not found" is a valid result and is written to `RESULTS.md` and `LESSONS.md` the same day.
