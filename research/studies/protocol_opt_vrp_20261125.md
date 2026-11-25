# opt_vrp_daily: Deribit daily-expiry defined-risk premium selling. Locked 2026-11-25, before any Deribit or Binance request of this study

SHA-256 of this file is in `protocol_opt_vrp_20261125.sha256` and checked by `tests/test_opt_vrp.py`. Do not edit rules, thresholds, windows or criteria. A change needs a new dated protocol before the first affected data. Simulated money and public data only.

## 1. Question and why it is not a repeat

Can selling a defined-risk option spread (or iron condor) that expires about 24 h later (12 h for R8) on Deribit BTC and ETH, sized so that the maximum loss is 20% of equity, grow a 147 USD account 3x in a calendar month after costs and beat a matched random control? The constraint from LESSONS is many independent trades with an edge; a daily structure can give up to 7 trades a week per asset. None of the closed studies sold premium with defined risk on daily expiries. The running DVOL forward test BUYS a weekly strangle on Mondays. Priors: LESSONS (hindsight ceiling of the weekly strangle buy was 2 of 22 months, and the low-DVOL buy lost 0.77x a week vs 0.86x for other weeks) is mild support for the opposite side but is not evidence for selling. Literature (for context, not as proof): BTC variance risk premium is positive (arXiv 2410.15195); illiquidity premium in delta-hedged Deribit returns (Atanasova, AUT); informal daily 0.35-delta strangle backtests (insights.deribit.com/?p=99807); counter-view that range-based realised vol cuts the premium to 3-5 vol points and 2024-26 is flat (bryanvine.github.io/alpha-research/paper1.html, not peer reviewed).

## 2. Data (all free, no key; fetched only on GitHub Actions, one shard per asset x calendar month)

- Trades: `history.deribit.com/api/v2/public/get_last_trades_by_currency_and_time` (currency BTC or ETH, kind option, sorting asc, count 1000, include_old true). Only entry windows are fetched: AM window [07:05, 09:05) UTC and PM window [19:05, 21:05) UTC of each day. Paged by moving the start to the last timestamp (inclusive), de-duplicated on `trade_id`; a page that adds no new id moves the start by 1 ms and is logged. A failed page after 4 tries makes that day a **gap** (never "no print").
- Instruments: `get_instruments?currency=...&kind=option&expired=true` (history host): strike grid, `expiration_timestamp`, `option_type`, `creation_timestamp`, `settlement_period`. A shard whose instrument fetch fails after retries fails loudly (no fallback grid from prints, which would select strikes by liquidity).
- Settlement: `www.deribit.com/api/v2/public/get_delivery_prices?index_name=btc_usd|eth_usd`, offset paging 100 per page (LESSONS: capped at 100). Payoff = max(0, +-(delivery - strike)).
- DVOL: `get_volatility_index_data` resolution 3600, 20-day windows with `continuation`. Starts 2021-03-24.
- Underlying: data.binance.vision spot 1h klines BTCUSDT and ETHUSDT (monthly zips, via `research/studies/binance_vision.py`): realised vol, 24 h return, intraday touch diagnostics (no priced exits).
- USDC cross-check (2025-01-01 onward only): the same windows fetched for currency USDC (BTC_USDC, ETH_USDC linear options).
- Sample: entry days 2021-03-24 to 2026-10-31, shard unit = asset x calendar month (136 shards). Time split: dev = 2021-03-24..2024-12-31 (sanity only, no tuning); confirm = 2025-01-01..2026-10-31. Both come out of one run; every judging criterion below applies to the confirm split only, and nothing is changed after the run.

## 3. Common mechanics (all rules)

