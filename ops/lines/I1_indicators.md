# I1 indicators_1: eight classic indicators on crypto perps, gold and FX

**Hypothesis (not a proven result):** a standard-parameter RSI, MACD, Bollinger, Stochastic, Supertrend, ADX, VWAP or Ichimoku rule, long and short with fixed exits, earns a net edge after real costs on some market and timeframe. Prior expectation: no (retail indicators are heavily mined), so this is a closed-form "not found" check across the cheapest remaining family, not a bet.

**Full pre-registration:** `research/studies/RESULTS.md`, section "indicators_1 screen". Code: `research/studies/indicators_1.py`, tests `tests/test_indicators_1.py`. Study names `indicators_1` (and `probe_indicators_1`, counts and dates only) in `research/studies/run.py`. Dispatch: `gh workflow run research.yml -f study=indicators_1`; no workflow file is edited.

**Differs from the closed factory_crypto_3:** that family was breakout, moving-average and wick rules on 1h/4h/1d majors. This one is oscillator and band rules plus Supertrend, ADX, VWAP and Ichimoku, adds 15m, gold and FX with XM Standard costs. MACD, Supertrend and Ichimoku are trend-followers like `ma_4h_20_100`, so cells are correlated; Bonferroni over the family is conservative for that.

**Data sources (deviation, stated):** crypto from `data.binance.vision` `futures/um` monthly 15m/1h klines and measured funding (the same source factory_crypto_3 used on Actions; the Binance REST API answers 451 there). OKX/Bybit were not used: the probe reports their status, but their 15m history and funding depth are not known to fill the splits. Gold and FX from Yahoo 1h.

**Reported limits:** US ETFs (SPY, QQQ, IWM) are out of the family by the step-0 gate, which rests on two assumptions not sourced in `research/brokers/costs.md`: leverage cap 5 and an 8 bp round trip. Gold uses `GC=F` futures as the price proxy for XM spot gold. Yahoo 15m depth (about 60 days) rules out gold and FX 15m.
