# News-analyst training loop (Claude Haiku 5.5): protocol locked 2026-11-26, before any label, price or Haiku reply of this study

Owner goal (2026-11-26): "train the news analysis". Fine-tuning is not possible on the Max plan, so the levers are the prompt (versions), a rubric, and analog retrieval (similar past items with their outcomes). This file fixes the measurement; every number is in `params.json` (sha256 below). Simulated money, public data, no orders. Model `claude-haiku-5-5` through `core.ai_news.chat` only (AGENTS rule 7); the Max-plan USD paid is 0, tokens and the CLI's notional list price go to `reports/COSTS.md`.

**Supersession, stated on purpose.** `PLAN_20261126b_fable.md` section 4 item 6 says "no new reader" for LLM readers of filings and news as a trade trigger. The owner's 2026-11-26 goal supersedes that line for this lane only. It does not reopen N1, the earnings readers or the locked forwards: the DVOL forward, the news-latency forward collector (branch `data/news-latency-fwd`, hash-checked prompt) and the key-person study are not touched, not edited and not re-prompted. They are read-only inputs.

- params.json sha256: e171d307d8ccdaa3bc6f8736c163dfdbab4419d01bf2f521d1655199177af5ef
- versions.json (prompt registry): a version may be called only if it is registered there with the sha256 of its prompt file in a commit that precedes its first call; the code refuses an unregistered or edited version.

## Inventory (counts only, no outcome read; the build report restates it with live counts)
Timestamped news already in the repo and on the data branches:
- **N1 SEC filings** (`research/studies/news_v2.json`, `llm_8k_other.json`, `llm_earnings_wide.json`, `llm_earnings.json`, `items.json`; Actions run 45556256839 artifact `study-news_v3`): DeepSeek labels (n1 v1/v2) and Claude Haiku 5.5 v3 labels on 8-K filings from 2026-10-17 to 2026-11-23; `items.json` (43,349 rows, 148 stocks, 8-K since 2018) has accession, acceptance time and daily returns but no text. These outcomes were read by the N1 lane. They are **burned**: no filing accepted in [2026-10-17, 2026-11-24) is used in any set of this study, and no model of another family is pooled (AGENTS rule 7). We read only accession numbers and times from `items.json`, never its returns, and our universe comes from the SEC submissions API instead.
- **Notice tape** (`data/event-rows`, `tape/events.json`): 1,281 exchange notices (KuCoin 2024-01..2026-10, OKX 2025-06..2026-10), 439 priced on a perp.
- **Forced-flow** (`data/forced-flow`, `events/latest.json`) and **kr-listing** (`data/kr-listing`, `events/latest.json`): exchange-notice event lists (Binance, OKX, Bybit, Upbit, Bithumb titles).
- **News archiver** (Kuber volume, headlines and 1 h / 1 d labels, starts 2026-11-23): not reachable from Actions (Cloudflare); entirely inside the sealed era. Not used now.
- **news-latency-fwd** (`data/news-latency-fwd`): forward items with real `t_pub`, `t_seen` (first read: n = 8, median seen minus published 93 s, not meaningful). Items first seen on or after 2026-11-27 belong to the sealed set. They are not read by this study until the sealed run, and whether they are included is decided by a dated addendum written before that run (a reader for their bar format is not built now).
- GDELT / RSS archives: not added (GDELT DOC covers about 3 months only; nothing there is before the cutoff). Added only if the inventory shows the dev sets too small.

## Items and splits (by publication time `t_pub`, UTC)
- Stock items: SEC 8-K (not 8-K/A) of a point-in-time S&P 500 member (fja05680 membership list, as in the key-person study), with at least one item in `params.stock_items` (or none listed), 2018-01-01 onward. Crypto items: one per (notice, coin) from the three notice lists above whose coin has an OKX or Binance USDT-M perp with 1-minute bars.
- **train** 2018-01-01..2024-12-31, **validation** 2025-01-01..2026-06-30, **buffer** 2026-07-01..2026-07-31 (never used), **sealed** 2026-08-01 onward minus the burned window above.
- Dev sample: 1,200 stock items in train and 1,200 in validation, drawn by sha256 order (seed in params); all crypto items. Sealed: every eligible stock item 2026-08-01..2026-10-16 and every crypto item from 2026-08-01; sealed item text is built, sealed outcomes are **not** computed until the sealed run.
- **Seal enforcement in code:** the dev loader raises on any item or label with `t_pub >= 2026-07-01`; labels of sealed items are written only by `sealed` mode, which needs `LOCK.json` and refuses to run a second time (a `sealed/result.json` on `data/news-train` blocks it). A unit test checks both.

