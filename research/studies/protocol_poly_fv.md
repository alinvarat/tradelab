# Protocol poly_fv: Polymarket short-horizon crypto markets vs digital-option fair value

Locked 2026-11-25, before any rule was evaluated (the data probe, Actions 45558079208 / 45558814324 / 45560922469, ran first and only counted markets and read field shapes). Simulated money only; public endpoints, no keys, no LLM.

## Data probed (what exists)
- Gamma `/events` needs `Accept-Encoding: gzip`. Series: hourly `btc-up-or-down-hourly` (id 10114) and the same for ETH/SOL/XRP; daily `above-on` ladders (`<coin>-above-on-<month>-<day>[-<year>]`); also 5m/15m series (not used here). Hourly "Up or Down" events exist from July 2025 (earlier ones are a different "candle" format); `above-on` daily ladders exist before that.
- Tag-filtered (`tag_slug=crypto`) one-day windows return ~90 closed crypto up-or-down events per day from Aug 2025 to Nov 2026 (paging with `offset`).
- Event `eventMetadata.priceToBeat` / `finalPrice` give the hourly strike (Chainlink). Resolution source is Chainlink streams, not Binance: Binance fair value carries a basis; payoffs come from the market's own resolution.
- Data API `GET /v2/trades?condition=<conditionId>&limit=1000&cursor=` returns fills for resolved markets (side, outcome_index, price, size, timestamp). CLOB `prices-history` has 1-minute points but those are not fills.
- **Fees:** crypto markets carry `feesEnabled: true`, `feeType: crypto_fees_v2`, `feeSchedule {rate, exponent, takerOnly}` (a sampled daily market: rate 0.01, exponent 1; `takerBaseFee` 1000). Fee per share = `rate x (p (1 - p)) ** exponent`, charged on every taker fill (entry and early exit). Applied per market from its own schedule; a fee market without a schedule uses rate 0.25, exponent 2 (counted in gaps). Non-fee markets pay none.

## Universe
Resolved binary markets (`outcomePrices` exactly 0/1, first outcome Up or Yes) of: hourly `<coin>-up-or-down-...-<h>(am|pm)-et` events and daily `<coin>-above-on-...` ladders, coins bitcoin, ethereum, solana, xrp, scheduled end 2025-08-01 .. 2026-11-30 (up to the data available). Spot: Binance spot 1m klines from data.binance.vision (BTC/ETH/SOL/XRP USDT). Shards: one job per (month, coin), 64 jobs.

## Fair value
Driftless lognormal digital: `P(Yes) = Phi(ln(S / K) / (sigma sqrt(tau)))`; S = close of the last complete 1m bar before the decision time; K = `priceToBeat` (hourly; fallback the Binance 1m open at the hour start) or the strike in the question (daily above); sigma = std of 1m log returns over the trailing lookback; tau = minutes to the scheduled end. Daily markets with |ln(K/S)| > 0.5 are dropped.

