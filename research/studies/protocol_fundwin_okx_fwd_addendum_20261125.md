# Addendum 1 to protocol_fundwin_okx_fwd_20261125: settlement grid, locked 2026-11-25, before the first forward settlement

The workflow probe (Actions run 45599324096, `fundwin_okx.yml` mode probe) showed that `public/funding-rate?instId=ANY` answers from a
runner (539 live USDT swaps, 541 tickers) and that OKX swaps do not all settle on the 00:00 / 08:00 / 16:00 UTC grid of the protocol:
323 swaps had `fundingTime` 1795622400 (a multiple of 8 hours), 214 swaps had `fundingTime` 1795608000 (four hours earlier, so they
settle on a 4-hour interval), and 2 had hourly settlements. The protocol text said instruments on other schedules are not traded, which
would drop 40% of the swaps, among them the ones with the most extreme rates.

Change, effective for every settlement after this commit (no forward data existed before it): the settlement grid is the **4-hour grid**
(00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC). At each grid time T the universe is every live `*-USDT-SWAP` whose published
`fundingTime` is T (all 8-hour swaps at 00/08/16 and the 4-hour swaps at every grid time). Hourly swaps are still not traded. Everything
else of the protocol is unchanged: the six cohorts, thresholds, entry and exit minutes, costs, control, units, e-process and verdict rule.
One unit of evidence is still one settlement of one cohort, now up to six units a day per cohort.
The keeper dispatches the ledger at 03:30, 07:30, 11:30, 15:30, 19:30 and 23:30 UTC.
