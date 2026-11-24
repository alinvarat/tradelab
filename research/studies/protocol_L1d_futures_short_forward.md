# Protocol L1d: 7-day short after a Binance futures-launch notice (forward only)

Locked 2026-11-24, before any forward data. Origin: L1c run 1 (`RESULTS.md`), where the 7-day return after these notices was negative in train, validation and test (post hoc, so it is tested only on new events).

- **Events:** new "Binance Futures Will Launch USDⓈ-Margined <SYM>USDT ... Perpetual" notices, parsed by `core.screens.binance_futures_symbols`, first seen by the Kuber collector (polled every 30 s); notices older than 15 minutes when first seen are not events.
- **Tradeable:** the coin has a USDT spot market on KuCoin, else Binance, at entry.
- **Entry:** short at the bid 60 s after first sight. **Exit:** buy back at the ask 7 days later. Benchmark: BTC-USDT mid on the same venue (the result is the coin's fall relative to BTC).
- **Result per event:** -(exit_ask / entry_bid - 1) + (BTC return), minus 0.2% fees and 0.7% assumed perp funding for 7 days (0.03% per 8 h, paid by the short; real funding is not collected by this ledger and is reported as a gap).
- **Sizing:** 20% of the L1d ledger equity per event, no leverage, separate 147 USD ledger from L1b.
- **Decision:** `core.sequential.EProcess(lo=1.0, hi=5.0)` on one value per UTC day of exit; edge at e-value 20, no edge when the negative side reaches 20. No change after the first event without a new dated protocol.
