# Protocol: D1 forced-flow fade on small perps, 5-60 minutes, pre-registered 2026-11-26

Locked before any D1 return, trade or P&L was computed. What was read before the lock: the stage A probe (`d1_probe.py`, Actions runs 45670184510 and
45670439412, counts and structure only). It found: Binance Vision has **no** USDT-M `liquidationSnapshot` (0 symbols; only the COIN-M listing exists, major coins, not small
perps); the OKX public `liquidation-orders` endpoint answers but holds only about the last hours per instrument (a request for 30 days back returns nothing); Gate
`liq_orders` is live only (date-range requests are rejected, HTTP 400); Bybit, BitMEX and Binance `allForceOrders` are blocked from Actions (403/451). So **no point-in-time
liquidation history is reachable**: the plan's kill test for the backtest route on real prints is met (fewer than 200 clusters on 30 instruments is certain). The backtest therefore uses a
**forced-flow proxy** built from Binance USDT-M 1-minute klines (quote volume and taker-buy quote volume), and the real liquidation prints go forward-only (not part of this protocol).
The probe also printed per-month counts of proxy triggers (volume multiple and move only, no returns); the thresholds below were fixed from the plan text (10x/20x volume, 3%/5% move are the
round numbers used by the plan's "multiple of median 5-minute volume"), not from any outcome.
Plan: `research/plans/PLAN_20261126_fable.md`, direction D1. Code: `core/d1_liq.py`, `research/studies/d1_liq.py`, workflow `d1_liq.yml` mode `run`.

## Universe and data
Every Binance USDT-M perpetual that ever had monthly 1-minute klines on data.binance.vision (delisted ones included; listing from the S3 index), ticker ending USDT without an underscore, except
the 30 "major" bases (BTC ETH BNB SOL XRP DOGE ADA TRX AVAX LINK DOT LTC BCH NEAR UNI ATOM ETC XLM FIL APT ARB OP SUI TON SHIB PEPE AAVE HBAR INJ TAO; a leading 1000/1000000 is stripped). Months 2023-12 to 2026-10
(2023-12 only as baseline history). A symbol-window is usable only with a full 24 h baseline (see below), so a new listing has no event in its first day.

## Proxy event (one event = symbol and 5-minute window; known at the window end T)
Windows are the UTC-aligned 5-minute blocks. For window k: ret = close of its last minute / open of its first minute - 1; qv = sum of quote volume; imb = taker-buy quote volume / qv.
- baseline = median qv of the previous 288 windows (24 h; at least 250 of them non-empty; the window itself is excluded); day volume = sum of those 288 qv must be >= 5,000,000 USDT (so the contract is tradeable at 400 USDT notional).
- Trigger: qv >= M x baseline AND |ret| >= R AND the taker side agrees with the move (ret < 0 needs imb <= 0.40: aggressive sells; ret > 0 needs imb >= 0.60: aggressive buys).
- Two size thresholds (the plan's "2 size thresholds"): `s1` = M 10, R 3%; `s2` = M 20, R 5% (s2 is a subset of s1).
- A symbol's later event within 30 minutes of its previous event is dropped (same cluster). Events with T in [2024-01-01, 2026-10-29).
- Side: **fade**. Down-move (forced selling of longs) -> long; up-move (forced buying/short squeeze) -> short. Both directions are one rule; the split by direction is reported, not judged.

## Trade
- Entry at the open of the first 1-minute bar at or after T + delay (at most 3 bars late). Judged delay 60 s. Delay 300 s is reported only (it tells whether our timestamps/latency could support the rule); it does not enter Holm or the verdict.
- Exit at the open of the bar `hold` later (at most 3 bars late); holds 5, 15, 60 minutes. Stop 5% against the entry on a 1-minute bar high/low, filled at the stop plus 0.5% slippage.
- Costs: round trip 0.40% (taker fee 0.05% a side = 0.10%, slippage plus half-spread 0.15% a side = 0.30%) plus 0.01% funding allowance. Stress `mean_2x`: the cost doubled again (as `core.sweep_stats`: net minus cost).
- One trade at a time (k = 1), first come: events are taken in time order and an event whose T + delay falls before the previous accepted trade's exit is skipped (counted). This makes the unit a cluster: a market-wide cascade is one trade.
  Account weight lev 3 (`size {lev 3, k 1}`) in the gate arithmetic, as the sweeps use.
- Rules: 2 sizes x 3 holds = **6 judged rules** (`s1|h5m|d1m` ... `s2|h60m|d1m`); the six delay-300 variants are reported only. Headline rule: `s1|h15m|d1m` (named before any outcome; it does not get special treatment in Holm).

## Controls (all under the same costs, hold, stop and side as the trade)
- **Reversed-side placebo** (the sweep gate's own): the follow-the-move trade of the same events, `-gross - cost + funding`.
- **Random-time control**: for every event, 3 entries at random minutes of the same symbol in the same calendar month (seed `20261126:<symbol>:<T>`), same side, hold, delay and stop; needs >= 2 usable; control = their mean. The rule's mean net must exceed the control mean on the selected trades.

## Stage 0 (train only, `core.sweep_stats.gate`, the sweep's gate unchanged, strict counts)
n_train >= 30; train net mean > 0 and above the placebo; volatility/cost (sd of gross / cost) >= 10; x = N per 30 days x s^2 >= 0.2; all-win ceiling >= 3x a month; plus train mean above the random-control mean.
Splits by T (as the forced-flow protocol): train 2024-01-01..2025-07-01, validation 2025-07-01..2026-03-01, test 2026-03-01..2026-10-29.

## Post-gate criteria (Holm over the stage-0 survivors, `core.sweep_stats.evaluate` + `judge_family`, alpha 0.05)
val and test net mean > 0; both > 0 at doubled cost; validation n >= 30 and test n >= 20; block-bootstrap Holm p < 0.05 on the validation daily series; at least 70% of 6-month folds positive; last-12-month mean at double cost > 0; plus validation and test mean above the random-control mean.
A rule PASSES when it meets every criterion. "Not found" is a valid result.

## Reporting
For all six judged rules and the six delay-300 rules, by split: n, mean, sd, s = mean/sd, N per month (selected trades per 30.4 days), x = N s^2, hit rate, placebo mean, control mean; raw trigger counts, skipped-by-concurrency counts, symbols with events, events per month,
direction split, dropped trades (no bar at entry or exit) and failed downloads. Rules tested, rules passed, closest rule. If a rule passes: a dated addendum proposal `research/event_book/components_addendum_<date>.json` in a separate PR (the locked components file is not edited), to be confirmed forward.
One run and one fix: a data or parser bug may be fixed once (documented in the PR) before a second run; no rule, grid, threshold or cost change after any outcome. The real liquidation prints (OKX, Gate) are a separate forward collection and are not mixed into this result.
