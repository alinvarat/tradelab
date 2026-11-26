# Protocol: key-person events (8-K Item 5.02, CEO / founder / chair), pre-registered 2026-11-26

Owner idea (2026-11-26): a founder or CEO scandal or abrupt exit moves the stock down; a founder or former CEO returning moves it up.
Locked before any price of this study was pulled and before any filing was labelled. Code `core/keyperson.py`, `research/studies/keyperson.py`,
workflow `keyperson.yml`, prompt `research/studies/keyperson_prompt.txt` (sha256 `b1a78bdf5006c77cd03d51b308f57cd0869f446498242c09046fc021b3f77e48`; a test checks this hash against the file).

## What was known before the lock (so the reader can judge independence)
- RESULTS "8-K by item" (run 45269334155, 148 current stocks, long every filing, no text read): item 5.02 as a whole, H1/H3/H5 net -0.28% / -0.13% / -0.12%, paired diff against a random stock
  negative in validation and test. That study read no text and had no class, no side and no point-in-time universe. This one reads the 5.02 text, splits by class, trades a side and uses a point-in-time universe.
- N1 / news_v3 read earnings releases (item 2.02) with an LLM, not 5.02 filings; `llm_8k_other` read non-earnings 8-Ks with DeepSeek over one month. Neither labelled key-person changes. No 5.02 class count and no 5.02 price was seen by the author.
- Not independent of: the closed 8-K and form-4 families (same SEC feed, different universe and label). Not a repeat of them.

## Universe and events
- Point-in-time S&P 500 (fja05680 `sp500_ticker_start_end.csv`, `core.studies.parse_membership`), the only free point-in-time source in the repo; an S&P 1500 history is not available. Survivorship: delisted names are included in the membership list, but a name with no Yahoo bars (renamed, acquired) is dropped at the pricing stage and counted; this removes some firms that collapsed after an abrupt exit, so it biases AGAINST the short. A ticker needs a CIK in SEC `company_tickers.json`; one ticker per CIK (share classes).
- Event = an SEC filing of form 8-K (not 8-K/A) whose item list contains 5.02, accepted from 2017-01-01 to 2026-10-01 while the ticker is a member on the New York date of acceptance. Acceptance time read with `fu.accept_ts` (New York wall clock, locked convention). Entry: the open of the first session whose 09:30 ET open is strictly after acceptance (`fu.session_after`). The histogram of the stamp hour as read is reported.
- Text: the main document of the filing, HTML to text, the Item 5.02 section only (from the "Item 5.02" heading to the next other item or the signature, at most 6,000 characters). Exhibits (press releases) are not read.
- Deterministic pre-filter before any model call (decided now, no outcome seen): the section must match `chief executive|CEO|founder|co-founder|chair(man|woman|person)?|principal executive officer`. Filings without a section, or whose document cannot be fetched, are counted and dropped, never classed.
- Splits by acceptance time: train 2017-01-01..2020-01-01, validation 2020-01-01..2023-01-01, test 2023-01-01..2026-10-01 (36 / 36 / 45 months). Test ends 2026-10-01 so that a 20-session exit bar exists.
- One event per ticker per 30 days: the first event whose class is not "other" (applied after labelling, labels do not depend on prices).