- Information set at entry: only data stamped before the entry time. `DVOL_close(h)` = close of the hourly DVOL bar stamped h - 1 hour (safe whether Deribit stamps bar start or end). Binance bars count only if their open time <= h - 1 hour. h = 08:00 (AM) or 20:00 (PM).
- `sigma_d = DVOL_close / 100 / sqrt(365)` for every rule, including the 12 h R8.
- Index = `index_price` of the last print in [E-60 min, E) (E = 08:05 or 20:05); else the Binance 1h close of the bar opened at h - 1 hour. (Plan said 1m close; the 1h close at the hour start is used so that no 1m files are downloaded. Deviation stated.)
- Expiry = the instrument expiring at the next 08:00 UTC after entry (D+1 08:00 for both windows), with `creation_timestamp <= E`. Any `settlement_period` qualifies (day, week or month: Friday 08:00 expiries are labelled week, and excluding them would drop one day in seven for a reason unrelated to the structure). The label is stored; results are also split by it. If no instrument of that expiry was listed at E the day is a no-trade with reason `no_expiry`.
- Strikes (BS-free, from the listed grid at E, never from which strikes printed): short put = highest listed put strike <= index*(1 - k*sigma_d); short call = lowest listed call strike >= index*(1 + k*sigma_d); long wing = among listed strikes beyond the short strike, the one nearest to it whose distance is >= 0.5*sigma_d*index (one step minimum). No such strike = `no_wing`.
- Fills (first-print, pessimistic): short leg = price of the first SELL-direction print (taker hit the bid) on that instrument with timestamp in [E, E+60 min); long leg = first BUY-direction print. Both legs required (condor: all four), else the day is a no-trade with reason `no_short_print` or `no_long_print`. The position is entered at the later of the leg fill times; legs are priced at their own print's index_price. Coin price x index_price = USD.
- Costs. BASE: short price x 0.90, long price x 1.10; taker fee per unit per leg = min(0.0003, 0.125 x fill price after haircut) in coin (BTC for BTC, ETH for ETH); delivery fee on a leg that finishes in the money = min(0.00015, 0.125 x intrinsic in coin). HIGH: haircut 25% (x0.75 / x1.25) and both fees x2. A day whose net credit after entry fees is <= 0 is `no_credit`; one whose credit >= width is `credit_ge_width` (data artefact, excluded).
- Per-unit result: pnl = short USD - long USD - entry fees - intrinsic(short) + intrinsic(long) - delivery fees. Short gain = premium - intrinsic. Spread max loss = width - net credit. Condor: total credit of both sides, max loss = largest width - total credit (only one wing can finish in the money).
- Size model: 0.01 BTC or 0.1 ETH steps (linear USDC contracts); coin-margined BTC options (min 0.1 BTC) do not fit 147 USD. Prices come from the coin-margined tape, which has the same IV surface. qty = floor(0.20 x equity / max_loss per step); fewer than 1 step is `size_below_minimum`. The 40% total-open-risk cap never binds because each (rule, asset) wallet holds at most one structure and settles it (08:00 next day) before the next entry (08:05, or 20:05 for R8).
- Wallets: one independent 147 USD wallet per (rule, asset) test (16 tests), continuous over the split, no top-ups, entries use settled equity. Ruin: equity < 5 USD stops the wallet. A month is **funded** when the wallet's month-start equity >= 147; months are bucketed by entry date. Fresh-wallet monthly multiples (each calendar month restarted at 147) are reported as a diagnostic only.
- Margin (the treatment of a vertical spread under standard margin is UNVERIFIED: Deribit support pages returned 403). Two models, both reported. MARGIN-A: margin = max loss of the structure (netting assumed). MARGIN-B: no netting; each short leg = (max(0.15 - OTM fraction, 0.10) x index + short premium) per unit, each long leg paid in full. Under either, qty is cut until margin <= 80% of equity at entry; below 1 step = `margin`. Portfolio margin may need a minimum equity (third-party figure 0.25 BTC), so a 147 USD account is probably on B.
- Marking: account marked at entry and at expiry only (hold to expiry, no priced exits).

## 4. The eight rules (all Daily, BTC and ETH separately, hold to expiry, 20% of equity at max loss)

| Rule | Window | Structure | Filter (known at entry) |
|---|---|---|---|
| R1 bull_put_spread_vrp | AM | put spread k=1.0 | DVOL_close(08:00) / RV168h >= 1.15 |
| R2 bear_call_spread_vrp | AM | call spread k=1.0 | same as R1 |
| R3 iron_condor_vrp | AM | put + call spread k=1.0, both must fill | same as R1 |
| R4 high_dvol_condor | AM | condor k=1.3 | DVOL_close(08:00) >= 60th percentile (linear interpolation) of the previous 90 daily values of that same 08:00 DVOL close; at least 60 prior values; no RV filter |
| R5 post_shock_condor | AM | condor k=1.3 | abs 24 h Binance return ending 08:00 >= 2.5% (BTC) or 3.5% (ETH) |
| R6 weekend_condor | AM | condor k=1.0 | entry weekday Friday, Saturday or Sunday; no other filter |
| R7 rich_put_skew_spread | AM | put spread k=1.0 | skew >= trailing 30-day median of daily skew (previous 30 calendar days, at least 15 non-missing) |
| R8 evening_condor_12h | PM | condor k=1.0 | DVOL_close(20:00) / RV72h >= 1.15 |

