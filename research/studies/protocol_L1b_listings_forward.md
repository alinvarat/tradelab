# Protocol L1b: 4-hour hold after a listing notice (forward only)

Locked 2026-11-24, before any forward data. Origin: L1 screen run 2 (`RESULTS.md`), where the 4h horizon was positive in train, validation and test but was not the locked pick, so it is tested again only on new events.

- **Events:** new Binance "Will List" notices (catalog 48) and Upbit KRW-market "디지털 자산 추가" notices, parsed by `core.screens.binance_listing_symbols` / `upbit_listing_symbols`, first seen by the collector on Kuber (polled every 30 s); a notice published more than 15 minutes before it is first seen (collector start or restart) is not an event. Other venues may be added only by a dated addendum before their first event.
- **Tradeable:** the coin already has a USDT market on KuCoin (level-1 quote), else on Binance spot (book ticker), at the moment of entry.
- **Entry:** the ask 60 s after the notice is first seen (not the notice time, because the collector can only act on what it has seen). **Exit:** the bid 4 h after entry. Benchmark: BTC-USDT mid on the same venue over the same window.
- **Result per event:** coin return (ask to bid, so the spread is paid) minus the BTC return, minus 0.2% taker fees for the two legs.
- **Sizing for the paper ledger:** 20% of the ledger equity per event, no leverage; several open events share the equity.
- **Decision:** `core.sequential.EProcess(lo=1.0, hi=5.0)` on one value per UTC day (mean of that day's event results). Edge when the e-value reaches 20 (alpha 0.05); stop as no edge when the negative-side e-value reaches 20. Results are reported as they come; nothing is changed after the first event without a new dated protocol.
- **Goal link:** with about 1 event a month this line cannot reach 3x a month alone; it is kept only if the venue addenda raise the frequency.

## Addendum 2026-11-25: two more venues join the event stream (before their first event)

Reason: Binance gives about one "Will List" notice a month and Upbit answers 403 from Kuber, so the line cannot reach the frequency the goal needs. Two public announcement feeds that the Kuber collector reaches are added. Nothing else changes: the entry delay, exit, benchmark, costs, stake, freshness rule and sequential decision are exactly those above.

- **KuCoin spot listings.** `https://api.kucoin.com/api/v3/announcements?language=en_US&type=new-listings&pageSize=50`; only items whose `annType` contains `new-listings` are read, and `core.screens.kucoin_listing_symbols` keeps only spot "Listed/Will List" titles. Futures, copy-trading, tokenized-stock, pre-market, margin, convert/earn and delisting notices are excluded. Timestamp: `cTime` (announcement time, ms).
- **Bitget spot listings.** `https://api.bitget.com/api/v2/public/annoucements?language=en_US&annType=coin_listings`; only `annSubType == "spot"` items are read, and `core.screens.bitget_listing_symbols` excludes stock-perp, futures, copy-trading, margin and delisting titles. Timestamp: `cTime` (ms).
- **Known limits, recorded before data:** Bitget serves only the ten latest notices, so a Bitget notice that is pushed off the page within one 30 s poll is missed (undercount, never look-ahead). Both feeds also republish titles for markets that already traded; the unchanged tradeable rule (a KuCoin or Binance USDT market at entry) and the 15-minute freshness cut still apply.
- **Counting:** a symbol announced by two venues is two events only when both announcements are separate events; identical `venue:symbol:announcement-time` keys are dropped by `new_listing_events` as before.
