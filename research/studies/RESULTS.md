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

## (a) 8-K items and (b) Form 4: not run yet
Both jobs got HTTP 403 from SEC, because the `TRADELAB_SEC_UA` repo secret has not been set. Once the owner sets it, re-run with `gh workflow run research.yml -f study=items` (or `form4`).
