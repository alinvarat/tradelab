# Smarter paper bot: ensemble momentum + risk overlay (locked 2026-11-23, before any run)
Goal: better RISK-ADJUSTED results than the current auto trader (top 3 by 63-day return, equal weight, monthly) on the same universe, same costs (core.research.COST), simulated money only. It does NOT aim at 3x per month; no evidence supports that.
Universe: SPY QQQ EFA EEM TLT IEF GLD DBC VNQ BTC-USD, cash proxy SHY, daily adjusted closes from 2004, monthly rebalance at month end, weights earn from the next close (core.research.run).
Fixed variants (no other variants may be tried; no parameter tuning):
- V0 base: dual momentum, lookback 63, top 3 (current bot, no guard).
- V1 ensemble: for lookbacks 21/63/126/252 count votes where an asset's return beats SHY's; keep assets with >=3 votes; take the top 4 by mean lookback return; inverse-vol weights (63-day), weights sum to 1; empty -> cash.
- V2 = V1 + portfolio volatility target 12% (scale = min(1, 12% / trailing-63-day annualised vol of the held weights); the remainder is held in SHY).
- V3 = V2 + require price above its 200-day average.
Periods: train 2004-2018, validation 2019-2022 (used to choose), test 2023-2026-11 (opened ONCE after the choice is written to the results file). Choice rule: highest validation Sharpe among variants whose validation max drawdown is not worse than V0's; if none beats V0 on both validation Sharpe and drawdown, V0 stays and the result is "no improvement". The test period decides whether to run the winner as a forward paper "challenger" next to the live bot (never replacing it). Compare also with SPY buy-and-hold; report CAGR, vol, Sharpe, max drawdown, worst year, positive years.
Caveats written in advance: the universe was picked by earlier studies; BTC exists only after 2014; Yahoo adjusted closes; costs are a proxy; one market regime sample.
