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
