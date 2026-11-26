# Protocol: notice_fwd, forward paper ledger of exchange notices entered 5 seconds after the pod sees them, locked 2026-11-26

Direction Q2 of `research/plans/PLAN_20261127_fable.md`. Locked before any price of this study was read. Code: `core/notice_fwd.py` (pure),
`research/studies/notice_fwd.py` (I/O), workflow `.github/workflows/notice_fwd.yml`, dispatched by `.github/workflows/keeper.yml` every
30 minutes. State on branch `data/notice-fwd` (`state.json`, append-only `notices.jsonl` and `trades.jsonl`, `summary.json`, `counts.json`).
Simulated money, public endpoints, no keys, no LLM (a locked rule decides the side; AGENTS rule 7 is not engaged).

What the authors had read before locking: counts, titles and `t_seen - t_pub` of the first part of `data/news-ingest` (422 rows, 2026-11-26).
No OKX price or any outcome of a notice was read. That read shows the direct sources (OKX, Binance) 40 to 120 s behind their own stamps and
the EquationNews relay (`eqn_rest`) at a median of about 4.5 s; the rules below were written with that known (the speed gate is not a surprise fit).

## Notices (frozen)
- Rows: every item of `data/news-ingest` from OKX (`okx_announcements`), Binance (`binance_listings`, `binance_news`, `binance_delist`), the
  EquationNews relay (`eqn_rest`, `eqn_ws`) and any other source whose title is Korean or names Upbit or Bithumb (so Korean notices count
  when a wire carries them). Wire press releases are not notices.
- Class by title (`core.notice_fwd.classify`, reusing `core.forced_flow` and `core.kr_listing` parsers): `listing` (will list / to list /
  will add, ticker in parentheses or after the verb) = long; `delist` (spot or futures delisting, ticker named) = short; `monitor`
  (Monitoring Tag extended to a coin) = short; `kr_listing` (KRW market opened) = long; `kr_delist`, `kr_caution` = short. Price-alert bot
  lines ("Perp Monitor: X +6% in 10 seconds"), Alpha, TradFi, margin, P2P, earn, airdrop, tournament and update notices are not notices.
- Instrument: `<COIN>-USDT-SWAP`, live on OKX at the time of the run; a coin without one is counted `no_perp` and not traded.
- Cluster = (class, coin) within 7 days of its first row, over all sources; one trade per cluster.

## Speed gate (frozen)
- A row is fast only if `res` is `s` (second-resolution stamp) and 0 <= `t_seen - t_pub` <= 25 s, so that entry at `t_seen + 5 s` is within 30 s
  of the stamp. The cluster clock is the earliest `t_seen` among its fast rows; a cluster with no fast row is counted `too_slow`, not traded.
  For `eqn_*` rows `t_pub` is the newswire's relay time, not the exchange's: the clock is the relay's, and when a direct row of the same
  cluster exists the difference of the two `t_pub` is reported (`pub_gap_s`, descriptive).
- **Test 0 (outcome-free, per source):** a source with at least 20 second-resolution items and a median `t_seen - t_pub` above 25 s is killed
  (never traded again, flag sticky). Counts and latency per source are in `counts.json` / `summary.json` every run.

## Entry, exit, costs (frozen)
- Entry time `t_seen + 5 s`. Price: the first OKX trade print at or after that second (`market/history-trades`, timestamp paging; the walk must
  cross below the entry second so the earliest print is known). The ticker at entry is not used: the ledger runs from the published parts
  after the fact on Actions, and a pod-side quote reader is outside the plan (stop list 6). If the tape fails three runs in a row the
  fallback is the open of the first 1 m bar at or after the entry second (`entry_src = bar`, a delay of up to 65 s); such rows are
  logged and reported but are **never evidence**.
- Holds 5 min, 60 min, 4 h. Primary hold 60 min; the others are reported only. Exit price: first print at or after entry + hold (bar open fallback).
- Costs: entry filled 0.15% against the side; 0.25% more charged (fees 0.10% plus exit slippage 0.15%): 0.40% round trip. Funding assumed as a
  cost 0 / 0.03% / 0.10% for 5 min / 60 min / 4 h. The 2x-cost check doubles every cost.
- Controls: (a) random side (SHA-256 of cluster id and hold) on the same two fills; (b) no-notice control: the same coin, side and hold with the
  entry one day earlier (same tape rules), reported as `nn_net`.
- A cluster whose entry cannot be filled in three runs is `no_entry`; one whose exits cannot be filled 6 hours after the last hold is `expired`.

## Evidence, minimum n, kill and found (frozen)
- Unit = one cluster, its 60-minute row with a tape entry. Paired e-process (`core.sequential.EProcess`, alpha 0.05, e >= 20, unit = clip(net)
  - clip(random-side net), clip 10%).
- **Minimum n = 30 traded tape-entry clusters** (about 10 weeks at the plan's prior of 5 a month; 3 a week if the Korean leg is relayed).
  No kill or found verdict before n = 30; before then the verdict is `underpowered`.
- **Kill at n >= 30 if any holds** (primary hold): mean net <= 0; mean gross < 0.8% (2x the round trip); mean of (net - random-side net) <= 0;
  mean of (net - no-notice net) <= 0; cluster-level x < 0.2 where x = (clusters per 30.4375 days) * (mean / sd)^2 of net.
- **Found** needs n >= 30, no kill reason, e-process `edge` and mean net at 2x costs > 0. Entering a book is a separate dated components
  addendum (AGENTS rule 5); nothing here changes the event book.
- **Deadline 2027-02-06:** with n < 30 on that date the result is `not_found (underpowered)`.
- No class, source list, gate, hold, cost or clip changes after the first forward settlement; a change is a new dated protocol and ledger.

## Known limits
- Paper fills on a print, no queue or depth; thin perps may not fill 147 USD at that price. Wire items can be later than the exchange's own post; the
  relay clock cannot be checked against the exchange stamp unless a direct row exists. About 5 clusters a month are expected (plan prior), so the
  ledger is slow by construction.
