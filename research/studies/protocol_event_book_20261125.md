# Protocol: forward event book (one 147 USD paper wallet, several notice components), locked 2026-11-25

Locked before any forward data of this book. Plan: `research/plans/PLAN_20261125_fable.md`. Code: `core/event_book.py`,
`research/studies/event_book_forward.py`; workflow `event_book.yml` mode `forward`, dispatched by `keeper.yml`;
state on branch `data/event-book` (`state.json`, append-only `trades.jsonl`, `summary.json`). Components and frozen sizes:
`research/event_book/components.json` (SHA-256 below; `tests/test_event_book_lock.py` checks both files).
Components.json SHA-256: 034bbea5377bd5b146392ff4a46e8acc1c33c2b6a8acde09b87a12b7fe898c3d

## Components (frozen)
- **l1f**: short 4 h after a new Binance "Will Delist ..." notice (catalog 161, `binance_delist_symbols`). Origin: L1e/L1f
  rows (`data/event-rows`).
- **l1_4h**: long 4 h after a new Binance "Will List ..." notice (catalog 48, `binance_listing_symbols`). Origin: L1 rows.
- More components enter only through a dated addendum file `research/event_book/components_addendum_<date>.json` committed
  before the component's first forward event (for example a passing cell of the notice-tape screen). An addendum never
  changes sizes or rules of existing components; its `effective_from` must be later than its commit time.
- L1g (Alpha removal) is not a component: its coins have no OKX perp in the sample (see rows).

## Execution (paper, public data only)
- Venue: OKX USDT swaps (Bybit answers 403 to GitHub runners). A notice coin is tradable only if `<COIN>-USDT-SWAP` (or
  the `1000`/`10000`/`1000000` prefixed name) is live with a quote; otherwise the event is counted as skipped (`no_perp`).
  Spot-only coins are not traded, so the forward book is stricter than the screens (coverage is reported).
- Freshness: the collector polls every 30 s inside a ~9 minute job, re-dispatched every 10 minutes by the keeper; a notice
  published more than 15 minutes before it is first seen is not an event (first sight of the book at start included).
- Entry at the first poll that sees the notice: long at the ask, short at the bid. Exit 4 h later at the close of the
  1-minute candle at the due time, adjusted by the entry half-spread against the position. Stop 25% against the entry
  price checked on 1-minute highs/lows of the OKX candles, fill at the stop plus 0.5% slip. Costs: 0.11% fees round trip
  and 0.1% assumed funding/borrow; the spread is paid through bid/ask.
- Order minimums: quantity must satisfy the OKX instrument `minSz`/`lotSz` (times `ctVal`) and a 5 USD minimum notional on
  the equity at entry; an order below the minimum is skipped for that ledger and counted.
- One notice = one risk unit: its weight is split equally between the tradable coins named in it. At most 2 risk units are
  open at once (extra notices are skipped and counted), so a day loses at most about 2 x 27% of equity.

## Sizing (frozen from rows up to 2026-10-31)
- Rows: `data/event-rows` branch (`rows/l1.jsonl.gz`, `rows/l1f.jsonl.gz`), run 45562238880 on 2026-11-25. Net 4 h return
  after the study's 0.6% round trip, coin minus BTC; stop-adjusted on 1-minute closes (25% stop, 0.5% slip, 0.1% extra for shorts).
- **l1f**: n 105, mean +14.2%, sd 16.7%, s 0.85, 3.09 events a month, x = 2.24; half-Kelly 1.49 of equity, capped by the loss
  rule 0.25 / 0.25 = 1.0 -> weight **1.0**.
- **l1_4h**: n 31, mean +48.3%, sd 192.8% (ACT +2,073% on KuCoin dominates), s 0.25, 0.91 events a month, x = 0.057; half-Kelly
  0.0631 -> weight **0.0631** (frozen as computed; the outlier makes it small, which is the conservative direction).
- l1g (Alpha removal): n 13, test split only, KuCoin-priced, no OKX perp evidence; not a component.
- Frozen weights are in `components.json`; the hold is 4 h and the stop 25% for both.
- weight = notional / equity per risk unit = min(half-Kelly, 0.25 / stop, 3). Half-Kelly is `mean / E[r^2] / 2` on the
  stop-adjusted 4 h net returns of the component's rows.

## Ledgers and control
- Real ledger: 147 USD, compounding, sizes by the weights above on the equity at entry.
- 200 control ledgers: for every real trade each control takes the same side, weight, entry time, hold and stop on a coin
  drawn at random (with replacement) from OKX USDT swaps with 24 h turnover >= 100,000 USD, never the event coin.
- Cohorts: a fresh 147 USD wallet every Monday 00:00 UTC for 30 days, for the real ledger and each control. At 3x (441 USD)
  the wallet banks the win and resets to 147; at 0.4x (58.8 USD) it halts until the cohort ends. Reported per cohort: real
  banks, equity, halted, and the share of control cohorts that banked.
- The decision series is a separate always-on reference ledger (no bank, no halt): daily log return of the real ledger minus
  the mean daily log return of the 200 controls, one value per whole UTC day from the first day, 0 on days without trades.

## Decision
- `core.sequential.EProcess(paired=True, lo=1.8, hi=1.2)` on the daily difference (lo is a hard lower bound: real >= -0.7
  with at most 2 open units, control mean gain <= ln 3; wins above 1.2 are clipped). Edge at e-value 20 (alpha 0.05); no
  edge when the negative-side e-value reaches 20. Checked every day; no rule changes after the first event without a new
  dated protocol.
- The goal check (3x in 30 days) is the cohort table: the real hit rate against the controls', reported as it comes; no
  claim of reaching 3x without the e-process edge and a cohort bank after costs.
