# Protocol: do other exchanges' own spot delist notices show the L1f drop on their own spot books? Pre-registered 2026-11-27

Locked before any price of this study is pulled. Only notice titles, ids, dates and counts may be read first (a probe; no prices, no returns). Known before the lock, not independent of it:
L1f (Binance), the forced-flow families (OKX, Bybit, Upbit and Bithumb notices priced on global perps, none passed) and the L1f venues study (the L1f edge is in coins with no Binance perp). This study
changes only the book: the notice of exchange E, the coin's own USDT spot book on E, as a margin short. Whether E lent the coin at the notice cannot be verified backwards, so every result is an UPPER BOUND on a margin short.

## Events
- E in {okx, bybit, gate, kucoin, bitget, mexc}. One event = E's own announcement that the SPOT market (USDT pair) of coin C will be delisted / trading ended; time = its publication time (earliest capture / the API's own timestamp).
  Titles for perpetuals, futures, options, margin-only pairs, ETF/leveraged tokens, "extend / postpone / cancel / resume / completed" are not events. One coin per event (a notice naming several coins is several events and one notice for the notice-level x).
- Window 2024-01-01..2026-10-29, restricted to what each feed can return; the reach of each exchange (events found, first date) is reported, an unreachable feed is "unreachable", not a failure of the rule.
- Dedupe (E, C) within 7 days to the first. Excluded: stablecoins; a coin with a Binance L1f notice within +-7 days (independent of L1f); a coin with no USDT spot bar on E before the notice (not tradable there).

## Trade (one rule, no grid)
Short at the open of the first 1-minute bar of E's own COIN/USDT spot book at or after notice + 60 s, buy back at the open of the bar 4 h later, 25% stop on a bar high (fill stop + 0.5%) (`core.forced_flow.short_trade`).
Costs: round trip 0.6% (fees 0.11% + slippage 0.2% a side) + 0.1% borrow = 0.7%; stress at 2x. Bars that cannot be fetched are dropped and counted, never treated as "no instrument".

## Controls
- Placebo: reversed side (-gross - cost + funding).
- No-notice control: the same coin on the same exchange, same rule, 24 h earlier (as `core.notice_fwd`); needs its bars; control mean reported, train mean must exceed it.

## Tests and gate
Seven tests, one rule each: each of the six exchanges and the pool `other_spot` (all six). Splits by notice time: train 2024-01-01..2025-07-01, validation ..2026-03-01, test ..2026-10-29.
Stage 0 on train: `core.sweep_stats.gate` as in `protocol_forced_flow_20261125.md` (n_train >= 20, mean > 0 and above placebo and control, vol/cost >= 10, x = N a month x s^2 >= 0.2, all-win ceiling >= 3x a month, notice-level x >= 0.2).
Then validation and test as in that protocol (val n >= 12, test n >= 10, positive at 2x cost, block-bootstrap Holm p < 0.05 over the stage-0 survivors, both folds positive, last 12 months at 2x cost positive, val and test above control).
A test PASSES only if every criterion holds. Reported for every test: n, mean, sd, s, N a month, x = N s^2, hit rate, by split, placebo, control, mean at 2x cost, coverage and dropped counts. "Not found" is a valid result.

## Consequence
A passing exchange is proposed for the forward margin recorder (`protocol_l1f_margin_arm_20261127.md`) by a separate dated addendum (the recorder would need that exchange's notice feed and public margin data; nothing is added before). A pool-only pass with no single exchange passing is reported as such and not added.
