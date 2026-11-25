# Plan 2026-11-26 (Fable strategy review 2): after 1,300 rules and 0 passes

Goal unchanged: a simulated 147 USD account reaches >= 3x in 30 days after costs, beats a random control, rules locked before data.
Status: plan only. No data was run for this file. Every N, s and x below that is not quoted from `RESULTS.md` is a **prior from first principles**, not a measurement.
Leaderboard today (`reports/LEADERBOARD.md`): 1,089 sweep rules + more than 60 hand-built rules + the event/notice families = more than 1,300 tested, **0 passed**. Closest: `fundwin2/fw[thr=0.005,fade_payer,-60,15]` (9 of 10 criteria; its signal had look-ahead, and the fixed `fundwin3` drops at the gate with x 0.27).
Supersedes section 1 estimate and section 3 ranking of `PLAN_20261125_fable.md`; its process rules (sections 4, 5) stay.

## 1. Diagnosis
Math: monthly x = N * s^2. Median 3x month needs x >= 2.2 at full Kelly, **2.9 at half Kelly** (growth = 0.375 x). The book rule is half Kelly, so 2.9 is the real bar.

1. **Cost against edge.** Round trip is 0.14% (perp taker) to 0.6% (event fills). Liquid-market rules gave gross means of 0.05-0.3% a trade. indicators_1: 0 of 54, 15m/1h cells lose mainly to cost. fxgold_tick: 179 of 180 candle cells had a train mean <= 0 at XM spreads, every cell x < 0.1. A rule needs gross mean >= 3x cost before it can reach s 0.1.
1b. **Fair-value models add nothing after fills.** poly_fv: 862,575 candidate rows, calibration correct, 0 of 54 at stage 0, best train x 0.24 on 14 trades (test -19.5%). The market price already equals the digital fair value inside the fee and the spread.
2. **Low N where s is high.** The only rows with s > 0.3 are exchange-notice jumps, and those come 1-3 times a month. L1f needs s 0.85 to make x 2.2 from 3 events; nothing tradable has s above 0.4.
3. **The large s was not tradable.** L1f 1.98 (spot-priced, 105 rows) became 0.19 on the 65 coins with a Binance perp. The implied mean of the 42 no-perp coins is roughly +30% in 4 h (a rough inference: the two figures come from different engines and price sources). Most likely reading: the drop is large *because* nobody can short it; where a short exists, arbitrage already took the edge. Same shape in L12 -> L12b and in Thin A (MEXC-only lottery winners).
4. **Cluster-level N is much lower than coin-level N.** mon_tag: x 0.18 per coin, 0.005 per notice. fut_delist: 0.27 -> 0.13. Our x sums double-count correlated trades.
5. **Liquid markets are efficient at our latency.** With a 30-60 s reaction and taker fills, anything visible in 1 h bars of BTC, gold, EURUSD or SPY is priced. H1 worked in 2023-24 and decayed to zero by 2026. H4 gain over random was 0.1% against 0.3% cost.
6. **Selection.** 1,300 rules on the same 2024-26 window. Every near-pass (fundwin2, L8, A1/A2, momentum on a 2026 universe) died on a look-ahead, formula or survivorship audit. Expect any new in-sample x to halve forward; the repo's own worst case is a 10x shrink.
7. **The gate has two halves.** x >= 0.2 and an all-win ceiling >= 3x at the leverage a 147 USD account can get. Low-volatility ideas (ETF close flows, near-resolved prediction markets, cross-venue funding carry) fail the second half on paper even with a real edge.

Consequence: stop screening price-pattern rules on liquid instruments. Only two shapes can still clear both halves: (a) forced one-sided flow in thin instruments where our latency is enough, (b) high-N forced flow with gross move >= 1% a trade.

## 2. Directions not yet tried (ranked by haircut x)
All: data reachable from Actions, orders >= 5 USD, entry no earlier than 60 s after the event, instrument must have a bar before the event, N counted per cluster (notice or coin-day), one dated protocol or sweep config each, one run and one fix.

| # | Direction | N a month (cluster) | s | x raw | x after haircut |
|---|---|---|---|---|---|
| D1 | Liquidation-print fade, small perps, 5-60 min | 40-100 | 0.08-0.15 | 0.26-2.25 | **0.15-0.5** |
| D2 | Korean on-ramp listing notice, long the global perp | 6-10 | 0.2-0.35 | 0.24-1.2 | **0.15-0.5** |
| D3 | Delist-hazard timing short (pre-notice, perp coins) | 3-5 coin-days | 0.2-0.3 | 0.12-0.45 | **0.05-0.2** |
| D4 | Tag-removal and survivor-relief long (spot-capable) | 0.7-1.5 | 0.3-0.5 | 0.06-0.38 | **0.05-0.15** (below the 0.2 line) |

