# Protocol: forced-flow event families shaped like L1f, pre-registered 2026-11-25

Locked before any price of this study was pulled. Only announcement titles, article bodies and archive page structure were read
(stage A probes, `forced_flow_probe.py` / `forced_flow_probe2.py`: no prices, no returns). Known before the lock, and not independent of it: the
L1f rows (Binance delist short, mean +14%) and the notice tape (run 45567857959) which priced OKX delists descriptively (negative for shorts) and found
no cell passing; the monitoring-tag, futures-delist, pair-removal, Upbit, Bithumb and Bybit families here were not priced before.
Stage A3 (`forced_flow.py ... events`) builds the event lists without prices and freezes them on `data/forced-flow` (`events/latest.json`); the priced run
reads that frozen list, so the archive (not reproducible) cannot change between the lock and the run. Parser bugs found in A3 may be fixed once before the freeze.
AGENTS rule 10 (research first): the sweep engine has no announcement-event kind, so these families need an event loader; the sweep's own gate,
metrics, Holm and pass functions (`core.sweep_stats`) are reused unchanged, and the report gives rules tested / passed / closest to passing as the leaderboard does. Code: `core/forced_flow.py`,
`research/studies/forced_flow.py`, workflow `forced_flow.yml` mode `run`; rows kept on branch `data/forced-flow`.
Goal: more independent forced-flow events to add to the event book (L1f alone: x about 2.0, 3x a month needs about 2.2). Not a
result until a family passes the gates below AND is confirmed forward by the event-book e-process through a dated addendum.

## Events (one event = family, coin, notice time; no look-ahead: the time is the notice's own publication time)
- `mon_tag`: Binance "Will Extend the Monitoring Tag to Include <coins> ..." (catalogs 161, 49, 93). Only the coins that GET the tag;
  removals of the monitoring or seed tag are not events.
- `fut_delist`: Binance "Futures Will Delist ... Perpetual Contract(s)" (catalog 161); coins = every `<COIN>USDT` contract in title and body.
- `pair_rm`: Binance "Notice of Removal of Spot Trading Pairs" (catalog 161, body parsed): coins whose `<COIN>/USDT` pair is removed (other quotes ignored).
- `okx_delist`: OKX announcements API, titles classified delist or perp_delist by `core.notice_tape.classify_title` (reach: from 2025-09).
- `upbit_delist`, `upbit_caution`, `bithumb_delist`, `bithumb_caution`, `bybit_delist`: Wayback Machine snapshots of the exchanges' own pages/APIs
  (Actions are blocked by those exchanges). Upbit: `first_listed_at` of API list/notice snapshots; Bithumb: the date printed on the notice page
  (KST); Bybit: article titles from the page `<title>`, time from a publish-date field in the HTML (events without one are dropped and counted).
  Coverage is whatever the archive holds (not complete; the share is reported); archiving does not depend on the outcome. Delist = Korean
  "거래지원 종료"/"상장폐지" or English delist/market-support-termination titles; caution = "유의 종목"/"투자 유의"/investment warning/caution.
- Deliberately not tested (stated so nothing is cherry-picked afterwards): seed-tag listings (a listing, not forced selling; L1 covers it; the perp rarely exists before the
  notice), seed/monitoring tag removals, margin pair removals, Coinbase (no archived notice feed), token unlocks (screen L2 already
  closed: small daily edge, test split negative), index removals (no free point-in-time source found).
- `fut_delist` skips titles that also update leverage/margin tiers ("Delist and Update ..."): the body mixes delisted and updated contracts.
- Archive rules (no look-ahead): title and time come from the EARLIEST capture of each notice id (titles are edited later); titles with lifted/extended/cancelled/completed
  words (해제, 연장, 취소, 유예, 재개, completed, cancel, extend, postpone, lifted, resum) are not events (wrong-sign or non-new); an event whose posted time is later than its
  capture time is dropped and counted; archive fetch failures are counted per source.
- Window 2024-01-01 to 2026-10-29. Duplicates (family, coin) within 7 days are one event (the first). L1f reference events: Binance catalog 161 "Will Delist ... on <date>" via
  `core.screens.binance_delist_symbols`.
