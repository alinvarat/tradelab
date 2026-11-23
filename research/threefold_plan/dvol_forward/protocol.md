# Forward test: BTC weekly strangle when Deribit DVOL is low

Locked 2026-11-23 (Monday, ~13:30 UTC), before any snapshot in the test window was taken. Do not change rules, window, sizing or costs after the first snapshot. Simulated money and public read-only data only; separate from the running TradeLab bot.

**Hypothesis.** When BTC implied volatility (Deribit DVOL) is low relative to its own recent history, short-dated options underprice the coming move, so a weekly OTM strangle has positive payoff skew. Not tested before in this project (previous option rules used price direction, VIX, CPI, weekends).

**Window.** Mondays 2026-11-30 through 2027-02-22 (13 entries). No extension if results are unclear.

**Data (collector.py, systemd user timer).** Each Monday at 09:00 UTC and again at 09:05 UTC: DVOL hourly and daily history, BTC index price, BTC option instruments with strike within ±25% of index expiring the Friday 08:00 UTC of the same week, and their order books (depth 10). A snapshot whose receive time is outside 09:00:00–09:10:00 UTC is invalid; that week is cash for every arm. Settlement uses Deribit delivery price for that Friday (public/get_delivery_prices), fetched after expiry.

**Signal.** `dvol_now` = close of the latest completed DVOL hourly bar at the 09:00 snapshot. `threshold` = 30th percentile of the 90 daily DVOL closes ending before the entry day. Trade if `dvol_now <= threshold`.

**Position.** Call strike nearest index × 1.085, put strike nearest index × 0.915 (ties: further OTM), same-week Friday expiry. Each leg budget = 25% of wallet equity (both legs ≤ 50%). Buy the largest multiple of min_trade_amount whose cost fits, walking the visible asks; skip a leg if the minimum does not fit or depth is insufficient. Hold to expiry. Inverse payoff per unit: call max(0, S−K)/S BTC, put max(0, K−S)/S BTC, S = delivery price.

**Costs.** Base: asks as quoted, taker fee min(0.0003, 12.5% × price) BTC per unit, settlement fee min(0.00015, 12.5% × price), USD↔BTC conversion 0.25% each way, filled from the 09:00 snapshot. High: asks × 1.15, conversion 0.5% each way, filled from the 09:05 snapshot (delay).

**Wallet.** One continuous 147 USD (≈5,000 THB) wallet, no top-ups. Monthly multiple = month-end ÷ month-start equity; report months starting ≥147 USD separately from depleted ones.

**Controls (same costs, same snapshots).** (a) Unconditional: buy the strangle every valid week. (b) Random: 1,000 draws choosing the same number of valid weeks as the signal uniformly, seed 20261123. Count each week once.

**Report.** Ending equity, months ≥3×, funded months ≥3×, worst month, max drawdown at week closes, base vs high cost, share of random draws ≥ signal. Claim success only if at least one funded month reaches 3× at both costs AND ending equity beats both controls at both costs; even then it is one 13-week sample and needs a second locked window before any bot is considered.
