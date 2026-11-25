# Protocol D2: long the global perp after an Upbit / Bithumb KRW-market listing notice, pre-registered 2026-11-26

Locked before any price of this study was pulled. Spec source: `research/plans/PLAN_20261126_fable.md`, direction D2. Nothing about this event
family was priced before; only notice titles of the Wayback captures (stage A, no returns) are read before the freeze. Code: `core/kr_listing.py`,
`research/studies/kr_listing.py`, workflow `kr_listing.yml`. Rows and frozen events are kept on branch `data/kr-listing`.
Goal: independent forced-buying events for the event book (not a result until a rule passes every gate below AND is confirmed forward through a dated addendum).

## Event
- One event = one coin whose KRW (원화) market is opened, time = the notice's own publication time. Sources (Actions are blocked by both exchanges, so Wayback only):
  Upbit `first_listed_at` of the announcements API captures (ISO with +09:00 offset); Bithumb the date printed on the notice page (KST, naive, read as UTC+9).
  Title and time come from the EARLIEST capture of each notice id. A notice posted later than its capture time + 60 s is dropped and counted (clock/zone error test).
- Listing title = contains 원화/KRW AND (마켓 추가 | 디지털 자산 추가 | 신규 거래지원 | 신규 상장 | market add | new listing | support for), and none of
  종료 폐지 유의 해제 해지 변경 연기 취소 유예 재개 중단 점검 이벤트 에어드랍 입출금 상장기념 (and English delist/terminat/cancel/postpone/suspend/event/airdrop/maintenance/warning/change).
  BTC-only or USDT-only market notices are not events. Ticker = the parentheses of the title (`core.forced_flow.kr_symbols`).
- One event per coin per 30 days across both venues: the earliest notice of either venue counts (the later venue is not new information; venues are reported).
- Window 2024-01-01 .. 2026-10-29. Splits by notice time: train 2024-01-01..2025-07-01, validation ..2026-03-01, test ..2026-10-29 (as forced_flow).
- Stage A (events mode, no prices): events are built from the archive and frozen on `data/kr-listing` (`events/latest.json`). Titles of ALL Upbit/Bithumb notices (no returns) are kept
  to audit the parser. One parser fix is allowed after reading those titles, documented in the PR, before the freeze. The priced run reads only the frozen list.
- Timestamp audit (reported, no prices): capture lag (capture - posted) quantiles, share of lags <= 10 min, KST hour-of-day histogram of listing notices (a 9-hour zone error would
  show as an hour shift into the night), events per month (coverage gaps).
- Kill 1 (counts): fewer than 60 events in the window, or fewer than 60 with a perp bar before the notice, or no minute-level time on the events: stop, report "not found / data insufficient".

## Trade (long; the hypothesis is forced buying before the KRW market opens)
- Perp: Binance USDT-M 1-minute klines (data.binance.vision; coin, then 1000 / 1000000 prefix), else OKX `<COIN>-USDT-SWAP` 1-minute candles. The perp must have a bar before the notice; no perp = not tradeable, counted.
- Entry at the open of the first 1-minute bar at or after notice + delay, delay 1, 5 or 15 minutes. Exit at the open of the bar `hold` later, hold 15 min, 1 h or 4 h. Stop 25% below entry on a bar low, fill at the stop minus 0.5%.
- Costs (judged): round trip 0.6% (taker fees 0.11% + slippage 0.2% per side) plus funding/borrow charged as cost 0.05% (15 min) or 0.1% (1 h, 4 h). Stress: cost doubled. Sensitivity at the 0.14% perp taker round trip is descriptive only.
- 9 rules = 3 delays x 3 holds. Headline rule: 4 h hold with 1 minute delay (`kr_listing|h240m|d1m`). Holm runs over the rules that pass stage 0.

## Control and placebo
- Reversed-side placebo: the same trades as a short (-gross - cost + fund), part of the sweep gate: train net mean must exceed it.
- Random control: per event one draw (seed `20261126:<coin>:<ts>`) of 5 coins from the 24 liquid alt perps of forced_flow (never the event coin), the same long with the same delay, hold, stop and costs on
  Binance USDT-M 5-minute bars at the same time; control = mean of the drawn coins (needs >= 3). Train net mean must exceed the control mean; so must validation and test.

## Stage 0 (train only, `core.sweep_stats.gate`, count relaxed as forced_flow)
n_train >= 20, train mean > 0 and above the placebo, vol/cost >= 10, x = N per month x s^2 >= 0.2, all-win ceiling >= 3x a month, train mean above the random-control mean.
Kill 2: nothing passes stage 0 at the 1-minute delay, or train mean <= 0 at 1 minute, or x < 0.2, or nothing survives the 5-minute delay (then our timestamps cannot support it).
A stage-0 survivor only at 1 minute but not at 5 minutes is reported as not tradeable (a 60 s reaction on a notice with second-level uncertainty is not assumed).

## After stage 0 (validation and test: `core.sweep_stats.evaluate` + `judge_family`, Holm over the stage-0 survivors, alpha 0.05)
val and test net mean > 0, also at doubled cost; val n >= 12, test n >= 10; block-bootstrap Holm p < 0.05 on the validation daily series; both 6-month folds positive;
last-12-month mean at double cost > 0; validation and test means above the random control. A rule PASSES when it meets every criterion. The sweep's strict counts (30/30/20) are reported beside.
"Not found" is a valid result.

## Reporting
Per rule: n, mean, sd, s = mean/sd, events per month N, x = N s^2, hit rate, by split; gross mean, placebo, control by split; by venue (descriptive); coverage (events, perp-priced, by source, dropped).
One run and one fix: a data or parser fix is allowed once (documented) before a second run; no rule, grid, threshold or cost change after seeing results.
A pass is proposed as a dated addendum `research/event_book/components_addendum_<date>.json` with a forward collector plan (separate PR; locked files are never edited).
