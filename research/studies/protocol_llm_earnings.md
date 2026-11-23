# DeepSeek reads earnings press releases: forward-only test, rules locked before any call

Locked 2026-11-24, before any model call or result. The model is `deepseek/deepseek-v4.1-flash-1017`, the only model allowed. It is called through OpenRouter on GitHub Actions; the key is a repo secret.

**No hindsight.** The model was released on 2026-10-17, so it cannot have seen any event after that day. Only 8-K filings accepted on or after **2026-10-20** are used. The model gets the press-release text and the ticker, and nothing else: no prices, and no news written after the filing.

**Events.** Every 8-K with item 2.02 from the 148 universe stocks accepted from 2026-10-20 through the run date. Input: the EX-99 exhibit (else the primary document), HTML stripped, first 15,000 characters.

**Model task (fixed prompt in `core/studies.py`, temperature 0).** Answer JSON `{"direction": "long"|"short"|"skip", "confidence": 0-100, "reason": "..."}` for the next 1–5 trading sessions. A reply that cannot be parsed counts as skip. One call per filing, no retries for a different answer.

**Trade.** Enter at the open of the first session at or after acceptance, exit at the close after 1, 3 and 5 sessions. A short gets the negative return. Cost is 0.09% per side; borrow cost is ignored (large caps).

**Controls.** (1) The same filing with a random direction, `random.Random(f"dir:{symbol}:{ts}")`. (2) Always long. Paired diff = model's signed net minus control (1)'s signed net, over the filings the model did not skip.

**Verdict.** With ≥ 60 non-skip trades, "edge candidate" requires all three: mean net > 0 at H1 and at H3; block-bootstrap p (symbol-month) < 0.05 for the paired diff at H1; and mean net > 0 at 2× cost at H1. Otherwise the verdict is "no edge shown", and with < 60 trades it is "too few, keep collecting". There are no splits, because every event is out of sample. Thresholds stay fixed when later earnings seasons are added.

**Reported.** n, skip rate, direction hit rate, gross/net per horizon, the paired diff, the always-long result, and the result restricted to confidence ≥ 70 (descriptive only).