- RV168h = annualised (x sqrt(24*365), x100) sample stdev of the last 168 Binance 1h log returns whose bars close by 08:00 (169 closes); RV72h likewise with 73 closes at 20:00. Any missing hour makes RV missing and the rule `no_rv`.
- R7 skew, measured on prints in [07:05, 08:05) on instruments expiring D+1 08:00 (the target expiry, listed since D-1): median IV of put prints with strike/index_price in [0.80, 0.95] minus median IV of call prints with strike/index_price in [1.05, 1.20], at least 3 prints each side. If the target expiry lacks them, use prints on the instruments expiring D 08:00 in [07:05, 08:00) (the prior still-listed daily). Still missing = `no_skew`.
- R6 calendar control: the same condor on Monday to Thursday entries.
- Keep the filters exactly as written. No threshold, k or window is tuned.

## 5. STEP 0: hindsight ceiling (computed from the rows before any rule is scored)

For each (rule, asset), at HIGH cost, using every day that passes the rule's filter and is fully fillable: (a) the all-win path: every executed trade earns its full net credit at 20% risk sizing, each calendar month restarted at 147 USD; (b) the oracle that also skips every losing day (actual outcomes). If the all-win path (a), the more generous one, reaches 3x in fewer than 50% of the calendar months of the whole sample, the test is stopped with the verdict `structure cannot reach target`: it is reported with its ceiling numbers and attrition only, and is not scored further (it still counts in the Bonferroni family). Quick arithmetic stated in advance: a spread risking 20% of equity earns about +2% of equity a trade at 8-15% credit/max loss, so 3x in a month needs about 56 compounding winning days with zero losses and one full loss costs 20%. The ceiling is expected to be borderline.

## 6. Controls and judge

- Primary statistic per trade: return on risk ROR = net pnl per unit / max loss per unit (independent of size, minimum steps and the wallet path).
- Control (i) unconditional: the same structure on every fillable day of the split (no filter). Control (ii) random: 1,000 draws (seed 20261125, `random.Random`), each choosing the same number of days uniformly without replacement from that fillable pool in the same split, same fills and costs; the statistic is mean ROR; report the share of draws >= the signal mean (`draw_share`). Computed at BASE and at HIGH cost. R6 also reports the Mon-Thu control mean ROR and the Fri-Sun minus Mon-Thu difference.
- Family: 8 rules x 2 assets = 16 tests, Bonferroni bar = 0.05 / 16 = 0.003125 on `draw_share`.
- A test is a **PASS** only if, on the confirm split, all hold: (1) step 0 passed; (2) at least one funded month with a 3x multiple in the continuous wallet at HIGH cost under MARGIN-B; (3) draw_share <= bar at BASE and at HIGH cost; (4) executed trades per week averaged over the split (days/7) >= 3; (5) mean net pnl per trade at HIGH cost > 0. A test meeting (1)-(5) under MARGIN-A but not B is **CONDITIONAL** (needs portfolio margin or a verified netting rule). Anything else fails. R6 can reach 3 a week only with zero attrition; this is accepted, not adjusted.
- Independent events: BTC and ETH on the same day are one episode; the summary reports episodes a week alongside trades a week.
- Reported per test, per cost, per margin: trades, trades a week, attrition by reason, win rate, mean net return per trade (on equity and on risk), worst loss, ending equity, max drawdown (realised equity), funded months and months >= 3x, vs both controls, BTC vs ETH, settlement-period split, USDC cross-check. A one-off gain, top-ups or a depleted account do not count as reaching a target.

## 7. USDC cross-check (report only, not a pass criterion)

2025-01-01 onward, same windows on currency USDC: for each side of each structure, whether both legs had a USDC print of the matching strike, expiry and direction (liquidity attrition table by month and rule). For legs with a first print on both tapes within 10 minutes, the ratio USDC USD price / coin-tape USD price (median) and the share of USDC fills better than the modelled BASE haircut. If the share of windows with both legs printing in USDC is below 50%, the tradable frequency is declared below 3 a week.

## 8. Known limits

- First-print fills assume a taker can trade the printed price at some size; real depth is unknown. The forward collector (daily 08:05 order-book snapshots, extension of `core/dvol_collect.py`) is the next step only if a test passes; it is not built here and the locked DVOL forward protocol is not touched.
- Legs may fill minutes apart and on different index prints. Margin treatment is unverified (two models). The sample has a flat or negative 2024-26 variance premium per the counter-view above, so a dev-positive / confirm-negative pattern is plausible and would be reported as is.
- ETH daily listing may start later than BTC; unlisted days are `no_expiry`. Expired-instrument metadata may omit some delisted strikes. Binance spot stands in for the Deribit index in the realised-vol and shock filters.
- Not verified offline: field shapes of the Deribit responses are taken from the data plan and handled defensively; any unexpected shape is counted as a gap and listed in the summary. Test fixtures are synthetic; no live data was pulled before this protocol was locked.
