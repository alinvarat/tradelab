# DeepSeek forecasts Polymarket questions it cannot know: rules locked 2026-11-24 before any call or price look

**Why.** A binary contract is convex: a bet at price p returns 1/p − 1 when right and −100% of the stake when wrong, so the loss is capped at the stake. Polymarket's history is free. The model was released on 2026-10-17, so a question that opened on or after 2026-10-20 and has since resolved is out of sample for it. The earlier `research/polymarket.py` calibration study used no model.

**Markets.** From the Gamma API: closed binary markets (two outcomes, final prices exactly 0 and 1) whose `startDate` ≥ 2026-10-20 and `endDate` ≤ the run time, lasting at least 4 days, with volume ≥ 10,000 USD. Ordered by volume, at most 1,500 markets.

**Decision time.** t0 = endDate − 72 h, and it must fall at least 24 h after startDate. The YES price at t0 is the last price-history point at or before t0, and it must be at most 24 h old. The YES token is the first outcome.

**Model call.** One call per market, temperature 0. The model sees the date of t0, the question, the description (first 2,500 characters) and the end date. It does **not** see the market price. It answers JSON `{"p_yes": 0..1, "reason": "..."}`. An unparseable answer means no bet.

**Bet rule (fixed).** With q = p_yes and p = the YES price at t0: buy YES if q − p ≥ 0.10; buy NO if p − q ≥ 0.10; otherwise no bet. The entry price is the side's price + 0.01 (spread and slippage); a bet is skipped if the entry is ≥ 0.99 or ≤ 0.01. Return per 1 USD: 1/entry − 1 if the side won, else −1. Polymarket trading fees are taken as 0, and the slippage is the cost.

**Control.** The same markets and entry pricing, with the side chosen by `random.Random(f"pm:{market_id}")` (YES or NO). Paired diff = model return − control return.

**Verdict (≥ 100 bets).** "Edge" requires all four: (1) mean return > 0 with block-bootstrap p < 0.05, blocks = event; (2) mean return > 0 at +0.03 entry slippage; (3) paired diff > 0 with block p < 0.05; (4) the model's Brier score at t0 is below the market price's Brier score on the same markets. Otherwise "no edge shown"; fewer than 100 bets means "too few".

**Reported.** Bets, hit rate, mean return by price bucket and by category, and an account path from 147 USD that stakes 10% of equity on each bet in t0 order and settles at endDate. Months ≥ 3× and worst drawdown are reported, plus the same path at 20% stakes, for the 3×/month question only.

**Known limits.** Prices are history points, not an order book. Large stakes would move thin markets. Resolution disputes are taken as final as given. The model gets no web access, so it knows nothing after its release.
