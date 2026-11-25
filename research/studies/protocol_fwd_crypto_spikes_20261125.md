# Protocol: forward paper tests of two inconclusive crypto spike screens (L12B_F and L8B_F)

Written and committed 2026-11-25, before the first forward event. Paper money only, no keys, no orders. Code: `core/fwd_crypto.py` (logic), `research/studies/fwd_crypto_spikes.py` (I/O), job `fwd_crypto` in `.github/workflows/research.yml`. Tests: `tests/test_fwd_crypto.py`.

## What these are (and are not)
Both are **forward tests of an inconclusive screen**. Neither screen passed. L12b (`RESULTS.md`, "L12b screen") was inconclusive at base cost (validation h24 +0.49%, p 0.12; test +1.52%) and killed at double cost; L8b (`RESULTS.md`, "L8b screen") was inconclusive at base cost (h1 validation +0.52%, p 0.17) and killed at double cost. Both are run forward only because forward data is the one unbiased test and paper money is free. A good forward result would justify a larger forward test, not any use of money. Neither line may be described as "passed" in any file. These tests do not reopen the kill at double cost; they only ask whether the base-cost result survives on new data against a same-time random control.

## Frozen rules
Event definitions are the screens' own functions, unchanged: `core.screens.hourly_shock_rows` (side -1, constants `L12_MOVE` 8%, `L12_REL` 6 points beyond BTC, `L12_MIN_QV` 200k USDT 30-day average hourly quote volume, one event per coin per 24 h) and `core.screens.gainer_fade_rows` (`L8_THRESH` 20% UTC-day gain, `L8_MIN_QV` 2M USDT 20-day average quote volume, one event per coin per 7 days). Both lines short the coin and are BTC-hedged (the BTC short gain over the same window is subtracted), 0.4% round trip, funding actually settled during the hold added (positive rate: longs pay shorts, so the short receives it; negative: the short pays). Short gain is `1 - exit/entry` (`core.screens.short_gain`).

| | L12B_F | L8B_F |
|---|---|---|
| Event | one-hour spot bar H closes >= +8% and >= 6 points above BTC's same hour | UTC day D closes >= +20% vs its open |
| Entry price | open of hour H+1 | open of day D+1 (00:00 UTC) |
| Exit price | close of the 24th hour held (entry + 24 h) | close of day D+1 (entry + 24 h) |
| Cooldown | 24 h per coin | 7 days per coin |

Entry price is the screen's documented price (the next bar's open). The runner finds events about 5 minutes after the bar opens, so a real fill would be slightly different; this is the same optimism the screens had, and it is stated rather than corrected. A coin counts only if a perp existed: see the source swap below.

Events begin with the first hourly run, which records `start_ts` (that run's hour) in the state file. Only shock bars that open at or after `start_ts` count: for L12B_F the hour that opens at `start_ts` (entry one hour later), for L8B_F the first UTC day that opens at or after `start_ts`. No bar that began before this protocol was merged is used. The state file lives in branch `data/fwd-crypto-spikes` and is created after this protocol is merged.

## Data source swap (stated before any event)
The probe (`research/studies/fwd_probe.py`, workflow run 45519155304 on GitHub Actions) found: `fapi.binance.com` and `api.binance.com` answer **HTTP 451**, Bybit answers **403**, while `data-api.binance.vision` (spot klines, exchangeInfo) and OKX public API (`/api/v5/public/instruments`, `funding-rate-history`) answer **200**. Therefore:
- Spot hourly/daily bars and quote volume: `data-api.binance.vision` (Binance spot, the same venue as the screens).
- "Live perp" and funding: **OKX USDT-margined swap** `<BASE>-USDT-SWAP` (state `live`), funding from OKX `funding-rate-history` (realizedRate when present). This replaces the screens' Binance perp; a coin counts when the OKX swap is live and a funding rate settled in the 24 h before entry (L12b's own test). Coins whose OKX base name differs from the Binance one (for example 1000-prefixed tokens) are treated as having no perp. This is a real change from the screens: OKX funding and its coin list differ from Binance's, so results are an approximation of "Binance perp" and will be reported as such.
- Prices stay spot prices (the screens used spot too). Funding on the BTC hedge leg is not modelled (the screens did not either).

## Same-time random control
For every event a control is drawn at the same entry bar: the eligible set is every spot coin with a live OKX swap and a 24 h (L12B_F: average hourly quote volume >= 200k USDT) or 20-day (L8B_F: >= 2M USDT) liquidity level above the screen's own threshold, excluding the event coin. The draw is a shuffle seeded by `sha256(line|entry_ts|event_symbol)`, taking the first coin with an entry bar. The control is shorted at the same entry time, held the same 24 h, hedged with BTC, with the same 0.4% and its own settled funding. Controls do not need to have had a spike.

## Sizing (147 USD paper ledger per line)
Each line has its own ledger starting at 147 USD. Per taken trade the stake is 10% of the line's current (realized) equity, 1x (no leverage): the stake is the collateral and a loss cannot exceed it (a short is liquidated when the price reaches 2x the entry; any bar high >= 2x entry in the hold books exit = 2x entry, and net return is floored at -100%). At most 5 taken trades are open at once per line; events beyond that are tracked as shadow trades (stake 0) so the evidence uses every signal, and the number skipped is reported. Events are processed in entry-time then symbol order.

## Evidence and stopping rule
- Unit: one value per UTC exit day (mean of that day's closed events), as `core/sequential.py` requires. Values are net returns on the stake, clipped to [-1, 3].
- Two e-processes (`core.sequential.EProcess`, alpha 0.05, evidence at 20): the line's own net return (`lo=1, hi=3`) and the net return minus the control's (`lo=1, hi=3, paired=True`).
- **Early stop:** verdict `edge` only when both reach 20; verdict `no edge` as soon as either negative side reaches 20. `edge` here means "worth a larger forward test", not a pass of the screen.
- **Fixed maximum:** at **150 closed events** (taken or shadow) with no early verdict, one fixed-sample read is made on exactly the first 150 closed events (later closings cannot change it): day-cluster bootstrap p of the mean net return > 0 and of the paired mean > 0 (`core.screens.block_bootstrap_p`, seed 7); both < 0.05 reads `positive at max`, otherwise `inconclusive at max`. Combined false-positive rate of the two stopping paths is at most about 0.10. The e-processes are conservative, so an early verdict will need a large effect; `inconclusive at max` is a likely outcome and is reported as such.
- Always reported with the verdict: ending equity, worst drawdown of the ledger, mean net, mean control, hit rate, worst trade, funding paid, number of shadow events. The results at double cost (extra 0.4% per trade) are also reported; a result that is positive only at base cost is not described as positive.
- No rule, threshold, window, size or source in this file changes after the first event without a new dated protocol. Once a line has a verdict other than `continue` it opens no new events (open trades still close and are reported). A failed data fetch for any candidate event stops the line from advancing and is retried next hour; the state records `gap_hours_missed` when more than 24 h of hours were skipped (events in the gap are lost, not back-filled).

## Operations
Hourly at minute 5 UTC the owner's machine dispatches `research.yml` with `study=fwd_crypto_spikes` (GitHub's cron never fires in this repo). The job restores `fwd_crypto_state.json` from branch `data/fwd-crypto-spikes`, detects new events on the last closed bars, closes positions that reached 24 h, and pushes the state plus `fwd_crypto_summary.json`. Read the state with `git show origin/data/fwd-crypto-spikes:fwd_crypto_summary.json`.
