# Protocol: where can the L1f short be traded? (venues for the 42 coins with no Binance perp), locked 2026-11-25

Locked before any price of this study was read. Known before the lock (not independent of it): the L1f spot-priced rows (x about 1.98 on 105 rows) and the forced-flow
run (`protocol_forced_flow_20261125.md`), where the 65 of 107 notices whose coin has a Binance USDT-M perp gave mean +4.7%, s 0.31, x 0.19. The venue probe
(`l1f_venues.py probe`) stores bar COUNTS only, never prices; it is run first and the rules below do not depend on its outcome.

## Events and rule
- The 107 frozen L1f notices (`l1f` list of `data/forced-flow:events/latest.json`; one coin per notice, window 2024-01-01..2026-10-29). Rule unchanged from L1f: short at the
  open of the first 1-minute bar at or after notice + 60 s, buy back at the open 240 minutes later, 25% stop on a bar high (fill stop + 0.5%). One rule only (no grid), so Holm is over one rule.
- Stablecoins (USDP, IDRT, VAI) are reported but excluded from the judged set (a peg cannot carry the effect; fixed here, before pricing).
- Splits by notice time as the forced-flow protocol: train 2024-01-01..2025-07-01, validation ..2026-03-01, test ..2026-10-29.

## Shortable (point in time, no survivorship)
An instrument counts for an event only if its own 1-minute history (venue API or public archive, fetched after the fact but covering the event time) has a bar BEFORE the entry
(it existed at the notice), a bar at the entry and a bar at the exit 4 h later (it was still tradable). A coin that is listed today but has no bar at the notice is not shortable;
a perp that is delisted today but has bars then is shortable. A failed download is a gap and reported, never counted as "no instrument".
Venues in fixed priority (set before looking): binance_um, okx, bybit (public archive only, API blocked from Actions), bitget, gate, mexc, kucoin_fut, hyperliquid (API keeps the
newest 5000 one-minute candles, so only recent events can reach it; a reach limit, reported). An event is priced on the FIRST venue in this order that is shortable; every
venue is also reported alone on the events it covers (no choosing the best venue per outcome).
Margin routes (Binance cross/isolated, KuCoin margin) are NOT point-in-time verifiable: no public archive says whether a coin was borrowable at the notice (borrow endpoints need an
API key, which this repo never uses). They are reported as a separate, labelled upper bound (spot-priced on Binance spot 1-minute klines, borrow assumed available, fee 0.1% a side,
borrow 0.1% per 4 h) and never added to the reachable set or to the gate.

## Costs (same convention as the forced-flow study, so x is comparable)
Round trip 0.6% (fees 0.11% + slippage 0.2% a side) + funding/borrow 0.1% per 4 h, applied identically on every venue; stress at doubled cost. A second reported variant charges
slippage per side = max(0.2%, half the (high-low)/close of the fill bar) on the venue's own bars, to penalise thin books. Actual venue funding is not fetched (documented gap; 4 h funding on
these coins is typically below 0.1% in either direction).

## Controls and gate
Reversed-side placebo (-gross - cost + funding) and the forced-flow random control (5 of 24 liquid alt perps, same time, hold, stop, costs, Binance 5-minute bars). Stage 0 and the
validation/test criteria are the forced-flow protocol's (`core.sweep_stats.gate`, event-family counts train >= 20, val >= 12, test >= 10, notice-level x >= 0.2, control beaten),
applied to the reachable set. Sets reported: A = 65 Binance-perp notices; B = notices with no Binance perp but a perp on another venue; A+B = reachable; margin upper bound separately.
Output: n, mean, sd, s, N a month, x = N s^2, hit rate, per split, control, placebo, mean at 2x cost, coverage per venue. "Not found" is a valid result.

## Consequence
If B or A+B passes, a dated addendum `research/event_book/components_addendum_<date>.json` is proposed (separate PR); the locked event-book files are not edited.
