# DeepSeek earnings reader across every US 2.02 filer: rules locked before any new call

Locked 2026-11-24, after the 148-stock run (`protocol_llm_earnings.md`, verdict "edge candidate") and before any call on the wider set. Same model, prompt, parsing, trade rule and verdict thresholds. Only the universe and the costs change. The goal is more independent trades per day.

**Events.** Every 8-K accepted from 2026-10-20 through the run date that lists item 2.02 (EDGAR daily `form.idx`, then the issuer's submissions record for items and acceptance time), from any issuer with a ticker in the SEC ticker map and Yahoo daily bars.

**Liquidity and costs, fixed by tier.** Use the median dollar volume (close × volume) of the 20 sessions before entry. Excluded: median < 5M USD, or prior close < 3 USD. Cost per side: ≥ 100M USD 0.09%; 20–100M 0.20%; 5–20M 0.40%. Shorts carry no borrow charge, which is a stated limit.

**Calls.** The 106 filings already called are reused, never re-called. Every new filing gets exactly one call, and every call is saved in `llm_earnings_calls.json`.

**Verdict, on new filings only** (the 148-stock filings are already seen): the same rule as before. With ≥ 60 non-skip trades, H1 and H3 net > 0, H1 block p (symbol-month) < 0.05 for the paired diff against a random direction, and H1 net > 0 at 2× cost → "edge candidate". Otherwise "no edge shown".

**Reported, not used for the verdict.** The daily book: each entry day, equal weight across that day's non-skip H1 trades. Its mean, sd and the ending equity and worst drawdown at 1, 2, 3, 5, 8 and 10× leverage. Results by liquidity tier. The pooled result including the old 106.
