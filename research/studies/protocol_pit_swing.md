# Swing timing on point-in-time S&P 500: buy the short-term pullback in an uptrend, sell the bounce. Locked 2026-11-24, before any run

**Idea.** Buy low and sell high with the market's rhythm. A member in a long uptrend that has just pulled back for a few days tends to bounce. Many members means several independent trades a day, which is what the 3×-a-month maths needs. This has not been run on a point-in-time universe before; RSI(2) was run on SPY alone (rejected, `METHODS.md`).

**Universe.** S&P 500 members on each day, from `sp500_ticker_start_end.csv` as in `protocol_pit_momentum.md`, using Yahoo daily bars over 10 years.

**Entry signal (at a session's close, using only that close and earlier).** The member is a member that day; its close is above its 200-session simple average; its 3-session return is ≤ −5%; and its close is below its 5-session simple average. Rank the candidates by 3-session return, most negative first.

**Book.** 10 slots, each holding 1/10 of equity at entry. Entry is at the **next session's open**; when signals outnumber free slots, the most-negative signals are filled first. **Exit** is at the next session's open after a close above the 5-session average, or at the open after the 10th session held. Cost is 0.09% per side, and a 2× cost run is reported.

**Control.** The same book and dates. On every day the strategy fills k slots, the control fills k slots with random members that are above their 200-session average and not already held (`random.Random(f"ctl:{date}")`). The control uses the same exit rule.

**Evaluation.** Monthly returns of both books, with paired diff = strategy − control. Splits: train ≤ 2022, validation 2023–24, test 2025+. Pass = the five checks of `protocol_next.md`, with month blocks; check (5) becomes "no month carries more than 25% of the summed diff".

**Reported.** Trades, trades per day, hit rate, average hold, CAGR, worst drawdown, and months ≥ 3× at 1, 2 and 3× leverage (8%/yr financing). SPY buy-and-hold is reported alongside.

**Known limits.** Acquired names missing from Yahoo; no borrow or short; opening gaps are taken at the open price; no intraday stops.
