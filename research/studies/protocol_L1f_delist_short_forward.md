# Protocol L1f: 4-hour short after a Binance delisting notice (forward only)

Locked 2026-11-24, before any forward data. Origin: L1e run 1 (`RESULTS.md`): the 4h short was positive in train, validation and test, but was not the locked pick (post hoc, so only new events count).

- **Events:** new "Binance Will Delist <SYM>, ... on <date>" notices (catalog 161), parsed by `core.screens.binance_delist_symbols`, first seen by the Kuber collector (polled every 30 s); notices older than 15 minutes when first seen are not events.
- **Tradeable:** a USDT spot quote on KuCoin, else Binance, at entry.
- **Entry:** short at the bid 60 s after first sight. **Exit:** buy back at the ask 4 h after entry, or earlier at the first poll where the ask is 25% or more above the entry bid (stop; the collector polls about every 30 s, so the fill can be worse than the stop). Benchmark: BTC-USDT mid on the same venue.
- **Result per event:** -(exit_ask / entry_bid - 1) + BTC return, minus 0.2% fees and 0.1% assumed borrow/funding.
- **Sizing:** 20% of a separate 147 USD L1f ledger per event, no leverage.
- **Decision:** `core.sequential.EProcess(lo=1.0, hi=5.0)` on one value per UTC day of exit; edge at e-value 20, no edge when the negative side reaches 20. No change after the first event without a new dated protocol.