x raw = N * s^2 at the ends of the prior ranges. Haircut = at least half off, more where the upper end needs both a high N and a high s (D1) or an unproven condition (D3).

### D1. Liquidation-print fade at minute horizon
- **Forced trader:** the exchange liquidation engine, which sells or buys at market into a thin book regardless of price. H2 (OI-flush proxy, 1 h delay, 1-7 day hold) and the wick rule on six majors failed; real liquidation prints on small perps at 5-60 minutes have not been tested.
- **N, s:** a cluster = one instrument and 5-minute window with liquidated notional above a multiple of its median 5-minute volume. Prior 40-100 independent clusters a month after merging market-wide cascade days. Overshoot 1-3%, half reverting: gross +0.5-1.0%, cost 0.10% fees + 0.1-0.3% spread, net +0.2-0.5%, sd 2.5-3%, s 0.08-0.15. Kelly leverage about 4-5x, reachable; ceiling passes. Main risk: adverse selection (liquidations happen inside trends; the H3 lesson).
- **Data:** OKX public `GET /api/v5/public/liquidation-orders` + OKX 1-minute candles and tickers for the spread; `data.binance.vision` USDT-M `liquidationSnapshot` for history. Depth of both is **unverified**.
- **Kill test:** (1) counts-only probe of both sources; kill the backtest route if < 200 clusters on >= 30 instruments, and go forward-only through the keeper. (2) One family: 2 size thresholds x 3 holds (5, 15, 60 min), fade, entry 60 s after the cluster's last print at the opposite side of the book. Kill if the train net mean <= 0, if it does not beat the same-time follow-side placebo, or if cluster-level x < 0.2.

### D2. Korean on-ramp listing notices (Upbit KRW, Bithumb KRW), long the global perp
- **Forced trader:** market makers and arbitrageurs who must source inventory abroad before the KRW market opens (closed market, retail can only buy on venue), plus shorts squeezed on the global perp. L1 planned this and never got data (Upbit 403 from Actions and from Kuber); the notice tape covered only KuCoin/OKX listings, which move nothing. This is the historical backtest of the L1b line and of queue item 2c in `reports/STATUS.md` (more listing sources), not a second collector: check that item's owner before building.
- **N, s:** prior 6-10 notices a month whose coin already has a Binance or OKX perp. Most of the jump is in the first 60 s; the prior for what is left from +60 s to +30-60 min is +2-4% with sd 10-12%, s 0.2-0.35. Kelly leverage about 2.5x, reachable. Long only, so it also works spot-only.
- **Data:** notice times from the Wayback route that worked for Upbit/Bithumb delist notices in forced-flow (half of the fetches failed there); second-level timestamp precision is **unverified**. Prices: `data.binance.vision` USDT-M 1-minute, else OKX.
- **Kill test:** (1) counts-only probe: >= 60 notices with a perp bar before the notice and a publish time to the minute, else kill. (2) One protocol: long at the open of the first 1-minute bar at or after notice + 60 s (and + 5 min), holds 15 min / 60 min / 4 h (6 cells, Holm), 0.6% round trip, 25% stop, reversed placebo and the 5-random-alt-perp control. Kill if train mean <= 0 at + 60 s, or notice-level x < 0.2, or nothing survives the + 5 min delay (then our timestamps cannot support it).

### D3. Delist-hazard timing (the pre-notice version of L1f)
- **Forced trader:** the same holders who must exit after a Binance delist notice; the pre-positioned short earns the announcement jump that a post-notice entry misses.
- **Size = hazard x jump - carry.** A standing short basket of tagged perp coins fails on paper: hazard about 5-8% a coin-month x jump about 15-20% is about +1% a month against 35% idiosyncratic sd (x about 0.01). It only works if hazard can be concentrated to >= 10% per coin-day (fixed review weekday/hour, a vote-to-delist result, a futures delist of the same coin some weeks earlier): then +1.8% a coin-day against 6% sd, s 0.3, 3-5 coin-days a month.
- **Data:** frozen notice lists on `data/forced-flow` (timestamps and names only), `data.binance.vision` USDT-M klines and funding.
- **Kill test:** (1) timestamps only, no prices: weekday/hour histogram of delist notices, gap between batches, lead from mon_tag / fut_delist / vote notices to the delist of the same coin. Kill if no pre-registered condition lifts train-period hazard to >= 10% per coin-day on >= 20 coin-days. (2) Only then one protocol with that condition frozen on train dates; kill if x < 0.2 on validation dates.

