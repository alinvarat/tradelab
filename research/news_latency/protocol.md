# News latency: can we still make money after WE first see a headline?

Locked 2026-11-24, before the first +1m/+5m label exists. Simulated money and public data only; no orders.

**Question.** The archive stamps `first_seen_utc` when this machine first sees a headline and records the price at that moment. If a trader could buy (or sell) immediately at that first-sight price, is there a residual move at +1 minute or +5 minutes that survives costs, compared with a random stock under the same market conditions?

This tests the owner's belief that "fast news plus good analysis" is enough. It measures speed relative to the market, not the quality of a model's explanation.

**Data.** Every linked headline (104 large caps plus the aliases in `core/entities.json`) is stored in `labels_open.json` at first sight with the stock price, SPY and a deterministic random control stock (chosen from the large-cap list, never one of the headline's linked symbols; seeded by the headline key + symbol). At +1m and +5m (grace: 2 min and 5 min) the archive writes `latency.jsonl` rows with the stock return, SPY return, abnormal return, control return and control abnormal return. A row is only written from a price inside its window; late or missing prices are left empty, never filled with a stale quote.

**Costs.** The event side pays a 0.14% round trip (0.05% fee + 0.02% slippage per side, the engine's assumptions) before comparison; the control is a benchmark, not a trade. Report gross and net.

**Evaluation.** Primary horizons +1m and +5m, separately. Nothing is concluded before **100 complete pairs** (event and control both priced) at that horizon. Then the mean net paired difference (event abnormal minus cost minus control abnormal) is bootstrapped (2,000 resamples, seed 20261123, 95% interval). "Edge candidate" only if mean net > 0 and the interval is above 0; otherwise "no edge shown". Even a positive result needs a later non-overlapping window before any trading rule uses it.

**Reporting.** Number of events, complete pairs, missing controls, mean event/control/diff, net mean, interval, share positive, and the result at +1m and +5m. Also report how many headlines had a price already moving at first sight (descriptive, from the archived move) if available; it does not change the test.

**Limits.** `first_seen_utc` is the collector's 30 s polling delay, not the exchange timestamp; Yahoo quotes can be 1–40 s old; a headline may already be old when a feed publishes it; controls are large caps, not matched by sector or volatility; overlapping headlines about one event are not independent. A positive 1m result can be noise or queue position, not a repeatable edge.
