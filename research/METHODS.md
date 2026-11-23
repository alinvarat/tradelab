# Trading methods studied (2026-11-23)

Data: Yahoo adjusted daily closes since 2004 (dividends included). Cost 0.10% per unit of turnover.
Weights set at a close apply from the next day. Parameters chosen on 2006-2016 (train), reported on
2017-01 to 2026-11 (test, never used to choose). Scripts: `run_research.py`, `robust.py`; output `result_*.json`.

| Method | Source idea | Test CAGR (9 ETFs) | Test CAGR (+BTC) | Test max drawdown (+BTC) | Verdict |
|---|---|---|---|---|---|
| Buy and hold SPY | baseline | 13.8% | 13.8% | 33.7% | Hard to beat on raw return |
| 60/40 SPY/IEF | baseline | 9.0% | 9.0% | 21.0% | Lower risk, lower return |
| Equal weight, monthly | baseline | 9.0% | 15.1% | 27.5% | Diversification works |
| Trend SMA150 per asset | Faber 2007 | 6.7% | 11.6% | 10.4% | Best drawdown control |
| Dual momentum top 3, 63 days | Antonacci 2014 | 10.9% | 27.8% | 29.3% | Best return; adopted |
| Time-series momentum, vol target | Moskowitz, Ooi, Pedersen 2012 | 5.6% | 6.7% | 14.9% | Weak after costs here |
| RSI(2) mean reversion, SPY | Connors | 2.3% | 2.3% | 13.0% | Rejected |
| Turn of month, SPY | calendar effect | 3.6% | 3.6% | 13.6% | Rejected |

Robustness of dual momentum with BTC (`robust.py`):
- 2017-2021: 38 to 49% a year; 2022-2026: 11 to 15% a year (SPY 9.3%) for all four tested settings.
- At triple costs (0.30%): 24 to 27% a year over the test.
- Losing years: 2018 -21% to -34%, 2022 -3% to -17%. 2017 alone (+182% to +325%) came from Bitcoin's bubble.
- Bitcoin was held on 53% of test days; much of the edge depends on it.

Not studied with real money: intraday trading, leverage, options, shorting. Day trading small accounts
loses to costs in most published studies; leverage turns normal drawdowns into account wipe-outs.

What this means for 5,000 THB: if the next ten years look like the last ten, about 10 to 15% a year
(500 to 750 THB) is a reasonable hope, with some years losing 20 to 30%. There is no method in this
research that makes large, reliable profits from a small account.

## News-shock trading (owner's idea, 2026-11-23)
Historical headlines in bulk were not available (GDELT refused every request from this machine), so news days
were detected from the market's footprint: an open gap of 3% or more on at least 1.5x normal volume.
104 large US stocks, 2010-2026, about 6,500 events. Scripts: `events.py`, `evolve.py`, `baseline.py`,
`survivor_check.py`, `dipbuy_portfolio.py`.

