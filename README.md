# TradeLab

Paper-trading simulator for global markets (US stocks and ETFs, world indices, forex, futures, crypto) with
analysis tools, news, backtests, an AI analyst, and an auto trader that reviews its own losing trades.
**Simulated money only. There is no broker or exchange connection anywhere in the code.**

## Run
- Start (auto-restart supervisor): `cd ~/Project/tradelab && (setsid nohup bash run_forever.sh >/dev/null 2>&1 &)`
- Open: http://127.0.0.1:8770
- Stop: kill the `bash run_forever.sh` process first, then `python3 -u server.py`.
- Tests: `python3 -m unittest tests.test_engine`
- Standard library only (Python 3.13). The chart library is vendored in `ui/vendor/` (Lightweight Charts 4.2.0, Apache-2.0).

## Views
| View | What it does |
|---|---|
| Auto trader | 5,000 THB (converted to USD) paper account; daily walk-forward rule selection, mistake review, learned filters, lessons log |
| Markets | Watchlist, indices, rates, FX, commodities, crypto, sector ETFs, crypto fear and greed, top headlines |
| Chart and analysis | Candles, SMA/EMA/Bollinger, RSI, MACD; 10-indicator rating, support/resistance, pivots, Fibonacci, performance, beta, drawdown; symbol news; AI analyst; order ticket |
| Portfolio | Equity, positions with editable stop/target, orders, allocation, trade history, account settings |
| News | CNBC, MarketWatch, Yahoo Finance, CoinDesk, Google News with headline sentiment |
| Screener | ~40 symbols scored and sortable |
| Backtest | 8 strategies, costs, stops, shorts, vs buy and hold |
| Calendar and alerts | FOMC/CPI/NFP dates (`data/events.csv`), price alerts |
| Risk tools | Position size calculator, Monte Carlo risk of ruin |

## Data sources and limits
- Yahoo Finance chart API (prices may be delayed about 15 minutes; no bid/ask, so a typical spread is simulated).
- Binance public REST for live crypto bid/ask (USDT treated as USD).
- Fundamentals are not shown: Yahoo `quoteSummary` returns 401 without a session crumb.
- Market orders on a closed market wait for the next open quote; stops do not fire while closed.
- Thai market symbols (`.BK`) are refused by design (owner request 2026-11-23).

## Auto trader: how it learns (`core/autotrader.py`)
Method chosen from the research in `research/METHODS.md`: monthly dual momentum over SPY, QQQ, EFA, EEM, TLT, IEF,
GLD, DBC, VNQ and BTC-USD. Each month it holds the top assets by recent return, only if they beat cash (SHY).
1. Daily: 24 settings (lookback 63/126/252 days x top 2/3 x SMA200 guard x inverse-volatility weights) run on
   adjusted daily prices since 2006 with 0.10% fee and 0.05% slippage. Ranked on train (start to 3 years ago) only.
2. Mistake review: losing holdings are attributed to assets and to the condition at entry (below the 200-day
   average, volatility spike). Live losing months are added. The matching fix is adopted only if it improves the
   train result; validation effects are logged either way.
3. Trades only if the chosen setting also made money in the 3 validation years. Long only, no leverage,
   pauses itself after a 30% drawdown. Market orders on closed markets wait for the open.
State: `data/auto.json`. Lessons, monthly results and every tested setting are visible in the UI.

## Honest expectations
Measured on 2026-11-23: the chosen setting made +21.1%/year in train (2006-2023) and +14.7%/year in validation
(2023-2026, max drawdown 21%) while SPY made +16.3%/year. On 2017-2026 it made about 28%/year but with -24% in 2018,
and much of that came from Bitcoin. Expect roughly 10-15% a year with losing years of 20-30%; past results do not
predict future returns. Run it on paper for at least 3 months before considering real money.
