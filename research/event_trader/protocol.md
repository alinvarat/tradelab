# Event trader v2 (paper): follow up-shocks in large caps, tested forward against a random control
Locked 2026-11-23 before any event trade. Simulated money only (5,000 THB = USD at the live rate), no real orders.
Why: the owner asked why the bot did not react to the Nvidia headline (stock +33% in a day). The old bots never read news or trade single stocks. This system records every large single-stock move with its headlines and tests ONE rule forward. Earlier project research found no edge from buying after big news, so the expected result is "no edge"; the point is a clean answer on fresh data plus a labelled event dataset.

Universe: the 104 large caps in `core/universe.py`. Scan every 60 s (env TRADELAB_EVENT_EVERY).
Shock: market open, quote fresher than 30 min, |price / previous close - 1| >= 5%, and today's volume so far >= 0.5x its 50-day average. One event per stock per UTC day. Headlines (up to 3) attached at detection time.
Trade (up-shocks only, long-only): buy 5% of equity at the ask at first sight, 8% stop, exit after 20 hours at the bid when the market is open; max 3 open; no new entries after losing 3% in a UTC day or while paused; costs from the engine (0.05% fee + 0.02% slippage + simulated spread).
Control: at the same moment buy a random stock that is not shocked (|move| < 5%) with identical size, stop, exit and costs, in a separate account.
Recorded: all events (up and down) with price paths at +1h, +4h, +1d, +3d; closed pairs (net return of rule vs control).
Evaluation (locked): nothing may be concluded before 30 closed pairs. Then edge candidate only if mean rule return > 0, mean paired difference > 0 and bootstrap p(diff <= 0) < 0.10 (2000 resamples, seed 20261123). Even then it needs a second, non-overlapping locked window. Otherwise report "no edge shown". Down-shocks are data only.
No tuning of the numbers above on events already seen. Changes = a new dated protocol file.
Limits: Yahoo quotes may be delayed ~15 min and have no order book; fills are proxies; a small sample in a few months is noisy.

Addendum 2026-11-23 (logging only, rule unchanged): each event also records SPY move, abnormal move (stock move minus SPY move), VIX level, number of shocks so far that day, and each outcome also as a SPY-relative return. Reason: the first events came on a day the whole market jumped (Dow +1,300), so a raw 5% move can be market-wide rather than stock-specific. Analyses may split by this context but the locked trading rule and criterion stay as written.

Addendum 2026-11-24 (correction): the limit line above says Yahoo quotes may be delayed ~15 min. Measured on 2026-11-23, US quotes were 1-6 s old, so the polling interval (now 10 s scan, hot tier and positions faster) is the only delay. Rules and criterion are unchanged.