### D4. Tag removal and survivor relief, long
- **Expected to fail the 0.2 line alone** (N is too low); listed because the events stage is nearly free and it is the only spot-capable mirror of L1f.
- **Forced trader:** shorts held for delist hazard cover when the hazard resolves; holders barred by the tag return. Named as "not tested" in the forced-flow protocol (tag removals, seed-tag changes). Long only, so it is the spot-capable mirror of L1f.
- **N, s:** tag-removal notices about 0.7-1.5 a month (several coins each, one risk unit). Prior +5-8% in 4 h, sd 12-15%, s 0.3-0.5 at notice level. Survivor relief (tagged perp coins *not* named in a delist batch) adds about 1.2 clusters a month at a smaller prior (+1-2%).
- **Data:** the Binance announcement catalog used by `core/forced_flow.py` (whether tag-removal titles are already parsed is unverified); `data.binance.vision` spot and USDT-M 1-minute.
- **Kill test:** events stage first (counts); kill if < 20 train notices in total. One protocol, 3 holds x 2 delays as forced-flow; kill on train mean <= 0 or notice-level x < 0.2.

### Killed on paper (do not build)
- US leveraged-ETF close rebalance and any equity intraday flow: gross about 0.15% a trade, reachable leverage <= 5x, all-win ceiling about 1.45x.
- Near-resolved prediction-market favourites: already run and killed as Thin B rule B1 (validation -6.2%, 0.23 entries a week); do not redo.
- Standing hazard baskets (delist short or Upbit-listing long): x about 0.01.
- Margin-pair removal notices: direction ambiguous, prior move about 1%.

## 3. Is stacking many small components the path?
Yes for a positive-edge book, no as a quick route to a median 3x.
- **Count:** at half Kelly the sum must be 2.9. At 0.2 each (cluster level, uncorrelated) that is 15 components at face value and about 30 after a 50% forward shrink.
- **Measured, tradable, cluster-level:** l1f on perps 0.19 (train negative), fut_delist 0.13, mon_tag 0.005. Sum **0.33**.
- **Unverified, not in the sum:** new-perp first-week short R2 (validation +3.4%, test +1.9%, beats control; failed only Bonferroni and the frequency gate; its sd was not read, prior x 0.1-0.2); train-only values of rules that were gate-dropped or failed validation (fundwin3 0.27, crowd_fade 0.27, taker_cont 0.18). Together at most about 0.5 more, and only after each is re-measured on validation rows.
- **With D1-D3 at haircut values (0.35-1.2):** book x **0.7-1.5** from measured plus new, up to about 2.0 if every unverified item holds. Working figure 1.2.
- **What that buys:** x 1.2 at half Kelly is a median month of about 1.6x, not 3x. Under bank-and-reset the measure is the hit rate: at x 1.2 the month ends >= 3x in roughly 12% of months at half Kelly (zero-edge control with the same sizing: about 1%), or about 30% at full Kelly (control: at most 23%, the bound set by the 0.4x halt). These are normal approximations, to be replaced by the cohort table. The gap between real and control is what the e-process can confirm.
- **Wallet limits:** 2 open risk units, 25% loss cap per unit, overlapping holds (R2 is a 7-day hold). High-N components (D1, funding window) need their own unit budget in an addendum or they crowd out the notice events.
- **Rule:** sum only x measured on instruments tradable at event time, at cluster level. A component enters by a dated `components_addendum_<date>.json`; `components.json` is never edited.

## 4. Keeping the L1f edge
Conditional on the running `protocol_l1f_venues_20261125.md` result (not duplicated here).
1. **Default expectation:** where a perp exists x is 0.19, so alt-venue perps (set B) will most likely sit near it, not near 2. Prior for B: s 0.3-0.5 on <= 0.6 events a month, x 0.05-0.15, less with the thin-book slippage variant. Reachable L1f total about 0.25-0.35. If B shows s >= 0.6, add it by addendum at its own frozen weight.
2. **Borrow:** not point-in-time verifiable without an API key. Only a forward log is possible: from now, record at each notice the public borrowable flags (Gate, KuCoin, Bitget currency endpoints). It stays a labelled upper bound until 20 notices are logged.
3. **Pre-notice signal:** D3. It reaches only perp coins but earns the jump instead of the 4 h tail.
4. **Spot-only long counterpart:** there is no symmetric long for a delist (the pre-removal rebound is already rejected). The long mirrors are D4 (tag removal, survivor relief) and D2 (forced buying before a KRW listing).
5. **Sizing:** the frozen l1f weight 1.0 still fits the perp rows (half Kelly = mean / E[r^2] / 2 = 0.047 / 0.0244 / 2 = 0.96). The weight is not the problem; the expected growth is (x 0.19, not 2.24). An addendum cannot change an existing component's size or rules, so any re-weighting would need a new dated protocol with a fresh ledger and controls.

## 5. Order of work
1. Counts-only probes for D1, D2, D3, D4 in one Actions run (no prices).
2. D1 and D2 protocols first (highest haircut x; D1 reaches a verdict fastest because N is high).
3. Read the L1f venues result; if a component qualifies (set B, R2 or fut_delist re-measured at cluster level), add it by a dated addendum with its own unit budget. Existing components stay as locked.
4. D3 and D4 only if their probes clear the counts.