- Selling or shorting after bad news: the next-day drift of -0.34% (2010-2018, t -3.2) vanished in 2019-2026 (+0.16%).
- Repeated search (the owner's "trade the past, adjust, repeat"): 264 rules over 40 generations. All top rules were
  "buy after a gap and hold 40 to 60 days". The best scored +7.0% per trade on 2010-2016, +14.8% on 2017-2020 and
  +6.8% on the locked 2021-2026 block, but buying the same stocks on any random day earned +3.6% there.
  The real edge is about +3% per 60-day trade, not +7%.
- Survivorship check on 47 stocks that shrank or struggled: the edge stayed positive (+1.6, +6.3, +3.3 points).
- As a portfolio (next-day open entry, 5 to 20 slots, 0.10% per side): 11.6 to 15.7% a year over 2010-2026 against
  SPY 13.4%, with deeper drawdowns (36 to 47% vs 34%). The 2021-2026 result swung from +6% to +24% a year
  depending on slot and hold settings.
- Verdict: news shocks create a small, real rebound tendency in large caps, but it did not reliably beat holding
  the index. Not added to the auto trader; available as a scanner on the Screener page.

Lesson on repeated backtesting: every extra trial raises the best in-sample score by chance. Here the search score
looked twice as good as the honest lockbox edge. Keep a locked period and compare with a random-entry baseline.

## Wider search: high-multiple routes (2026-11-23)
- 20x leverage on crypto, entered each month start, daily closes since 2014 (`leverage.py`): 6x reached in
  18-25% of months, account wiped in 54-66%; median outcome zero, before funding (~18% of capital a month at 20x).
- New Binance listings since 2019, 687 pairs incl. delisted (`listings.py`): bought at listing-day close, 0.9% touched
  6x within 30 days; median return -9.6% after 7 days, -19.3% after 30, -31.7% after 90; about 7 in 10 lost money.
  A strong first day predicted worse results (median 30d -32.8%).
- Polymarket calibration, 490 resolved binary markets (`polymarket.py`): bins of 20-60 prices; long-shot results
  flip sign between horizons (+84% at 7 days, -36% at 1 day for 5-10 cents). Too little data for any conclusion.
- Funding carry, spot long + perpetual short, Binance 2026 (`funding.py`): +2.7% to +5.6% a year before fees.
Not yet tested (data cost or effort): options, insider purchases (SEC Form 4), earnings drift with real dates,
social sentiment, on-chain data, memecoin launches (needs weeks of forward recording).

## Forex (2026-11-23, `forex.py`)
9 major pairs plus gold, daily since 2004, long and short, 0.02% per side.
- 8 classic rules, parameters fixed in advance: 6 of 8 lost money on average in 2017-2026 (-6% to -16% total over
  ten years). SMA 50/200 made +38.8% in 2004-2016 and then -6.3%. RSI mean reversion +6.2% total in the test but
  -12.6% in train: not reliable. Major pairs move about 40% over ten years, so unleveraged FX returns are small.
- Retail leverage from each month start: 1:100 reached 6x in 6.0% of trials and was wiped in 71.3%;
  1:500 reached 6x in 16.6% and was wiped in 83.4% (n=5,444, adverse moves checked first within a day).
Stocks were covered earlier (portfolio methods, news shocks, single-stock rules in the screener and auto trader).

## What people using AI to trade found (web research, 2026-11-23)
- Alpha Arena season 1 (Oct-Nov 2025, $10k each, crypto perps): 2 of 6 models profitable (Qwen3 Max about +22%,
  DeepSeek about +5%); four lost roughly a third to two thirds (figures differ between secondary sources).
  Season 1.5 (US stock perps): 5 of 32 accounts profitable. The organiser says one short run proves no model best.
- StockBench (arXiv 2510.02209): most LLM agents near flat (+0.3% to +2.2%).
- Live multi-market benchmark (arXiv 2510.11695): one +40.8% case, but the same setups lost on other assets;
  no LLM or agent consistently best.
- Traders Union survey of 1,020 retail traders: 58% use AI, 21% report measurable improvement, about 30% worse.
- Polymarket (Bloomberg analysis): regular users lost $131M; most profit went to the top 1% of automated bots.

## Hunter mode for the 6x target (2026-11-23, `hunter.py`, live `core/hunter.py`)
Leveraged crypto trend (BTC, ETH, SOL long above SMA50 with positive 30-day return), each month starting fresh,
intraday lows for liquidation, 0.05% fees, funding 0.03%/day on notional. Test 2023-2026 months:
5x: 6x 0%, 2x 11-19%, ruin 0-2%. 10x: 6x 0-4%, ruin 9-19%. 20x: 6x 9-11%, 2x 17-23%, ruin 43-51%.
Running as a separate 5,000 THB paper account at 20x with a 6x take-profit per month, beside the main auto trader.
Full survey of every other route: `reports/สำรวจวิธีเทรด ทุนเล็ก ทุกตลาด.md` (notes in `research_notes/`).
