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
