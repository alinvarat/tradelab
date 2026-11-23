# DeepSeek earnings reader, forward test with H5 primary: locked 2026-11-24, before any filing in its window

Why: the all-market run (Oct–Nov 2026 season) failed at H1. H3/H5 showed post-open drift (H5 net +0.60%, p 0.027), but that horizon was picked after seeing the data. This protocol tests it **only on filings that do not exist yet**.

**Window.** 8-K item 2.02 accepted on or after **2026-12-01**. The Oct–Nov 2026 season is closed and is not counted. Universe, liquidity screen and tier costs, model, prompt, parsing, entry and one-call-per-filing are as in `protocol_llm_earnings_wide.md`.

**Primary.** H5: enter at the first open after acceptance and exit at the close of the 5th session. Long or short as the model says; skips are not traded.

**Verdict, once at ≥ 600 non-skip H5 trades** (expected after the Jan–Feb 2027 season). "Edge" needs all four of these: (1) mean H5 net > 0 with block p (symbol-month) < 0.05; (2) H5 net > 0 at 2× cost; (3) H3 net > 0; (4) the paired diff against a random direction > 0 with block p < 0.05. Anything else is "no edge shown". Thresholds are not changed after data arrives.

**Reported at the evaluation, not used for the verdict.** A daily book on H5, holding five overlapping sleeves, each with 1/5 of equity, each day equal weight across that day's trades. Its leverage paths and its months at ≥ 3×.

**Running.** `.github/workflows/research.yml` runs weekly. The call cache and the results are pushed to the branch `data/llm-earnings` (not `main`), so every call is made exactly once.
