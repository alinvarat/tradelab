# H4 BTC lead-lag on perps (pre-registered 2026-11-25)

Hypothesis (not a result): after a sharp BTC move, alts with the highest beta that have not yet moved follow within an hour.
Full locked rules: `research/studies/RESULTS.md`, section "H4 screen". Code: `core/screens.py` (H4 section), study `h4_btc_leadlag` in `research/studies/run.py`, tests `tests/test_h4_leadlag.py`.

- Run: `gh workflow run research_sharded.yml --ref line/h4_btc_leadlag -f study=h4_btc_leadlag -f shards=20` (artifact `study-h4_btc_leadlag`; summary has `verdict`, `checks`, `base`, `double_cost`, `paired_vs_random_lagger`, `shard_gaps`).
- Data: `data.binance.vision` USDT-M 5-minute klines and settled funding, every perp ever listed, 2021-12 to 2026-10. Each shard reads the same BTCUSDT series plus its own symbols, so no shard needs more than a few hundred files.
- Do not change the thresholds after seeing a result; a variant needs a new dated protocol.
