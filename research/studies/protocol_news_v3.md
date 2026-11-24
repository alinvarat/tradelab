# News reader v3: market-relative reading with a unanimity and size rule. Locked 2026-11-24 before any v3 call

**Why (from v2 on 2026-11-06..11-22, now the training set; SPY-adjusted by hand, descriptive):**
- v2 returns were raw; that window had a sharp market fall (SPY 754 to 690), so the reader's short results were partly the market. After subtracting SPY over the same window the pattern stayed: H5 longs -2.0% (44% hit), shorts +5.6% (69%), unanimous 3/3 +1.9% (57%), split 2/1 -2.3% (43%). v2's confidence number was not calibrated (confidence >= 70 was worse).
- So v3 (a) judges and is judged relative to the market, (b) is told that release tone is not information and a short is a normal answer (the long lean), (c) trades only when all three samples agree and their median expected abnormal 5-session return is at least 2% in the same direction.

**Events (held out).** Every 8-K with item 2.02 accepted 2026-10-20 to 2026-11-05: after the model's release (2026-10-17, no training leak) and never read by v2 (protocol_news_v2 excluded these dates). Only v1 outputs on these dates were seen before (descriptive diagnostic in protocol_news_v2.md). Same universe, liquidity screen, tier costs and entry as v2.

**Inputs.** v2's inputs (previous release up to 6,000 characters, current release up to 12,000, run-up, gap) plus SPY's 5-session run-up and gap over the same windows and the abnormal (stock minus SPY) values. Prompt `NEWS_V3_SYSTEM`, message `v3_message`, decision `vote_v3` in `core/studies.py`. Model DeepSeek v4.1 flash 1017, 3 samples at temperature 0.7.

**Returns.** Every return is stock minus SPY over the identical window (entry open to the horizon close), then the tier cost.

**Verdict (H5 primary).** "v3 edge" requires: at least 60 trades; mean net per trade > 0 with block p (symbol-month) < 0.05; hit rate >= 55%; net > 0 at 2x cost. Also reported: v3 minus v1 paired per filing (skip = 0, SPY-adjusted), the plain-majority variant of v3 (to measure the unanimity rule), and H1/H3. If v3 passes it goes to the weekly forward runner (replacing v2) and into the bot's news analyst; if not, the failure is recorded and the next version is designed only from training data.

**Cost.** About 3 calls per tradeable filing; real cost from OpenRouter `usage.cost` is in the summary and goes to `reports/COSTS.md`.

**Run note 2026-11-24 (rules unchanged):** the first run (Actions 45423419796) was cancelled without any output being read, because OpenRouter returned 402 Payment Required from 16:59 UTC (credit exhausted) and every later call would have come back empty and counted as a skip. The rerun uses the same model, DeepSeek v4.1 flash 1017, through the owner's alternative provider (ai.thirx.com, `THIRX_MODEL`).

**Run note 2026-11-25 (rules unchanged):** run 45481243341 (dispatched on the old `research/news-v3` branch) is void: that branch's workflow passed an empty provider key and model, so not one v3 call was made (v3 n = 0 at every horizon, cost 0.00 USD, OpenRouter 402). Its "no edge shown" is an artifact and must not be quoted. The v1 numbers it printed come from cached v1 outputs on these dates, which were already seen (descriptive only). Rerun 45495806547 is dispatched from `main`, where the workflow passes the owner's DeepSeek provider (`DEEPSEEK_API_KEY` secret, `LLM_MODEL` variable `deepseek-flash`, base URL `https://api.deepseek.com`); the summary must record the model id the provider reports, and if it is not DeepSeek v4.1 flash 1017 the result is reported as a different-model run, not as this protocol's verdict.