## Achievable-entry labels
- **Entry** is `t_pub + lag + 5 s` where `lag` = 93 s (the live collector's median seen-minus-published, a PROXY: real `t_seen` exists only in forward data; historical items cannot have it). Sensitivities: lag 60 s and 300 s, reported for crypto. Entry price is the close of the last 1-minute bar that ended at or before the entry time (no look-ahead; a bar more than 300 s stale is a missing label, never filled).
- **Holds:** 5 min, 1 h, 1 d (crypto: entry + 24 h; stock: close of the entry session). **Stock has only the 1 d hold historically** because free 1-minute stock bars do not reach back (probe: Yahoo returns minute bars only for about the last month); stock 5 min and 1 h are reported "unavailable", not estimated. A stock item whose entry time falls inside a regular session (09:30-16:00 ET, 6.5 h from the daily bar's open stamp) is dropped as `intraday_no_bars` (counted); a stock item filed outside the session enters at the next regular open, which is the first fill that exists.
- **Already-priced record:** crypto `pre_lag` (entry price over the price at `t_pub`) and `pre_1h` (entry over the price one hour before `t_pub`); stock `gap` (entry open over the previous close) and `runup5` (previous close over the close five sessions before). These are known at the moment of entry and are shown to the analyst (versions with `uses_pre`).
- **Costs (net P&L):** stock 0.09% a side (`core.news_backtest.cost_per_side("stock")`, a test pins the equality) plus 0.02% a session on shorts for borrow; crypto 0.40% round trip (the D1/P1 small-perp engine cost). The 2x case doubles both. `net = (1 + side * gross) * (1 - c)^2 - 1` per trade, minus borrow.

## Metric
- Per version, hold and market: **score = mean net P&L per OFFERED item, in percent, with abstain = 0.** A trade needs a non-`none` direction for that hold. The reply format is fixed (`direction` per hold plus a confidence number); an empty or unparseable reply is retried 3 times and then counted as a failure item, excluded from n and reported, never as "none".
- Baselines under the identical entry, hold and cost: **always abstain** (score 0); **random direction**, paired on the analyst's traded items and taken as the exact expectation (the mean of the long and the short net P&L of that item); **keyword rule** (no LLM; word lists in `params.json`, long on more positive than negative words, short on the reverse, otherwise abstain). Reported but not gating: always-long on the same traded items and always-long on all offered items (N1's lesson: a long lean can look like skill in a rising market), and the analyst's trade count and hit rate.
- Intervals and p-values: paired differences (analyst minus baseline, per offered item), **bootstrap over UTC days** (2,000 resamples, seed in params), one-sided p for "difference <= 0". Accuracy alone is never the score.
- Primary cell for any done claim: **stock, 1 d**. Crypto cells are reported separately and never pooled with stock.

## Leakage control
- Cutoff of Claude Haiku 5.5 is undocumented in our references; Opus 5.5 and Fable are June 2026, so we assume about mid-2026 and keep a July buffer. Everything before 2026-07-01 is dev only (train, validation).
- **Direct probe** (mode `leak`, before any version is trusted): for 12 random trading days a month from 2024-01 to 2026-11, ask Haiku whether the S&P 500 and BTC-USD closed a named day up or down, with "unknown" allowed and "do not guess", and compare with the Yahoo ground truth. Accuracy among answered and the answer rate by month show where memory ends. Only public index prices are used; no sealed item is used.
- **Redaction** in every prompt (analyst and analogs): issuer and person names, tickers and coin symbols become placeholders, explicit dates and years become `[DATE]` / `[YEAR]` (heuristic, as `core.keyperson.redact`; leaks by description remain possible and the probe above says how much memory exists). Validation gains are reported separately for items dated after the cutoff the probe finds.

## Training loop (train and validation only)
1. Run version v0 (plain headline reader, no rubric, no prices, no analogs) on train and validation: the floor.
2. Error analysis on **train** replies and outcomes: where the analyst is confidently wrong, which classes lose.
3. New versions change one lever at a time: v1 the rubric (surprise against expectation; who is forced to trade; the already-priced check with the pre-entry move; time horizon, i.e. which hold the news can last), v2 analog retrieval (k similar past items with their outcomes, from items **closed strictly before** the scored item's `t_pub`: the analog's longest-hold exit time must be earlier than the scored item's `t_pub`, one pool per run), later versions from the error analysis. Selection is on validation. Every version ever run on train or validation is a member of the family; `K` is capped at 8 versions (v0..v7).
4. A version's validation result is descriptive. Its P&L is never quoted as an expected return.
5. Calls are sharded over a GitHub Actions matrix from the start (N1 timed out at 4 h with 2 calls in flight); replies are cached by (item key, prompt sha) so a rerun costs nothing.

## Done condition (pre-registered)
A single locked prompt version `v*` (named in `LOCK.json` with its prompt sha256, written before the sealed run and never changed) on the **sealed** stock items at the 1 d hold satisfies ALL of:
1. at least **100 traded** items (non-abstain, valid reply);
2. mean net P&L per traded item greater than 0 (always-abstain is beaten), and
3. the paired difference against the random-direction baseline and against the keyword baseline are both positive with **Holm-adjusted** one-sided p < 0.05, where the Holm family has m = 3 x K hypotheses (three baselines for each of the K registered versions) and the hypotheses of versions not run on the sealed set count as p = 1 (so the sealed p of the locked version is multiplied by the Holm factor for 3K hypotheses);
4. net mean per traded item still above 0 at 2x cost (reported as a requirement, not a tuning knob).
If fewer than 100 traded items exist on the sealed set the verdict is "unread" and numbers are descriptive; the bar is not lowered. Sealed is opened once. A second sealed-set claim needs new sealed data (the forward items) and a dated addendum.

## What this study cannot show
Daily bars say nothing about the 5-minute and 1-hour holds for stock; crypto notices are few after 2026-07 (48 priced in the tape); the 93 s lag is a proxy; analyst replies on 2018-2025 items may partly be memory; costs are assumed, not fills; the burned N1 window is not available as a test. Any change to a threshold, split, cost or prompt-registration rule needs a dated addendum before the data it touches.
