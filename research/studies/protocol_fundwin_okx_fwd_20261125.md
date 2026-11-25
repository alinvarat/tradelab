# Protocol: fundwin_okx_fwd, forward paper ledger of fading the paying side of OKX funding, locked 2026-11-25

Locked before any forward data. Code: `core/okx_fund_fwd.py` (pure), `research/studies/fundwin_okx_forward.py` (I/O), workflow
`.github/workflows/fundwin_okx.yml`, dispatched by `.github/workflows/keeper.yml` about 30 minutes before each settlement.
State on branch `data/okx-fwd` (`state.json`, append-only `trades.jsonl` and `preds.jsonl`, `summary.json`).
Why: the historical funding-window screens (fundwin1 to fundwin3) could only reconstruct the predicted rate (correlation 0.62 with the
settled rate on train); OKX publishes its own predicted rate, so this tests the real signal forward. No key, no order: public data only.

## Signal and trades (frozen)
- Universe: every live `*-USDT-SWAP` on OKX whose published `fundingTime` is the next settlement T of the 8-hour grid (00:00, 08:00,
  16:00 UTC). Instruments on other schedules are not traded.
- Reads: at T-15, T-5 and T-1 minutes (each read = `public/funding-rate?instId=ANY` and `market/tickers?instType=SWAP` at the same moment).
  The predicted rate is the `fundingRate` field of that read.
- Six cohorts = entry minute (15, 5, 1 before T) x threshold on |predicted rate| (0.3%, 0.5%). At a read, every instrument above the
  threshold opens one paper trade against the payer: predicted rate > 0 (longs pay): short at the measured bid; predicted rate < 0:
  long at the measured ask. Equal weight inside a cohort; one trade per instrument per cohort.
- Exit: one read at T+1 minute: a short is bought back at the measured ask, a long is sold at the measured bid.
- Costs: taker fee 0.05% on each fill (0.10% round trip) and the measured bid/ask on both fills (paid through the fill prices). The 2x-cost
  check subtracts the fees and the paid half-spreads a second time.
- Funding: the settled rate is `realizedRate` of `public/funding-rate-history` for T (read at T+100 s); a short receives a positive rate.
  Net return per trade = side * (exit/entry - 1) - 0.0010 - side * settled rate.
- Control: the same two fills with a random side per trade (fixed by a SHA-256 of `T|instrument|cohort`), same fees, same settled rate.
- A trade whose exit book or settled rate is missing is dropped and counted; a cohort read that starts more than 20 seconds late is
  skipped and counted (`late_cohorts`), a run that cannot reach a settlement within 40 minutes counts as `missed`.

## Evidence and verdict (frozen)
- One unit of evidence = one settlement of one cohort: the mean net return over its trades, minus the mean control return of the same
  trades. Units are fed in time order to a paired e-process (`core/sequential.py`, `EProcess(alpha = 0.05/6, lo = 0.05, hi = 0.05,
  paired = True)`); unit values are clipped to [-5%, +5%] for the e-process only, raw means are reported with the number of clipped trades.
- A cohort verdict is **edge** only if all hold: the paired e-process rejects (e-value >= 120), at least 60 units, raw mean net return
  per trade > 0, raw mean net per trade at 2x costs > 0. It is **no edge** when the paired e-process rejects the other way. Otherwise
  it continues. The family has six cohorts, hence alpha 0.05/6.
- No cohort, threshold, cost or clip changes after the first forward settlement. A change is a new dated protocol with a new ledger.
- Tracking report (not a verdict input): for every instrument that settled at T and had |predicted rate| >= 0.05% at some read, the
  predicted rate at -15/-5/-1 against the settled rate: n, median and p90 absolute error, bias, correlation.

## Known limits
- Paper fills at the quoted bid/ask of a snapshot; no queue, no depth: size for 147 USD is far below top-of-book on liquid swaps but
  not on illiquid ones. The settled-rate lookup needs the history endpoint to publish within 100 seconds of the settlement.
- Three settlements a day, so the 60-unit minimum takes about 20 days per cohort and the e-process longer.
