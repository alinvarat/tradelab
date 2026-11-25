# Protocol Thin B forward collector FB1 (synchronous basket quotes)

Locked 2026-11-25, before the first poll. Rules in `research/studies/RESULTS.md` section "Thin B". Simulated money only; public market-data endpoints, no keys.

- **Why:** the historical B3/B4/B6/B7 baskets use recorded trades (asynchronous) or hourly candle quotes; phantom arbitrage from asynchronous prices is the main risk. FB1 stores synchronous top-of-book quotes.
- **Poll (hourly, planned job `thin_b` in `research.yml`, state on branch `data/thin-b-forward`):** open Polymarket events with `negRisk` true, `negRiskAugmented` false, 3-12 markets (gamma `bestBid`/`bestAsk` per market); open Kalshi events with `mutually_exclusive` true and 3-30 markets (`yes_bid`/`yes_ask` and sizes from `/markets`).
- **Stored row:** event id, venue, time, N, sum of asks, sum of (1 - bid) (the NO basket), minimum top-of-book size, and the per-leg quotes, only when sum asks <= 1.00 or NO cost <= N - 1.
- **Verdict:** after >= 4 weeks and >= 30 events, settle each stored event from its resolution: mean net of fees (Kalshi 0.07 p (1 - p) per leg, Polymarket none) and a 0.5 cent haircut per leg, positive at double cost, with nothing-won events counted as losses.
- **Status 2026-11-25:** registered only; the collector code is not yet written (see the PR description).