## Classification (Haiku only, filing text only)
- Model `claude-haiku-5-5` through `core.ai_news.chat` (Claude Code CLI, Max plan, `CLAUDE_CODE_OAUTH_TOKEN`), temperature 0 (accepted by the call; the CLI path sets none), one retry on an empty reply; an unusable reply is a counted failure and the filing is excluded, never a class. No other model.
- Input: the redacted section. Issuer names (from the SEC submissions `name` and `formerNames`), the ticker and person names are replaced by `[COMPANY]` / `[PERSON]` (capitalised word runs without corporate title words, honorific + surname, and repeated given or family names). This is heuristic and imperfect; the model may still recognise a firm. Memory risk is also reported by a slice: events accepted on or after 2026-01-01 (assumed after the model's training data; the exact cutoff is not known), descriptive only.
- The model returns a role (ceo / founder / chair / none), an action (departure / appointment / both / none) and six flags (immediate, terminated, misconduct, planned, interim, returning), see the prompt. The class is DERIVED by this precedence, the order of the owner's list: abrupt (a departure with immediate, terminated or misconduct) > return (an appointment with returning) > planned (a departure with planned) > interim (the interim flag) > other. The count of filings with both abrupt and returning flags is reported. Role none, action none, or no rule above = other (not traded).
- Labels are frozen by accession with the prompt hash on branch `data/keyperson` (`events/labels.jsonl`, `events/latest.json`) after stage A, which uses no price. Nothing is relabelled after prices are read. A stage A rerun reuses labels with the same prompt hash.
- Spend: tokens and the CLI's notional USD from `ai_news.spend()` are logged in `reports/COSTS.md` (the Max plan has no per-call bill; paid USD 0).

## Stage A kill rule (counts only, before prices)
The step-0 arithmetic: stage 0 needs x = N a month x s^2 >= 0.2 (s = net mean / sd per trade) and n_train >= 20. With about 1 abrupt event a month in the S&P 500, x >= 0.2 needs s >= 0.45, i.e. a mean net of 45% of one standard deviation of a 1-20 day stock return; with a sd of 4-12% that is +2% to +5% a trade after costs. Founder or former-CEO returns are expected at well under 1 a month. If a judged class has fewer than 20 train events after dedupe, its rules fail the data gate and are reported as "too rare", not as a result against the idea; they are still priced and shown descriptively in stage B.

## Trade (daily bars from Yahoo, split-adjusted OHLC, dividends added by ex-date)
- Entry at the entry open, exit at the open `hold` sessions later; holds 1, 5, 20. Weight 1, one risk unit per event (k = 1 in the gate arithmetic; overlap is ignored). A missing bar drops the event and is counted by class.
- Judged directions (the owner's): `abrupt` short, `return` long. Every other class and side (planned, interim, both sides of all four classes) is DESCRIPTIVE only, never in Holm.
- Two bases, both reported and both judged as separate rules: `raw` (the stock alone, what a 147 USD account can actually hold) and `adj` (stock minus SPY over the same open-to-open window, dividends of both legs included). Rules: 2 classes x 3 holds x 2 bases = 12.
- Costs (round trip, labelled assumptions; `core/broker_costs.py` has no stock row). Long: 0.10% (fractional shares of liquid S&P 500 names, zero commission, 0.05% a side spread/slippage at the open, the value used by the locked factory_us_pit rules). Short: a stock CFD (fractional shares cannot be shorted): spread 0.20% round trip on an event day, plus financing/borrow 5% a year charged per session held (0.0198% a session). `adj` adds a 0.04% round trip for the SPY leg. Stress: 2x cost (`mean_2x`), as the sweep.
- mfe / mae for the gate come from the daily highs and lows of the entry..exit-1 sessions (long: high above entry, low below; short mirrored). The 5% liquidation arithmetic of the sweep is applied to a 1x position, so it never triggers.

## Controls and placebo
- Random control: for each event, 5 random entry sessions of the SAME ticker inside the SAME split that have a bar and lie more than 21 sessions from any of the ticker's own 5.02 filings (any class), seed `20261126:<ticker>:<acceptance ts>`; the same side, hold, basis and costs; the control of a trade is the mean of its draws (needs 3 valid).
- Reversed-side placebo: the gate's (the same trades with side reversed and the funding sign flipped), also reported by split.

## Stage 0 (train only, `core.sweep_stats.gate`, event-family counts as in the forced-flow protocol)
n_train >= 20; train net mean > 0 and above the reversed-side placebo; volatility/cost >= 10; x = N x s^2 >= 0.2; all-win ceiling >= 3x a month; plus train mean above the random-control mean. The sweep's own counts (30 / 30 / 20) are computed too (`sweep_strict_gate`, separate Holm) and a pass under the relaxed counts only is reported as such.

## After stage 0 (`core.sweep_stats.evaluate` + `judge_family`, Holm over the stage-0 survivors, alpha 0.05)
Validation and test net mean > 0 and > 0 at 2x cost; n_val >= 12, n_test >= 10; block-bootstrap Holm p < 0.05 on the validation daily series; at least 70% of the 6-month folds positive; the last 12 months positive at 2x cost; plus validation and test means above the random-control mean. A direction PASSES when one of its rules passes all of them. "Not found" is a valid result.

## Reporting
Per class, side, hold, basis and split (train / validation / test): n, mean, sd, s, events a month N, x = N s^2, hit rate, control mean, placebo mean; counts by class and split from stage A; the misconduct and post-2026-01-01 subsets; priced rows and drops by reason; the stamp-hour histogram. A passing direction is proposed as a dated addendum `research/event_book/components_addendum_<date>.json` in a separate PR (locked files are not edited) and confirmed forward by the e-process; no addendum otherwise.
One run per stage and one data or parser fix per stage (documented in the PR) before a second run; no rule, grid, threshold, prompt or class definition changes after a label or price is seen.
Not tested (stated so nothing is cherry-picked): small caps (no point-in-time list), CFO and other officers, director changes, 8-K/A, intraday entry before the next open, the S&P 400/600, event types other than 5.02.