- Independence from L1f: an event whose coin has an L1f notice within +-7 days is excluded from the judged set (reported as `overlap_l1f`). Overlap and the daily-P&L correlation
  with L1f are reported per family.

## Trade (all families: short, the hypothesis is forced selling; the reversed side is the placebo)
- Perp: Binance USDT-M 1-minute klines (data.binance.vision; symbol, then 1000/1000000 prefix), else OKX `<COIN>-USDT-SWAP` 1-minute candles. The coin must have a bar before the notice. No perp = not tradeable, counted.
- Entry at the open of the first 1-minute bar at or after notice + delay; delay 1 or 5 minutes. Exit at the open of the bar `hold` later, hold 1 h, 4 h or 24 h. Stop 25% above entry on a bar high, fill at the stop plus 0.5%.
- Costs: round trip 0.6% (fees 0.11% + slippage 0.2% per side) plus funding/borrow 0.1% (1 h, 4 h) or 0.3% (24 h). Stress: cost doubled (`mean_2x`).
- Rules per family: 3 holds x 2 delays = 6. Nine families, so 54 rules; Holm runs over the rules that pass stage 0 (as the sweep does). Headline rule of every family: 4 h hold, 1 minute delay (the L1f rule).
- Splits by notice time: train 2024-01-01..2025-07-01, validation 2025-07-01..2026-03-01, test 2026-03-01..2026-10-29. Weight 1, one trade at a time (k = 1) in the gate arithmetic.

## Control
Random control: for every event one draw (seed `20261125:<family>:<coin>:<ts>`) of 5 coins from a fixed list of 24 liquid alt perps (ADA ALGO APT ARB ATOM AVAX AXS CHZ CRV DOGE DOT DYDX ENJ FIL GALA INJ LDO LINK MANA NEAR OP SAND SNX UNI; never the event coin), the same short with the same delay, hold,
stop and costs on Binance USDT-M 5-minute bars at the same notice time; control = mean of the drawn coins (needs >= 3). This captures the alt-coin drift that every short would otherwise be credited with.

## Stage 0 (train only, `core.sweep_stats.gate`, the sweep's gate unchanged except the trade count)
n_train >= 20 (the sweep's 30 is unreachable for event families that fire 1-3 times a month; L1f train has the same order), train mean > 0 AND above the reversed-side placebo (-gross - cost + funding), vol/cost >= 10, x = N per month x s^2 >= 0.2,
all-win ceiling >= 3x a month; plus (added here) train mean above the random-control mean and notice-level x >= 0.2 (one observation per notice = the mean net of the coins it names,
because the book treats one notice as one risk unit; a notice naming 10 coins is not 10 events).

## Gate after it (validation and test, `core.sweep_stats.evaluate` + `judge_family`, Holm over the stage-0 survivors, alpha 0.05)
val and test net mean > 0; also > 0 at doubled cost; val n >= 12 and test n >= 10 (sweep: 30/20, same reason as above); block-bootstrap Holm p < 0.05 on the validation daily series;
both 6-month folds positive; last-12-month mean at double cost > 0; plus validation and test mean above the random-control mean.
A family PASSES when one of its rules passes every criterion. "Not found" is a valid result.
The sweep's own trade counts (train 30, validation 30, test 20) are computed as well (`sweep_strict_gate`, separate Holm family) and reported next to the event-family counts;
a pass under the relaxed counts only is reported as such, never as a sweep pass.
Dropped trades are counted, not hidden: no bar at the entry or exit (for example the perp was delisted before the exit bar) and failed price downloads are reported per family.

## Reporting
Per family and per rule: n, mean, sd, s = mean/sd, events per month, x = N s^2, hit rate, by split, placebo mean, control mean, coverage (events, perp-priced, by price source), overlap with L1f, daily correlation with L1f,
x of the family alone and of family plus the L1f reference. Passing families are proposed as a dated addendum `research/event_book/components_addendum_<date>.json` (a separate PR; locked files are not edited) and confirmed forward by the e-process against random controls.
One run and one fix per family: a data or parser fix is allowed once (documented in the PR) before a second run; no rule, grid or threshold changes after seeing results.