## Rules (one family, 54)
thresholds {5, 8, 12} cents x decision offsets before the scheduled end {60, 30, 10} min x volatility lookbacks {60, 240, 1440} min x exit {hold to resolution, exit at fair}.
- Market price = last recorded trade (yes-equivalent) before the decision time, at most 30 min old. dev = fair - price. Buy Yes if dev >= thr, buy No if dev <= -thr; otherwise no bet.
- Fill (Thin B model): the first recorded BUY trade on the wanted token between decision + 300 s and + 1500 s (never later than end - 60 s), size x price >= 10 USD, price in [0.01, 0.985]; fill price + 0.5 cent haircut + the market's taker fee. No fill, no bet.
- Exit at fair: first recorded SELL trade (size x price >= 10 USD) on our token after fill + 300 s and before end - 60 s with price >= our fair value in that token; sold at that price - 0.5 cent haircut - taker fee; else hold to resolution.
- Stake: capped per bet (5 percent of the 147 USD ledger = 7.35 USD); the per-bet return is on stake, so the cap does not change the statistics.
- Random control, paired per bet: the same market and time, buying either side at its own fill (mean of the two sides' net returns, hold). Edge vs control = rule net - control net.

## Splits and decision
By scheduled end: train 2025-08-01..2026-02-28, validation 2026-03-01..2026-06-30, test 2026-07-01..2026-11-30. Rolling folds (2 months): Mar-Apr, May-Jun, Jul-Aug, Sep-Nov 2026.
- **Stage 0:** on train, n >= 30 bets and monthly x = bets/month x (mean/std)^2 >= 0.2 (0 if mean <= 0). Reported for all rules.
- **Pass:** stage 0 AND Holm-adjusted (family of all 54) one-sided p < 0.05 of the paired edge vs control on validation (UTC-day cluster-robust standard error, normal approximation) AND validation and test mean net > 0 AND validation and test edge vs control > 0 AND mean net > 0 in more than half of the folds with >= 5 bets.
- x per month (validation + test) reported for every rule. Nothing is tuned after the run; a change needs a new dated protocol.

## Persistence and forward
Per-bet candidate rows (every market x offset x lookback with a fair value and a price, with both sides' fills and sell records) are stored as `rows/rows_NNN.jsonl.gz` on branch `data/poly-fv-rows`, with `summary.json`. If a rule passes, a forward paper ledger is registered by a new dated protocol and dispatched by `keeper.yml`.

## Known limits
Trade prices are executed prices not quotes; our 10 USD may move thin books; Binance vs Chainlink basis; only markets that resolved normally; fills later than the decision time are real trades, so the fill window (decision + 5 to + 25 min) lets price drift against the fair value computed at the decision time (this is a cost, not a leak); `priceToBeat` is the market's own published strike known at the hour start.

## Addendum 2026-11-25 (pipeline fixes after run 1; rules, thresholds, splits and gates unchanged)
Run 1 (Actions 45561319446, commit 3df678c) used code with these defects, found by reading shard 0 before any verdict was taken: (1) the daily-ladder strike was parsed from `groupItemTitle` (">117k" in 2025) so every daily market was dropped as implausible: the strike is now parsed from the question text (`above $56,000`); (2) trade feeds above 12 pages were dropped: now up to 30 pages, and a truncated feed is kept when its oldest fetched trade is more than 95 minutes before the end (pages are newest-first, so only early trades are lost); (3) sell records were capped at 12 per token, silently turning far exit targets into holds: cap removed. Rows now also carry `won` and the merge prints a calibration check (token-0 win rate for 10-minute rows with fair > 0.9 and < 0.1, per kind). Run 1 is reported as hourly-only; run 2 (all 64 shards, fixed code) is the family result.

## Addendum 2 2026-11-25 (pipeline fix after run 2, Actions 45565161994; nothing about rules, splits or gates changes)
Run 2 dropped 144,944 markets as `no_strike`: from 2026 the `<coin>-above-on-<date>-<h>(am|pm)-et` slugs are **hourly** above-X ladders (about 20 strikes per hour, question "Bitcoin above 84,600 on October 9, 8PM ET?" without a dollar sign, found by a probe of one day, Actions 45567864850). The strike is now parsed as the number after "above" with an optional `$`; these events keep the label `daily` in the row files (kind = "above ladder") and use the same rules. The strike plausibility check (|ln(K/S)| <= 0.5 at one hour before the end) now runs before the trade download. Run 3 (all 64 shards) is the family result; runs 1 and 2 are discarded as defective (run 2 stage 0: 0 of 54 rules, no pass, shown only as a pipeline check).

## Result of run 3 (Actions 45568094560, 64 of 64 shards, 862,575 candidate rows; rows and summary on branch `data/poly-fv-rows`)
247,462 markets listed (hourly Up/Down plus above ladders, 4 coins, Aug 2025 - Nov 2026); 35,151 had no recorded trades, 2,792 feeds truncated or failed, 1,365 strikes implausible. Calibration check passed: token-0 win rate 0.982 where fair > 0.9 and 0.019 where fair < 0.1 (hourly), 0.998 / 0.003 (above ladders). **Stage 0: 0 of 54 rules; passed: none.** Best train x per month 0.24 (d12_o60_l240_fair, only 14 train bets, validation +4.9 percent, test -19.5 percent); highest validation mean +6.1 percent (d12_o60_l1440_hold, n 41, edge vs control p 0.35, test -7.5 percent); the many-bet rules (5-cent threshold, 10-minute offset) have train x near 0 and negative validation and test means. Family verdict: no edge after fills, haircut and fees; no forward ledger registered.
