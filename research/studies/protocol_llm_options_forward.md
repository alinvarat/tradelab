# DeepSeek earnings direction expressed with short-dated OTM options: forward test, locked 2026-11-24 before any data

**Why.** Linear leverage cannot reach 3× a month, because the worst day wipes out every leverage level that would reach it (`RESULTS.md`, `LESSONS.md`). The structure that can reach it is convex: each loss is capped at the premium paid, while a winner can pay many times its cost. Historical equity option prices are not free (buying them was declined), so this test **collects its own data going forward** from free delayed sources. Simulated money only; no orders.

**Schedule.** GitHub Actions, every weekday at 15:00 UTC, which is after the US open all year. State, snapshots and calls live on the branch `data/options-forward`.

**Events.** 8-K filings listing item 2.02 in the SEC "latest filings" feed, accepted after the previous run and before this run. Issuer has a ticker; the median dollar volume over the prior 20 sessions is ≥ 100M USD, which keeps option spreads usable.

**Direction.** The same model, prompt (`LLM_SYSTEM`) and parsing as the earnings studies. One call per filing. A skip is not traded.

**Contract (fixed).** From Yahoo's chain at the run (15-minute-delayed quotes), take the nearest expiry at least 7 calendar days away. Long → the call with the lowest strike ≥ spot × 1.05. Short → the put with the highest strike ≤ spot × 0.95. Entry pays the **ask**. If the contract has no ask, or ask ≤ 0, there is no trade, and that is recorded. Control: the opposite-side contract (put ≤ 0.95 / call ≥ 1.05) recorded at the same time. A random direction, `random.Random(f"dir:{symbol}:{accession}")`, decides which of the two the control holds.

**Exit.** At the run on the 5th trading session after entry (sessions counted from SPY daily bars), sell at the **bid**. Before that, if the expiry date has been reached, the value at expiry is max(0, intrinsic) from the underlying's last close. A missing or zero bid counts as 0. Fee: 0.65 USD per contract per side, on 1 contract (100 shares).

**Account simulation (reported).** 5,000 THB (147 USD) start. Each new trade stakes 20% of current equity, capped at cash. Equity is marked at exit prices. Also: months ending ≥ 3×, worst drawdown, and how many trades a 147-USD account could actually afford (premium × 100 + fees ≤ stake), plus the same simulation with fractional contracts.

**Verdict, once at ≥ 150 closed trades** (expected after the Jan–Feb 2027 season). "Edge" requires all three: (1) mean return per trade (exit bid ÷ entry ask − 1, after fees) > 0 with block-bootstrap p (symbol-month) < 0.05; (2) mean of model minus random-direction control > 0 with block p < 0.05; (3) the result is still > 0 when every exit bid is cut by a further 10%. Otherwise "no edge shown". Thresholds never move.

**Known limits.** Quotes are delayed about 15 minutes and are not a fill. At 15:00 UTC the opening gap after an after-close filing is already in the price, which is conservative. Yahoo can change or block its endpoint, and gaps are recorded, not filled. Early-assignment and exercise frictions are ignored for long options.

## Addendum 2026-11-24: implementation fixes before the first market-open run (external review by Codex gpt-6.2-sol)
No threshold or rule changes. Corrections so the code matches the rules above:
- Form, items and acceptance time come from the issuer's SEC submissions record, not the feed. The window is (previous run, this run], and no earlier than 2026-11-24 00:00 UTC.
- The option chain is snapshotted before the model call, and its fetch time is the entry time. Both sides are kept (`both_sides`), plus the control draw.
- "At least 7 calendar days" is compared by date. Only a finite ask > 0 is a valid entry.
- The liquidity screen uses the true median of 20 completed sessions, ≥ 100M USD only.
- A failed exit quote is a gap retried at the next run, never a zero. Exits after the 5th session are flagged `late`. Expired contracts settle at intrinsic value from the underlying's close on the expiry date.
- The exit fee is always charged, even on a zero bid. Model statistics use every priced model exit; the paired statistic uses trades whose control is priced. The account replay processes exits before entries at the same time and reports months ≥ 3×, worst drawdown and one-contract affordability at the first 20% stake.

## Addendum 2026-11-24 (before the first market-open run): v2-single reader
Same reason as `protocol_llm_earnings_forward.md`. The model gets the v2 message: run-up over the 5 sessions to the last completed close, the move from that close to the option-chain spot at the run (what a trader can act on), the previous 2.02 release, and the current release. It uses `NEWS_V2_SYSTEM`, called once at temperature 0. Contract choice, exits and the verdict are unchanged.

## Addendum 2026-11-24: daily sequential evidence
Use [daily-v1](../sequential_protocol_20261124.md) for entries from November 25, 2026 UTC onward. Group each completed record by the UTC day of bookkeeping (`closed_ts`), including records priced after their planned exit. The first market-open run on November 24 stays in the fixed-sample study.

[The separately tagged all-8-K protocol](protocol_llm_options_forward_v2_sec_20261124.md) covers the prospective window from November 25 onward, beginning on its first scheduled run.
