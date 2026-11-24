# Forward market data (Kuber collectors), started 2026-11-24

Collected by `core/market_collect.py` inside the app, stored on the volume at `/app/data/collect/<stream>/YYYY-MM-DD.jsonl.gz`. Status: `/api/collect`. No trading, no keys, no LLM. Writing pauses when less than 200 MB is free.

| Stream | What | Every | For idea (research/IDEAS_codex_20261124.md) |
|---|---|---|---|
| `venues` | best bid/ask: Coinbase BTC-USD, ETH-USD, USDT-USD; Kraken XBTUSD, ETHUSD, USDCUSD, USDTUSD; Binance BTCUSDT, ETHUSDT, USDCUSDT. Fetched in parallel; `t` = request time, `rx` = receipt time, `err` = venue errors | 5 s | 2 cross-venue lead–lag, 5 stablecoin re-peg |
| `deribit` | every BTC/ETH option expiring within 30 days: bid, ask, mark, mark IV, underlying, open interest, volume | 30 min | 3 option-smile dislocations |

Rules: a strategy on this data gets its own protocol **locked before** looking at the holdout. The holdout window Codex suggested is Jan–Mar 2027 (venues) and Jan–Jun 2027 (options). Data before the protocol date may be used to design the rule only.

The one-month sprint has a separate [2026-11-24 protocol](protocol_sprint_20261124.md) for the venue, stablecoin and Deribit collector streams. It fixes the November 25–December 25 window before the first eligible observation. The January windows above remain available for later independent confirmation.
