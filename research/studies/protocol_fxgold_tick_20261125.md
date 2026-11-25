# Protocol fxgold_tick (family 5): gold and FX intraday on Dukascopy bid/ask, XM costs. Locked 2026-11-25 before any candle or tick of this study was downloaded
Probes (`fxgold_probe.py`, `fxgold_probe2.py`) only counted files, spreads and page structure; no returns were computed. No LLM. Simulated money only.

## Data
- Dukascopy `datafeed.dukascopy.com` bi5: 1-minute BID and ASK candle files per UTC day (XAUUSD, EURUSD, GBPUSD, USDJPY), 2018-01-01 to 2026-11-19, merged into one bid/ask minute bar. Hourly tick files only for release windows (rule family C). A day is kept only when both sides downloaded; missing days (market closed or download failed after retries) are reported, never filled.
- Calendar (family C): US CPI and Employment Situation (08:30 New York, dates from the BLS archived release lists), FOMC decision (14:00 New York; Fed calendar page for 2021+, scheduled 2016-2020 dates typed from the Fed calendars, emergency meetings excluded). `research/studies/fxgold_calendar.py`. ForexFactory exposes only the current week (probe) so it is not used.
- Splits (UTC): train 2018-01-01..2022-01-01, validation 2022-01-01..2024-07-01, test 2024-07-01..2026-11-20. Rolling non-overlapping 6-month folds over validation+test (`sweep_stats.folds`).

## Trade mechanics
Signal on the close of minute j, fill at the open of minute j+1 on the real side (long ask, short bid); stops/targets on the closing-side quote; both touched in one minute = stop; one position at a time per symbol; all trades closed before 21:00 UTC (no swap). gross = mid-to-mid return; cost = max(XM Standard spread from `core/broker_costs.py`, realised average spread in and out) / entry price; net = gross - cost; 2x stress = net - cost. Size: nominal leverage XAUUSD 40, others 10, one position (k = 1). Minimum lot 0.01 (1 oz gold / 1,000 units) is checked in the gate as a minimum notional against 147 USD x leverage.

## Rules (56 definitions; cell = rule x symbol; Family C also uses ticks)
- A. Opening-range breakout (brk) or failure fade (fail), session London 08:00 local or New York 08:00 local, range window 15/30/60 min, scan until +3 h, first signal per day. brk: first minute whose mid close is beyond the range; stop = range height. fail: break then mid close back inside within 10 minutes; stop = fake-out extreme (floor 0.25 range). Exits: t120 (stop + 120 min), tp (stop, target 1.5 R, 240 min), trail (trailing R, 240 min). 2 x 3 x 2 x 3 = 36 rules x 4 symbols.
- B. Asia range (00:00 UTC to 07:00 London) swept between 08:00 and 11:00 London and reclaimed (mid close back inside) within 15 or 30 min; fade to the range middle or the opposite side; stop beyond the sweep extreme (floor 0.1 range); exit 13:00 London. 4 rules x 4 symbols.
- C. Release minute: move = mid(t0+10 s) - mid(t0-5 s) from ticks; trade if |move| >= theta x sigma(1m returns over the previous 240 minutes), theta 2 or 4; momentum or fade; enter at t0+11 s at the real bid/ask, stop = |move|, hold 60 or 300 s. 8 rules x 4 symbols. (The macro random-side control mirrors the sign of the gross.)
- D. London 16:00 fix: continuation of the 14:00-15:30 London move held 15:55-16:05 (all days; last 3 weekdays of month only); fade of the 15:54-15:59 move when >= 1.5 or 3 sigma(5m), hold 15 min. Stop 3 sigma. 4 rules x 4 symbols.
- E. Gold round numbers (XAUUSD only), levels every 50 or 100 USD, 07:00-19:00 UTC, touch of a level (min 120 min between touches of the same level); fade = the touching minute closed back on the near side, brk = closed beyond; stop and target 1 R (R = 3 x mean 1-minute range of the previous hour), exit 60 min. 4 rules.
Total cells: 36x4 + 4x4 + 8x4 + 4x4 + 4 = 212.

## Decision chain
1. Stage-0 gate on TRAIN only (`sweep_stats.gate`): >= 30 train trades; minimum lot notional <= 147 x leverage; train net mean > 0 and above the reversed-side placebo; sd(gross)/cost >= 10; monthly x = N s^2 >= 0.2; all-win ceiling (90th percentile MFE) reaches 3x a month.
2. Family = cells passing the gate; Holm on the validation moving-block bootstrap p (20-day blocks, daily account series) over that family, alpha 0.05.
3. Pass = all of: validation and test mean net > 0; validation and test mean at 2x cost > 0; >= 30 validation and >= 20 test trades; Holm p < 0.05; >= 70% of 6-month folds positive; last 12 months mean at 2x cost > 0; validation mean above the maximum of 5 random-side controls (same entries, exits and costs).
4. Reported for every survivor: validation/test mean, p, x per month, 30-day multiple distribution at nominal leverage, ceiling. Per-trade rows of every cell go to data branch `data/fxgold-tick-rows`.
No parameter is changed after seeing validation or test data; a variant is a new dated protocol.

## Addendum 2026-11-25 (before any candle of this study was read): gold-only pilot
Dukascopy answers about 17 s per request, so the full download takes hours. A pilot runs the SAME pre-registered rules (no rule, parameter, cost or criterion change) on XAUUSD cells only, from candles of 2023Q4..2026Q4, with shorter splits: train 2023-12-01..2024-12-01, validation 2024-12-01..2025-09-01, test 2025-09-01..2026-11-20. It is a diagnostic subset (about 60 cells), reported as such; it does not replace and is not pooled with the full run, which keeps the splits above. The family size and Holm of the full run are unchanged. The macro tick windows are cut to -30 s..+330 s (the rules need -5 s..+311 s).
