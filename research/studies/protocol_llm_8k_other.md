# DeepSeek reads every non-earnings 8-K: rules locked 2026-11-24, before any call or any look at these filings

Why: the leverage maths shows that the way to 3× a month is many independent trades per day. Earnings releases only come in four seasons a year. Other 8-Ks (agreements, officer changes, guidance under Reg FD, M&A, offerings, delistings and so on) arrive every day.

**Window.** Accepted 2026-10-20 or later, after the model's release date (2026-10-17), through the run date. Nobody on this project has looked at returns after these filings. Only the 2.02 filings were studied before (`protocol_llm_earnings_wide.md`).

**Events.** Every 8-K in the EDGAR daily indexes whose submissions record lists at least one item and **not** item 2.02, from issuers with a ticker. The liquidity screen and tier costs are the same as the wide earnings study (exclude < 5M USD/day or < 3 USD; per side 0.09/0.20/0.40%).

**Model input.** The ticker, the acceptance time, the item list, the first 6,000 characters of the 8-K text and the first 9,000 characters of its EX-99 exhibit, if there is one. The prompt is `LLM_SYSTEM_8K` in `core/studies.py`; it lets the model skip routine filings. One call per filing, saved in `llm_8k_other_calls.json`.

**Trade.** As in the earnings studies: the first open at or after acceptance, holding 1/3/5 sessions, long or short, skips not traded.

**Verdict (primary, same rule as the forward earnings test).** With ≥ 600 non-skip H5 trades, all of: H5 net > 0 with block p < 0.05; H5 net > 0 at 2× cost; H3 net > 0; H5 diff against a random direction > 0 with block p < 0.05 → "edge". Otherwise "no edge shown"; below 600 trades, "collecting". The H1 rule of the earlier studies is reported but is not the verdict.

**Reported.** Results by item code, the daily book (H1) and its leverage paths, and trades per day.
