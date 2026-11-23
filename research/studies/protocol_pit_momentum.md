# 12-1 momentum on a point-in-time S&P 500: rules locked before any run

Locked 2026-11-24, before any point-in-time result exists. The momentum run on `core/universe.py` passed (`RESULTS.md`), but that universe was chosen in 2026, so the pass may be survivorship. This test exists only to check that one point.

**Universe.** S&P 500 membership intervals from the public file `sp500_ticker_start_end.csv` (github.com/fja05680/sp500, commit of 2026-09-07). At each formation month-end m, a stock counts only if its interval covers that day. Tickers with a "." use Yahoo's "-" form. A member with no Yahoo bars is a gap: it is counted and reported as coverage, not filled in.

**Rules (same as protocol_next (c)).** Each month-end, score = close at end of m−1 ÷ close at end of m−12 − 1. Hold the top decile, equal weight, from the next session's open to the last close of m+1. Control: equal weight of every member that has a score that month, same entry and exit. Both pay a 0.09% per-side round trip every month. A 2× cost run is reported. Splits: train ≤ 2022, validation 2023–24, test 2025+. Seed 20261124. Stats are blocks by calendar month.

**Pass.** The same five checks as `protocol_next.md` (block p < 0.05 on train+val; diff > 0 in train, in validation and in test; net > 0 at 2×; no month holds more than 25% of the summed diff). A month counts only if Yahoo coverage of members is ≥ 80%. The share of months that meet this is reported.

**Reported with it, not used for the verdict:** ending equity and worst drawdown at 1×, 2× and 3× leverage, with financing of 8%/yr on the borrowed part; the number of months ≥ 3× (expected to be zero); coverage per month.

**Known limits.** Stocks acquired and removed from Yahoo are missing (they usually leave on a takeover premium, so the basket is biased slightly down, against the control). Prices are split-adjusted and dividends are ignored. The S&P committee's own selection lags, so a new member entering after a rally is still counted only from its membership date.
