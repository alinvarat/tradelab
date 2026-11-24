# Locked studies: results (run 2026-11-23 21:08 UTC on GitHub Actions, run 45266434091)

Rules: `research/news_backtest/protocol_next.md`, including the addendum, all locked before this run. Universe: the 148 stocks in `core/universe.py`, Yahoo daily bars over 10 years, 0.09% cost per side. "Pass" means all five checks in the pass rule. Raw rows and summaries are the `*.json` files next to this one.

## (d) Turn of month: harness check
| | n | gross | control gross | net | paired diff | train / val / test diff | block p (train+val) | net 2× | pass |
|---|---|---|---|---|---|---|---|---|---|
| Turn of month | 16,586 | +0.46% | +0.24% | +0.28% | +0.22% | +0.28% / −0.30% / +0.61% | 0.024 | +0.10% | **no** (validation < 0) |
| Placebo (+20–60 sessions) | 16,339 | +0.22% | +0.24% | +0.04% | −0.02% | −0.02% / +0.01% / −0.03% | 0.59 | −0.14% | no |

- The harness behaves correctly. The placebo paired diff is about 0 (block p 0.59), so the code shows no sign of lookahead or of control leakage.
- The turn-of-month diff was +0.22%, larger than the 0.15% written down in advance. It still fails the pass rule, because validation (2023–24) was −0.30%. This fits the known turn-of-month effect, which is real but unstable. It is not a tradable edge under the rule.

## (c) Momentum 12-1, top decile long/flat vs the equal-weight basket
| n months | gross / month | basket / month | net / month | diff / month | train / val / test diff | block p (train+val) | net 2× | largest month share | pass |
|---|---|---|---|---|---|---|---|---|---|
| 107 (2017-12 → 2026-10) | +3.62% | +1.46% | +3.43% | +2.16% | +2.17% / +2.37% / +1.90% (22 months) | 0.002 | +3.25% | 9.8% | **yes** |

- After costs, the top-decile book grew 20.7× from 2017-12 to 2026-10, with a worst drawdown of −39%. The basket grew 3.3×, with a worst drawdown of −29%. Test months were volatile, from −21% to +28%.
- **The pass is almost certainly inflated by the universe.** `core/universe.py` was written in 2026 and lists stocks that are famous now (PLTR, SMCI, MSTR, ENPH, SE, SHOP and others). Today's winners are therefore in the universe from the start, and a delisted loser can never be picked. The most frequent picks were ENPH, NVDA, SE, AMD, SHOP, MSTR and PLTR. The protocol listed survivorship as a known limit. That limit means this result **cannot be used as evidence of a tradable edge**.
- The way to confirm it is a point-in-time universe, for example the S&P 500 members as of each month-end, or ETFs/sectors that existed throughout. That test needs a new protocol, locked before any run. Even if it confirmed, about +2% a month above the basket is far below the 3× a month target.

## (a) 8-K by item: run 45269334155 (2026-11-23 21:35 UTC), 148 stocks, 8-K since 2018
Paired diff = event net minus a random same-class stock bought at the same open. "train / val / test" are the diffs in each split.

| Item | H | n | net | diff | train / val / test | block p (train+val) | net 2× | pass |
|---|---|---|---|---|---|---|---|---|
| 2.02 results | 1 | 3937 | −0.14% | +0.10% | +0.30% / −0.08% / −0.05% | 0.03 | −0.32% | no |
| 2.02 | 3 | 3934 | +0.04% | −0.14% | −0.05% / −0.36% / −0.09% | 0.86 | −0.14% | no |
| 2.02 | 5 | 3929 | +0.28% | −0.40% | −0.68% / −0.35% / +0.03% | 1.00 | +0.10% | no |
| 1.01 agreement | 1 / 3 / 5 | ~970 | −0.21% / −0.07% / −0.00% | −0.07% / −0.35% / −1.04% | test −0.63% / −1.23% / −1.81% | ≥ 0.28 | < 0 | no |
| 5.02 officer change | 1 / 3 / 5 | ~2420 | −0.28% / −0.13% / −0.12% | −0.06% / −0.25% / −0.40% | test −0.30% / −0.37% / −0.10% | ≥ 0.37 | < 0 | no |
| any of the three | 1 / 3 / 5 | ~7130 | −0.18% / −0.02% / +0.14% | +0.04% / −0.18% / −0.44% | test −0.16% / −0.22% / −0.11% | 0.02 / 0.95 / 1.00 | < 0 | no |

