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

## 6. Implementation record (this PR line `line/event-book`)
- `research/studies/event_rows.py`, `.github/workflows/event_book.yml` (mode rows): per-event rows for L1, L1f, L1g on branch `data/event-rows`.
- `research/studies/protocol_notice_tape_20261125.md` + `core/notice_tape.py`: family-1 screen, spec committed before the run.
- `research/studies/protocol_event_book_20261125.md` + `core/event_book.py`: forward book, dispatched by the keeper.
