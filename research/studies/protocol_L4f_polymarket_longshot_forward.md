# Protocol L4f: sell Polymarket long shots the day before close (forward only)

Locked 2026-11-24, before any forward data. Origin: L4 screen run 3 (`RESULTS.md`) passed its locked rule (T-3d pick: validation +6.3% per event, test +4.3%, both p 0.0005; T-1d validation +6.3%, test +5.9%). The forward test uses the shortest lead (1 day), which had the highest return per day of locked capital in every split.

- **Markets:** open binary markets with volume >= $50k whose `endDate` is 12-36 hours away, polled every 30 minutes (Gamma `/markets/keyset`); addendum 2026-11-24 before the first entry: the poll runs on GitHub Actions (`l4f` job, state in branch `data/l4f-forward`) because Kuber gets a connection reset from the Polymarket API. One entry per market (the first poll where it qualifies).
- **Entry:** if the YES mid ((bestBid+bestAsk)/2) is in [0.02, 0.10], sell YES at its best bid; if 1 - YES mid is in that range, sell NO at its bid (1 - YES best ask). This pays the spread (taker), which is stricter than the screen's maker assumption.
- **Result:** at resolution (`closed` with outcome prices 0/1): +price per share if the sold side lost, -(1 - price) if it won; return on the locked collateral (1 - price per share). No fee (Polymarket charges none on most markets; any fee market is reported).
- **Sizing:** 5% of a separate 147 USD L4f ledger as collateral per market; no leverage.
- **Decision:** `core.sequential.EProcess(lo=1.0, hi=0.12)` on one value per UTC day of resolution (the mean of that day's results): a loss is at most -100% of collateral and a win at most +10.0/0.9 ≈ 11%. Edge at e-value 20; no edge when the negative side reaches 20. No change after the first entry without a new dated protocol.
- **Goal link:** at about +5% per event on collateral held about one day, the full ledger turned over daily would compound near the 3x-a-month pace; this test measures whether that holds after the spread and with real resolution risk.

**Correction 2026-11-24 (rules unchanged):** the "Origin" above cites L4 run 3, which was later found void (repeated API pages: 75 unique markets). L4f therefore rests on the prior evidence in `ops/lines/L4_polymarket_maker.md` only, not on a passed screen. Its rules were locked before its first entry and are not changed; the corrected screen (run 4) is reported separately.