- No item passes at any horizon. The only small p values (2.02 H1, "any" H1) come entirely from train. Validation and test are both negative, and the result is negative at 2× cost.

## (b) Form 4 officer/director purchases ≥ 50k USD: run 45269343194 (2026-11-23 21:26 UTC)
925 events from 2018 onward. 733 have the exact EDGAR acceptance time; the rest use the conservative filing-date stamp.

| H | n | net | diff | train / val / test | block p (train+val) | net 2× | pass |
|---|---|---|---|---|---|---|---|
| 1 | 925 | −0.02% | +0.18% | +0.14% / +0.30% / +0.19% | 0.17 | −0.20% | no (p, 2× cost) |
| 3 | 925 | +0.13% | −0.36% | −0.74% / +0.52% / +0.28% | 0.88 | −0.05% | no |
| 5 | 925 | −0.08% | −1.36% | −2.35% / +1.28% / −0.01% | 1.00 | −0.26% | no |

- H1 is positive in all three splits (+0.14% to +0.30%), but it is not significant (block p 0.17), and net turns negative once costs exceed 1×. This matches the literature: the drift exists, but it is small in large caps and does not cover costs.
- The H3/H5 means are dominated by fat-tailed controls. The control pool includes HOOD (+85% in 5 days, Aug 2021) and UPST (+84%), because the control is not matched on volatility (a limit stated in `protocol.md`). With every |return| ≥ 50% removed, the H5 diff is still −0.61%. The verdict does not change.
- The protocol's microcap version (wider spreads, at least 0.5% per side) has not been run. Running it would need a new protocol and a new universe.

## Summary of all four
Harness check: the placebo diff is about 0, so the tool works correctly. Pass rule: **only 12-1 momentum passed, and it is untrustworthy because of survivorship bias.** Turn of month, 8-K items and Form 4 all fail. None of them comes anywhere near 3× a month.

## Momentum 12-1 on a point-in-time S&P 500: run 45273979829 (`protocol_pit_momentum.md`)
601 of 771 tickers have bars. Coverage of members was 80–100% (mean 90%), so all 107 months count.

| gross / month | basket | net | diff | train / val / test | block p (train+val) | net 2× | largest month share | pass |
|---|---|---|---|---|---|---|---|---|
| +1.19% | +0.82% | +1.01% | +0.37% | −0.01% / +0.44% / +1.35% | 0.34 | +0.83% | 43% | **no** |

- **The earlier pass came from survivorship.** On the point-in-time membership the diff drops from +2.16% to +0.37% a month, with no significance and nothing in train. Ending equity: 2.4× at 1× leverage, 1.9× at 2×, 1.04× at 3×. No month reached 3× at any leverage.

## DeepSeek reads 2.02 earnings releases, forward-only: run 45274805697 (`protocol_llm_earnings.md`)
The served model was `deepseek/deepseek-v4.1-flash-1017`. 106 filings from 2026-10-20 to 2026-11-23 were each called once; the calls are kept in `llm_earnings_calls.json`, and the protocol says they are never called again.

| H | trades (no skip) | hit | net / trade | net 2× | random direction | diff | always long | block p diff | block p net |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 71 of 106 | 61% | +0.67% | +0.49% | −0.81% | +1.48% | +0.19% | 0.009 | 0.076 |
| 3 | 69 | 54% | +0.99% | +0.81% | −0.87% | +1.86% | +0.31% | 0.059 | 0.095 |
| 5 | 66 | 65% | +1.55% | +1.37% | −0.87% | +2.42% | +0.94% | 0.062 | 0.050 |

