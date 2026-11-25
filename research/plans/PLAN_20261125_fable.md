# Plan 2026-11-25 (Fable strategy review): a combined event book

Goal: a simulated 147 USD account reaches >= 3x in 30 days after costs, beats a random control, rules locked before data.
Status: plan only. Each component still needs its own locked protocol and forward evidence before it counts.

## 1. Math
- One rule with N independent trades a month and a per-trade Sharpe s (mean / sd of the net return) has monthly Sharpe about sqrt(N) * s. Define x = N * s^2.
- The log-wealth growth of a Kelly bettor is about x / 2 per month. To triple (ln 3 = 1.10) in the median month we need x >= 2.2 (full Kelly); for 70% of months we need x >= 4.4.
- Components with independent events add: x_book = sum of N_i * s_i^2. Half-Kelly gives 3/4 of the growth for half the variance.
- Bank at 3x and reset: the account is not allowed to keep compounding past the target, so every month is a fresh attempt and the hit rate rises above the median-growth figure.
- Estimate (Fable): L1f (short 4h after a Binance delist notice, +8.5 to +11% per event, 91 of 105 positive, about 3 a month), L1 (4h hold after a listing, about +10%, about 1 a month), L1g (short after Binance Alpha removal, +14%, n = 13), news reader v2 H5 (s about 0.08, about 70 a month). Combined x about 1.4 to 2.6 a month against 2.2 needed. The gap needs more event components, hence the all-venue notice tape.

## 2. Diagnosis (why single-rule screens kept failing)
1. Wrong unit of test: per-rule Bonferroni instead of the combined book.
2. Gross edge below cost for most ideas.
3. One validation year only.
4. Horizon picks driven by outliers (ACT, ALPACA).
5. An events-per-week gate that blocks rules that are fine inside a book.
6. L1f is under-sized (20% of the ledger, no leverage, earns about 7% a month); half-Kelly may be about 1.5x equity.
7. Realism (order minimums, perp availability, latency) is checked too late.
8. Rows are not kept (artifacts expire), so nothing can be re-combined.
9. Test splits are already spent, so confirmation must be forward.

## 3. Ranked families
1. Exchange-notice tape (listing, delisting, perp delist, monitoring tag, funding-interval change) on all venues.
2. Funding-settlement window.
3. Polymarket short-horizon crypto markets against fair value.
4. Meta-allocator over the kept rows.
5. Gold/FX intraday on Dukascopy ticks at XM costs.
6. Positioning metrics (open interest, long/short ratios).
7. US small-cap intraday long events.
8. Session price-action structure.
9. Claude Haiku Polymarket forecasts at scale.
10. Unscheduled negative news, forward.
11. Sector peer lag.
12. Convex exits.

## 4. Stacking book rules
- One 147 USD wallet, real order minimums, half-Kelly per component frozen from data up to 2026-10-31.
- Per-trade loss cap 25% of equity via stop x leverage; one notice = one risk unit (several coins in one notice share it).
- Bank-and-reset at 3x; halt the month at 0.4x.
- Compare against 200 random-control ledgers with the same sizing; decide with the `core/sequential.py` e-process on the daily log-return difference; a fresh cohort every Monday.

## 5. Process changes
Keep every per-event row (jsonl.gz on a data branch); automatic stage-0 screen; discovery at family level with BH q = 0.10 plus a forward e-process; rolling 6-month folds; robust horizon picks (trim the best events); gate on x >= 0.2 instead of events a week; assume 5-minute latency; kill rule: one run and one fix per family; 20 parallel paper ledgers driven by the keeper.

## 6. Implementation record and results (2026-11-25, PRs #189, #192, #193 and later; branches `line/event-book-*`)
- Rows (run 45562238880, branch `data/event-rows`, `rows/*.jsonl.gz` with 240-minute paths): 4 h net return after 0.6% round trip, coin minus BTC.
  l1f n 105, mean +14.5%, sd 18.1%, s 0.80, 3.09 events a month, x = 1.98 (2.24 with the 25% stop on 1-minute closes; train 1.79, validation 0.09, test 2.11).
  l1 n 31, mean +48% but sd 193% (ACT +2,073%), s 0.25, 0.91 a month, x = 0.057 (validation s 0.52, x 0.10). l1g n 13 (test split only), s 0.99, 0.38 a month, x = 0.37.
  Sum of x = 2.41 in-sample (not tradable as such: l1g has no OKX perp, l1 is outlier-driven); a forward test is the only confirmation.
- Notice tape (run 45567857959, `data/event-rows/tape/`): 1,281 classified events from KuCoin (6,823 notices, 2024-01 on) and OKX (131 notices, only from 2025-06); Bybit, Coinbase, Bithumb, Upbit gaps (403 / no feed), Bitget serves 30 days only. 149 events had OKX perp candles (judged family), 290 only Binance USDT-M (descriptive). Family of 192 cells: **no cell passes**; 72 cells had n >= 30, 22 of them a positive mean, the best raw one-sided p was 0.12 (funding-interval change, short 72 h), Holm-adjusted 1.0. Monitoring-tag notices: none found; spot delist and perp-delist notices: 1 and 3 OKX-priced events (too few; KuCoin perp-delist shorts priced on Binance USDT-M lost 1.1% a trade).
- Forward event book: protocol `research/studies/protocol_event_book_20261125.md` (SHA-locked), components l1f weight 1.0 and l1_4h weight 0.0631, OKX swaps, started 2026-11-25 12:00 UTC, dispatched by the keeper.
