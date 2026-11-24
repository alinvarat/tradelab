# News reader v2: more context and structured reading, tested against v1 on held-out filings. Locked 2026-11-24 before any v2 call

**Why.** v1 (`protocol_llm_earnings_wide.md`) read only the press release. It leaned long (80% of non-skips), its confidence was not calibrated, and it had no idea how the market had already reacted. A diagnostic on 2026-10-20..11-22 (seen data, descriptive only) found that v1 shorts worked at H1 (+0.72% net) and longs at H5 (+0.82%, 57% hit). v2 adds the context a human analyst would use.

**Events.** Every 8-K with item 2.02 accepted **2026-11-06 or later** through 2026-11-22. The universe, liquidity screen and tier costs are as in the wide study. Filings from 10-20 to 11-05 are not used, so v2 is never developed on its own test set. v2's prompt and rules below were fixed without looking at any v2 output.

**Inputs added in v2.**
- (a) Market reaction known at entry: gap = entry open ÷ the last close before acceptance − 1. Also the 5-session return before the filing (the run-up).
- (b) The issuer's previous 2.02 press release, if one exists within 200 days (first 6,000 characters), so this quarter can be compared with the last.
- (c) The current release, first 12,000 characters.

**Structured answer** (`NEWS_V2_SYSTEM` in `core/studies.py`): revenue/EPS versus the prior quarter, the guidance change (raised/maintained/lowered/none), a surprise score from −2 to 2, whether the reaction looks too small, fair or too large, then direction (long/short/skip) and confidence. **Three samples** at temperature 0.7; the majority direction wins. A tie or a majority of skips means skip. Confidence is the mean over the agreeing samples.

**Trade.** At the entry open, holding 1/3/5 sessions, with the same costs and splits as v1.

**Verdict (H5 primary, on the held-out filings).** "v2 better" requires all four: (1) mean per-filing paired diff (v2 signed net − v1 signed net, skip = 0) > 0 with block p (symbol-month) < 0.05; (2) v2 H5 mean net per trade > 0 with block p < 0.05; (3) v2 H5 hit rate ≥ 55%; (4) v2 H5 net > 0 at 2× cost. Otherwise "v2 not better". H1 and H3 are reported.

**Cost note.** About 1,000 filings × 3 calls. The real cost is logged from OpenRouter `usage.cost`.