- **Locked verdict: "edge candidate"**, meaning H1 and H3 net > 0, H1 block p diff < 0.05, and H1 2× net > 0.
- Caveats: this is one earnings season (one market regime) with only 71 trades. The random-direction control came out unluckily negative (−0.81% where about 0 is expected), which makes the diff larger than it should be. The model's own net is significant only at p 0.076 (H1). It cannot be called confirmed until another season is added.
- As a daily book (equal weight across that day's trades, 21 days, 3.4 trades/day): mean +0.32%/day, sd 1.96%. The best path was 8× leverage, giving 1.32× over the period (worst drawdown −38%). That is far from 3×, because there are too few trades per day and the volatility is high. To reach 3× a month, **more independent trades per day** are needed, from every US company that files 2.02, not just 148 stocks. That needs a new protocol, with costs that rise with lower liquidity.

## DeepSeek earnings reader on every US 2.02 filer: run 45280463314 (`protocol_llm_earnings_wide.md`)
There were 3,475 2.02 filings from 2026-10-20 to 2026-11-22. 2,097 passed the liquidity screen and 1,378 were excluded. The daily indexes for 11-11 and 11-23 returned 403, so filings from those two days are missing. 1,987 new calls were made, and the served model was `deepseek/deepseek-v4.1-flash-1017`.

| new filings only | trades | hit | net / trade | net 2× | random dir | diff | always long | block p diff | block p net |
|---|---|---|---|---|---|---|---|---|---|
| H1 | 1214 | 51% | −0.21% | −0.64% | −0.70% | +0.49% | −0.49% | 0.035 | 0.85 |
| H3 | 1204 | 53% | +0.38% | −0.06% | −0.78% | +1.16% | +0.07% | 0.001 | 0.079 |
| H5 | 1195 | 54% | +0.60% | +0.16% | −0.88% | +1.48% | +0.20% | 0.002 | 0.027 |

- **Locked verdict: "no edge shown"**, because H1 net is negative. The 148-stock result (61% hit at H1) **did not replicate** across the whole market.
- By liquidity tier at H1: the most liquid (≥ 100M/day) netted −0.26%, the middle tier −0.36%, and the thinnest tier +0.12% (with diff +2.18%, made larger by its random control at −2.06%).
- What looks interesting is the slower drift at H3/H5 (H5 net +0.60%, p 0.027). That horizon was not locked as the primary one, so it **cannot be claimed**. It is locked as the primary for the forward test in `protocol_llm_earnings_forward.md`.
- Daily book (H1, 53 trades/day, 23 days): mean +0.34%/day, sd 1.6%. Best path: 1.63× at 10× leverage (worst drawdown −42%). Still not 3×.

## DeepSeek reads every non-earnings 8-K: run 45292092632 (`protocol_llm_8k_other.md`)
3,980 8-Ks without item 2.02, from 2026-10-20 to 2026-11-22 (the 11-11 and 11-23 indexes returned 403). 1,703 passed the liquidity screen and 1,696 were called. The served model was `deepseek/deepseek-v4.1-flash-1017`. The model skipped 78%.

| H | trades | hit | net / trade | net 2× | random dir | diff | always long | block p diff | block p net |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 376 | 47% | −0.86% | −1.29% | −0.99% | +0.13% | −1.03% | 0.36 | 1.00 |
| 3 | 346 | 45% | −1.23% | −1.65% | −0.38% | −0.84% | −1.36% | 0.92 | 1.00 |
| 5 | 311 | 46% | −1.81% | −2.24% | −0.96% | −0.85% | −2.10% | 0.85 | 1.00 |

- **Locked verdict: "collecting" (311/600 H5 trades)**, but every horizon so far is clearly negative and the model's picks are no better than random. Most picks were long (221 long, 90 short), in a set where buying every filing lost 2.1% over 5 days (offerings and bad news dominate non-earnings 8-Ks).
- Daily book (15 trades/day): mean −0.89%/day, ending at 0.80× without leverage.

## DeepSeek on post-release Polymarket questions: run 45328442245 (`protocol_polymarket_llm.md`)
300 markets were eligible, 219 had a price at t0, the model answered all 219, and 100 met the bet rule. The served model was `deepseek/deepseek-v4.1-flash-1017`.

| bets | hit | mean return / bet | at +3¢ slippage | vs random side | block p (return) | block p (diff) | Brier model | Brier market |
|---|---|---|---|---|---|---|---|---|
| 100 | 41% | +15.5% | +8.1% | +17.8% | 0.17 | 0.17 | 0.251 | 0.232 |

- **Locked verdict: "no edge shown".** The positive mean is not significant, and the model's probabilities were *worse* than the market price (Brier 0.251 vs 0.232). The best wins were cheap NO bets against favourites (for example "Bitcoin above $70,000 on Nov 13" at 0.875), which is long-shot luck in a sample of 100.
- Account path (as locked: each bet stakes 10% of equity *including open bets*): October ended at 2.8× because overlapping bets used all the cash, then November wiped it to 0. At 20% stakes, one month was ≥ 3× and the account was still wiped. This is how 3×-a-month accounts actually die.

## Swing timing on point-in-time S&P 500: run 45332168793 (`protocol_pit_swing.md`)
3,594 trades (1.43/day), 61% winners, average hold 4.3 sessions. One compounding book from 2016: 1.80×, worst drawdown −40%. The random-pick control: 1.02×. SPY buy-and-hold: 3.26×.

| monthly net | control | diff | train / val / test | block p (train+val) | 2× cost net | pass |
|---|---|---|---|---|---|---|
| +0.45% | −0.13% | +0.58% | +0.39% / +1.20% / +0.54% | 0.061 | −0.09% | **no** (p 0.061) |

- The timing beats random picks in every split but misses the locked p threshold, and it is flat at 2× cost. It trails SPY because about 40% of the cash sits idle (6 of 10 slots used on average). No month reached 3× at 1–3× leverage.

## News reader v2 vs v1 on held-out earnings: run 45332709844 (`protocol_news_v2.md`)
346 tradeable 2.02 filings from 2026-11-06 to 11-22. LLM cost was **1.89 USD**: 3 samples, 2 documents per filing, which is above the 0.6–0.9 estimate.

| | trades | hit | net / trade | net 2× | vs random dir (p) |
|---|---|---|---|---|---|
| v2 H1 | 193 | 52% | +0.15% | −0.33% | +1.18% (0.08) |
| v2 H3 | 183 | 51% | +0.84% | +0.36% | +3.66% (0.01) |
| v2 H5 | 169 | 52% | +0.51% | +0.01% | +3.26% (0.016) |
| v1 H5 (same filings) | 159 | 45% | −2.45% | −2.92% | −0.66% (0.64) |

- Paired per filing, v2 − v1 at H5 = **+1.56% (block p 0.008)**, H3 +0.77% (p 0.075). v2 reads clearly better than v1: on the same filings it avoided most of v1's losses.
- **Locked verdict: "v2 not better"**, because v2's own H5 net is not significant (p 0.32) and its hit rate is 52% < 55%. Better than v1 is not yet profitable enough to use on its own.

## L1 screen: new listings (pre-registered 2026-11-24, before any data was pulled)
Spec: `ops/lines/L1_listings.md`; code: `core/screens.py` (`listing_returns`, `judge`), study `l1_listings`.
- Events: Binance "Will List ..." notices (catalog 48) and Upbit KRW-market "디지털 자산 추가" notices, 2024-01-01 to 2026-10-31. A coin counts only if it already traded on the pricing venue in the hour before the notice (Binance notices priced on Coinbase USD, Upbit notices on Binance spot USDT).
- Entry: close of the 1-minute bar containing notice + 60 s. Horizons 15m, 1h, 4h (1-minute bars), 1d, 7d (1-hour bars).
- Return: coin minus BTC over the same window (control), minus 0.6% round trip; double cost reported too.
- Splits: 2024 train, 2025 validation, 2026-01 to 2026-10 test. Horizon = best train mean. Block bootstrap by UTC day.
- Pass: validation mean > 0 with p < 0.05, still > 0 without the best 1 and best 5 events, test mean > 0. Kill: validation mean <= 0, p > 0.2, or <= 0 without the best 1 or 5 events. Otherwise inconclusive.
- **Run 1 (2026-11-24, Actions 45369639086): inconclusive.** 65 notices; 15 priced (all Binance notices on Coinbase), 50 had no prior Coinbase market; Upbit returned nothing from the US runner (request failed). Horizon picked on train: 4h. Net abnormal mean at 4h: train +37.4% (n 5, p 0.0005), validation +15.3% (n 4, p 0.064), test +9.5% (n 6, p 0.11); validation without the best event +3.8%. Double cost: validation +14.7% (p 0.08). 9 of 15 events positive at 4h; winners +20% to +57% (COW, ACX, ORCA, AVNT, ZKP, CFG), losers down to -10%. Too few events to pass.
- **Addendum (2026-11-24, before run 2):** same rules, horizon and splits; Binance notices with no prior Coinbase market are priced on KuCoin USDT (1-minute and 1-hour candles), BTC benchmark on the same venue. Results reported in total and per pricing venue. Upbit stays out until a non-US fetcher exists.
- **Run 2 (2026-11-24, Actions 45372512628): killed by the locked rule.** 31 of 65 notices priced (15 Coinbase, 16 KuCoin). The best train mean is now 7d (+183%, driven by ACT +2,073% raw on KuCoin in Nov 2024), and 7d fails: validation +8.4% (p 0.30), test -10.6%, validation without the best event -5.0%.
- Observation, not a pass (the 4h horizon was not the rule's pick in run 2): 4h was positive in every split, train +118% (n 11), validation +10.2% (n 13, p 0.0075), test +9.3% (n 7, p 0.087), double cost validation +9.6% (p 0.014); 17 of 31 positive, median +2.4%. Notices are rare: 65 Binance "Will List" notices in 34 months, about 1 tradeable event a month, far too few for 3x a month alone.
- Next (new hypothesis, to be locked before new data): L1b = fixed 4h hold after a listing notice, tested forward only, on more venues (Upbit, Bithumb, OKX, Coinbase, Bybit notices) to raise frequency; fetchers must run outside the US (Kuber), because Upbit refused the US runner.

## L1c screen: Binance futures-launch and "Will Add" notices (pre-registered 2026-11-24, before any data was pulled)
Code: `core/screens.py` (`binance_futures_symbols`, `binance_add_symbols`, `judge(pick_trim=5)`), study `l1c_binance_notices`. Motivation: L1 had about 1 event a month; these notice types are several a month, and the large L1 winners ACT and COW came through "Will Add" notices.
- Events: Binance catalog 48, 2024-01-01 to 2026-10-31. Futures: "Binance Futures Will Launch USDⓈ-Margined <SYM>USDT ... Perpetual" (1000/1000000 prefixes removed); TradFi, equity, pre-market, pre-IPO, multi-contract, COIN-M and delivery notices excluded. Add: "Binance Will Add <name> (<SYM>) on ...".
- Pricing: the first venue with a market in the hour before the notice, in the order Binance spot (data-api.binance.vision), Coinbase, KuCoin; BTC benchmark on the same venue.
- Entry, horizons, cost (0.6% round trip), BTC control, splits (2024 / 2025 / 2026-01..10), block bootstrap by UTC day and pass/kill rules: as in L1.
- One change from L1, fixed before data: the horizon is picked on train by the mean **without the best 5 train events**, so a single outlier (ACT in L1 run 2) cannot choose it.
- **Run 1 (2026-11-24, Actions 45379100863): killed.** 363 notices parsed (futures 361, add 2 priced of few); 117 priced (Binance spot 38, Coinbase 29, KuCoin 50), 78 with no prior market, 168 without bars at entry; 3.4 priced events a month. Trimmed pick 15m: train -1.8%, validation -1.4% (p 0.88), test -2.3%. No horizon is positive in train; 4h validation +2.1% (p 0.18) only.
- Observation (post hoc, not a result): the 7d return is negative in every split, train -10.2% (n 37), validation -7.5% (n 62), test -8.5% (n 18), so coins tend to fall in the week after a Binance futures launch. This becomes hypothesis L1d (short), testable only on new events: `protocol_L1d_futures_short_forward.md`.

## L1e screen: short after Binance delisting notices (pre-registered 2026-11-24, before any data was pulled)
Code: `core/screens.py` (`binance_delist_symbols`, `listing_returns(side=-1)`), study `l1e_binance_delist`. Earlier work tested a rebound buy around Bybit delisting days (`research/LESSONS.md`), not a short at the notice.
- Events: Binance catalog 161 "Binance Will Delist <SYM>, <SYM> on <date>" notices, 2024-01-01 to 2026-10-31 (pair removals, margin, futures, Alpha and fiat notices excluded).
- Pricing: first venue with a market in the hour before the notice, in the order KuCoin, Binance spot, Coinbase (KuCoin first, because a short is possible there after Binance stops); BTC benchmark on the same venue.
- Return: short from the close of the 1-minute bar containing notice + 60 s, i.e. -(coin return - BTC return) - 0.6% round trip; horizons, splits, bootstrap, trimmed horizon pick (without the best 5 train events) and pass/kill rules as in L1c.
- **Run 1 (2026-11-24, Actions 45392424474): killed by the locked rule.** 107 notices, 105 priced (Binance spot 89, KuCoin 16), 3.1 a month. Trimmed pick 7d: train +31.6% (n 28), validation -69.0% (n 18) because ALPACA (2025-04-24) was squeezed (7d short -1,793%), test +25.7%.
- Observation (post hoc, not a result): the short is positive at 15m to 1d in train and test, and at 1h to 1d in validation. 4h: train +24.5% (p 0.0005), validation +8.5% (p 0.08), test +11.2% (n 47, p 0.0005); double cost validation +7.9%. 91 of 105 events positive at 4h, worst -82% (BSW), best +54%. A short in a coin being delisted carries squeeze risk with no upper bound (ALPACA), so a stop is required for any use. Becomes L1f (forward only): `protocol_L1f_delist_short_forward.md`.

## L1g screen: short after "Binance Alpha Will Remove" notices (pre-registered 2026-11-24, before any data was pulled)
Study `l1g_alpha_remove`, parser `core.screens.binance_alpha_remove_symbols`. Same events window, pricing order (KuCoin, Binance spot, Coinbase), short return, cost, splits, trimmed horizon pick and pass/kill rules as L1e. Motivation: one Alpha removal notice names many tokens, so it may supply more events than L1e/L1f. Tokens with no prior market on the three venues are skipped (many Alpha tokens trade only on DEXs).
- **Run 1 (2026-11-24, Actions 45394637977): no verdict (no data in train or validation).** 132 tokens named in Alpha removal notices, 13 priced (all KuCoin, all in 2026; 119 had no market on KuCoin, Binance spot or Coinbase in the hour before). Test only: 4h short +14.4% (n 13, p 0.0005), 7d +29.5%. Too few events and no train/validation, so nothing is concluded; the forward collector can add Alpha removals with a dated addendum if a DEX price source is added.

## L4 screen: selling Polymarket long shots as a maker (pre-registered 2026-11-24, before any data was pulled)
Spec `ops/lines/L4_polymarket_maker.md`; code `core.screens.longshot_sells`, study `l4_polymarket_longshot`. No LLM. Different from the closed `polymarket_llm` study (model forecasts): this uses price structure only.
- Markets: resolved binary markets with volume >= $50k and end dates 2024-01-01 to 2026-10-31 (Gamma API, up to 6,000 markets). Resolution time = `closedTime`.
- Price: YES daily price history (`prices-history`, fidelity 1440); the last point in the 2 days up to 7, 3 and 1 day(s) before resolution. Either side priced 2c-10c is sold at that price (maker, no fee; the spec's 24 h re-touch fill check is not possible on daily points, so fills are assumed and this is reported as a limitation).
- Return per event: +price if the side loses, -(1-price) if it wins, divided by the locked collateral (1-price). The monthly equivalent (x 30 / lead days) is reported per split.
- Splits by resolution time: train 2024-01 to 2025-06, validation 2025-07 to 2026-03, test 2026-04 to 2026-10. Lead picked on train by the mean without its best 5 events; block bootstrap by UTC day; pass/kill as in L1, plus the spec's rule that the monthly equivalent in validation must exceed 5%.
- Run 1 (2026-11-24, Actions 45406586130): void as a test. Offset pagination stopped after 500 markets, all resolved in 2024 (train only): T-1d train mean +3.8% per event (n 72, p 0.013), T-3d +0.8%, T-7d -0.3%. Fix before run 2 (no rule change): keyset pagination (`/markets/keyset`), max 6,000 markets.
- Run 2 (2026-11-24, Actions 45406857348): void as a test. Keyset pagination reached the 6,000-market cap inside 2024-2025H1, so again train only: 1,740 events; per event T-7d +4.5% (n 1,140), T-3d +4.9% (n 900), T-1d +4.0% (n 360), all p 0.0005; monthly equivalents +19%, +49%, +120%. Fix before run 3 (no rule change): sample each split window separately, up to 4,000 markets each.
- **Run 3 (2026-11-24, Actions 45407180127): VOID, retracted.** It was first reported as a pass, but the keyset pages repeated: the `next_cursor` parameter is ignored by the API (the working one is `after_cursor`), so 12,000 fetched markets were only 75 unique markets, each counted about 40 times. The p-values and "per event" means of runs 2 and 3 are therefore invalid. Fix before run 4 (no rule change): `after_cursor`, de-duplicate by market id. L4f forward stays running because its protocol was locked before data and it measures new markets only.
- **Run 4 (2026-11-24, Actions 45411924081): killed.** Data gate checked by hand (the gate code merged after this run): 12,000 markets fetched, 2,613 long-shot events, 2,613 unique rows (no duplicates); train 1,190 / validation 716 / test 701 rows, with losing events in every split (79 / 54 / 45). Trimmed pick T-1d: train +1.6% per event (p 0.04), validation +0.35% (n 381, p 0.39), test +0.5% (p 0.35); without the best event +0.3%. T-3d validation +0.9% (p 0.24), test +1.6% (p 0.11); T-7d about 0. Even with the free maker fill this model assumes, selling 2-10c long shots is about break-even; the bias in the literature is not large enough here to be worth the tail risk.
- L4f (forward, taker at the bid) keeps running because it costs nothing (no LLM) and its rules are locked, but no screen supports it; it is low priority.

## L3 screen: small caps with an 8-K outside market hours (pre-registered 2026-11-24, before any data was pulled)
Spec `ops/lines/L3_smallcap_news.md`; code `core.screens.smallcap_events`, study `l3_smallcap_news`. No LLM.
- Universe: a seeded random sample (seed 20261124) of 1,500 Nasdaq / NYSE / NYSE American tickers from SEC `company_tickers_exchange.json` (no dashed tickers). Daily bars from Yahoo (2 years), 8-Ks from the SEC submissions API.
- Event: an 8-K accepted from 16:00 ET of the previous session to 09:00 ET of session D; previous close $1-20 and 20-day average dollar volume $1-50M; open gap >= 10% either way. One event per filing.
- Returns (changes from the spec, fixed before data): IWM-adjusted, 1% round trip. Continuation (trade the gap direction) and reversal (against it), open D to close D, and open D to close D+1. Control = IWM over the same window (no free point-in-time small-cap peer set).
- Groups: first matching item of 1.01, 2.02, 5.02, 7.01, 8.01, 3.02, 2.01 (else "other") x gap direction. Each group judged with `core.screens.judge` (trimmed pick on train, data gate). A group passes only if its validation p is below 0.05 / number of groups (Bonferroni) and it has at least 3 events a week.
- Splits: train 2025-05 to 2025-12, validation 2026-01 to 2026-06, test 2026-07 to 2026-10.
- Shorts in small caps may be impossible to borrow in a real app; long-side and short-side groups are reported separately.
- **Run 1 (2026-11-24, Actions 45414890419): killed (no group passes).** Data gate ok overall: 315 events, 315 unique, train 120 / validation 86 / test 73 (36 outside the splits); SEC submissions failed for 385 of 1,500 sampled tickers (rate limit), so the sample is about 1,115 tickers. 13 groups, Bonferroni p 0.0039. The only groups with enough events, item 2.02 (earnings) up and down gaps (95 each, about 1.2 a week), were killed: down gaps, continuation to D+1: validation -1.4%, test -5.3%; up gaps, reversal on D: validation +0.7% (p 0.38), test -4.4%. All other groups had fewer than 10 train or validation events (invalid by the data gate). Too rare in this universe (0.3 to 1.2 events a week per group) to matter for 3x a month even if a group had passed.

## L6 screen: insider purchases in small caps (pre-registered 2026-11-24, before any data was pulled)
Spec `ops/lines/L6_smallcap_insider.md`; code `core.screens.insider_rows`, study `l6_smallcap_insider`. No LLM. Differs from the closed `form4` study (large-cap universe, $50k minimum).
- Events: SEC insider-transaction data sets 2019Q1 onward; officer or director open-market purchase (code P, acquired) totalling >= $25k per Form 4, issuer listed on Nasdaq / NYSE / NYSE American. Availability: the conservative timestamp (filing date + 28 h UTC), entry at the open of the first session after it.
- Small cap at entry: previous close $1-20 and 20-day average dollar volume $0.5-20M. Up to 1,500 issuers (seeded sample if more), Yahoo 10-year daily bars.
- Returns: open to close after 5 and 20 sessions, minus IWM over the same window, 1% round trip; double cost reported.
- Splits: train 2019-2022, validation 2023-2024, test 2025-2026-10. Trimmed pick on train, data gate, pass/kill as in L1c.
- **Run 1 (2026-11-24, Actions 45416703411): killed.** Data gate ok: 3,857 rows, 3,857 unique, train 1,994 / validation 1,047 / test 816, no warnings. 31,399 qualifying purchases at 3,289 issuers; 1,500 issuers priced (seeded sample). Trimmed pick h5: train +0.3% (p 0.18), validation -0.4% (p 0.92), test +0.3%. h20: validation +1.0% (p 0.09), test +0.2%. Double cost: negative everywhere. No usable edge after costs.

## L7 screen: first red day short in small caps (pre-registered 2026-11-25, before any data was pulled)
Spec `ops/lines/L7_first_red_day.md`; code `core.screens.first_red_day_rows`, study `l7_first_red_day`. No LLM, no cost. Hypothesis from the Tim Sykes course table in `ops/knowledge/news_trading.md`, not a proven result.
- Universe: the same seeded random sample (seed 20261125) of 1,500 Nasdaq / NYSE / NYSE American tickers from SEC `company_tickers_exchange.json` (no dashed tickers) used by L3/L6; Yahoo daily bars (10 years).
- Event: session D closes red (`c < o`) after D-1, D-2 and D-3 all closed green (`c > o`) and close(D-1) / close(D-3) - 1 >= 15%. Small cap at D: close(D-1) $1-20 and 20-day average dollar volume $1-50M. One event per symbol per streak (a new streak cannot start until the price has run again).
- Entry: the open of D+1, never the close of D (that would use a decision already known). Short from that open to the close at +1, +2 and +5 sessions.
- Returns: -(stock) minus IWM over the identical window, 1% round trip; double cost reported. Control = IWM in the same window (no free point-in-time small-cap peer set).
- Splits: train 2019-2022, validation 2023-2024, test 2025 to 2026-10. `core.screens.judge` with trimmed pick on train and the data gate; no Bonferroni (one event definition, not a group family).
- Pass: validation net > 0 with block p (cluster = UTC day) < 0.05, no losing result without the best 1 or 5 events, test sign not negative, and at least 3 events a week (below that it cannot matter for the monthly target even if real).
- Kill: validation mean <= 0 or p > 0.2.
- Known limits to state in the result: survivorship (today's ticker list), small caps may be unborrowable to short, and a red close is only known after the session.
- **Run 1 (2026-11-25, Actions 45463480460): killed at double cost; not a pass at base cost (inconclusive).** Data gate ok: 1,597 rows, no duplicates, train 541 / validation 411 / test 569 (76 rows outside every split), `gaps.bars` 0, 1,500 symbols priced from 7,081 listed, 495 symbols produced an event, 3.1 events a week. The trimmed pick on train is h5. Base cost: train +2.55% (p 0.001), validation +1.29% (p **0.0845**), test +4.23% (p 0.0005). Verdict: validation p misses the pre-registered 0.05 bar, so **no pass**, and `judge` reports "inconclusive" (not killed) at base cost. Double cost: validation +0.29% (p 0.37) and the result without the best 1 event is **-0.06%**, without the best 5 is -0.68% → **killed**. H1 and H2 are negative in validation (-0.59% and -0.33%), so the effect, if any, is only at the 5-session horizon and is concentrated in a few trades. Hit rate at h5: train 51.9%, validation 50.4%, test 58.3%.
- As pre-registered this is a **not passed / killed at higher cost** result and the line stops here. Two honest caveats for whoever picks it up: (a) the test split is the strongest (+4.2%, p 0.0005) while validation is flat, which is the opposite of what a real edge usually looks like across splits and is consistent with regime dependence rather than a stable rule; (b) survivorship (universe picked in 2026) can only inflate a short-side result if losing names were dropped, so the true number is likely worse, not better. A retest would need a point-in-time universe and a new dated protocol; do not relabel this one.

## L2 screen: short around large cliff token unlocks (pre-registered 2026-11-24, before any price data was pulled)
Spec `ops/lines/L2_unlocks.md`; data source found for #88: `https://defillama-datasets.llama.fi/emissionsIndex` (free; `api.llama.fi` needs a paid plan). Code `core.screens.unlock_events`, `unlock_short_returns`, study `l2_unlocks`.
- Events: cliff unlocks (`unlockEvents[].summary.totalTokensCliff`) from 2024-01-01 to 2026-10-20 whose size is >= 1% of the token's current circulating supply (current, not point-in-time: a known bias that overstates old unlocks' size relative to supply then).
- Price: daily closes, Binance spot (`data-api.binance.vision`) else KuCoin, BTC on the same venue. Windows: short from day -14 to +7 (the spec), -7 to 0, and 0 to +7 relative to the unlock day.
- Return: -(coin - BTC) minus 0.2% fees and assumed funding 0.09% a day (0.03% per 8 h paid by the short; real funding is not fetched). Double cost adds the same again.
- Splits 2024 / 2025 / 2026, trimmed pick, data gate and pass/kill as in L1c.
- **Run 1 (2026-11-24, Actions 45418370541): inconclusive (not a pass).** Data gate ok: 1,172 rows, 1,172 unique, train 272 / validation 451 / test 449, no warnings. 372 tokens, 1,532 cliff unlocks >= 1% of supply, 1,172 priced (Binance 835, KuCoin 337), about 34 a month. Trimmed pick post0_7: train +1.9% (p 0.043), validation +2.5% (p 0.0005), test -1.5% (p 0.91), so the test sign fails. Double cost kills it (validation +0.4%, test -3.6%).
- Observation (post hoc): pre7_0 (short the 7 days before the unlock) is positive in every split, train +0.4%, validation +2.7% (p 0.0015), test +1.5% (p 0.011), but it was not the pick and turns negative at double cost. A forward test would need a new dated protocol; the edge is small relative to costs and funding is assumed, not measured.
