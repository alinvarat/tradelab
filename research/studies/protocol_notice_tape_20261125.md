# Protocol: exchange-notice tape screen (family 1), pre-registered 2026-11-25

Locked before any notice-tape price data was pulled (the L1 / L1f / L1g rows on Binance notices are already known and are
reported separately, not re-tested here). Plan: `research/plans/PLAN_20261125_fable.md`. Code: `core/notice_tape.py`,
`research/studies/event_tape.py`, study run by workflow `event_book.yml` mode `tape`. No LLM.

## Events
- Venues and sources (public, no key), fixed after an endpoint probe from a GitHub runner on 2026-11-25 (no price or
  notice rows of this screen had been pulled): OKX announcements API (all types), KuCoin announcements API (monthly time
  windows), Bitget announcements API (its API serves only the last 30 days, so Bitget adds almost nothing historic).
  Reported as gaps, not guessed: Bybit (announcements and prices answer 403 "country block" to GitHub runners), Coinbase (no
  public historic notice feed; the blog is behind Cloudflare), Bithumb (notice page 403), Upbit (403). Binance notices are
  out of this screen (already in L1/L1f/L1g rows). GeckoTerminal answered 200 but DEX-only coins stay out of this screen.
- Window 2024-01-01 to 2026-10-31 (as far back as each feed reaches; the reach per venue is reported).
- Five notice classes from the title (`core.notice_tape.classify_title`): listing, delist (spot), perp_delist, monitoring
  tag, funding-interval change. Titles about TradFi, stocks, ETFs, campaigns, earn, maintenance and similar are dropped.
- Tradeable: the coin has a live OKX USDT perpetual at notice time, i.e. `<COIN>-USDT-SWAP` 1-minute candles
  (history-candles) exist before the notice. The judged family uses OKX-priced events only. Events with no OKX candles
  are priced from Binance USDT-M 1-minute files (data.binance.vision, also with the `1000` prefix) and reported
  separately as descriptive (events, mean, s, x of their best cells), never judged and never counted in Holm. The BTC
  control is Binance USDT-M BTCUSDT 1-minute. Skips are counted by reason and class (OKX may not serve candles for
  delisted swaps; that blind spot is reported).
- A titles-only pass (class by venue counts, reach, a random 5% sample of unclassified titles; no prices) runs first and
  only fixes parser bugs (one fix, the family and grid do not change).
- One event = one (venue, class, notice time, coin). Duplicate (class, coin) pairs closer than 7 days are the same event. Futures launches ("New Listing: XUSDT Perpetual") are not a class here.

## Grid (the family)
- 8 types = (listing, long), (listing, short), (delist, long), (delist, short), (perp_delist, long), (perp_delist, short),
  (monitoring, short), (funding_interval, short).
- Holds 1h, 4h, 24h, 72h. Entry delay 1, 5, 15 minutes after the notice (close of that 1-minute bar). Stop 10% or 25% against
  the position, checked on 1-minute highs/lows, fill at the stop plus 0.5% slip. 8 x 4 x 3 x 2 = 192 cells; the family
  size for Holm is 192 whatever the number of events.
- Return of a cell = side * (exit / entry - 1) minus the same-window BTC USDT-M return times side (the control: market beta is
  removed), minus 0.7% round trip (fees 0.11%, slippage 0.2% per side, 0.1% funding/borrow). Stopped events book
  -(stop + 0.5%) minus cost and are not BTC-adjusted.

## Test and pass rule
- One-sided block-bootstrap p (cluster = UTC day, `core.news_backtest.block_bootstrap_p`, 2,000 draws; a cell at the
  floor p <= 0.004 is redone with 200,000 draws so that p can fall below the Holm bar 0.05/192 = 0.00026) for mean net > 0
  per cell over the whole window; Holm step-down over all 192 cells at 0.05.
- A cell PASSES only if: n >= 30 events; Holm-adjusted p < 0.05; mean > 0 in both halves (2024-01..2025-06 and
  2025-07..2026-10); mean > 0 after removing the best 3 events; x = events/month * s^2 >= 0.2 (s = mean / sd of the net
  return). Cells with n < 30 are reported "too few" and count in the Holm family.
- Per cell the run reports n, mean, sd, s, events/month, x, hit rate, halves, trimmed mean, adjusted p. All rows are kept
  as jsonl.gz on branch `data/event-rows` (`tape/rows.jsonl.gz`, per-event 1-minute paths included).
- Passing cells are NOT a result: they enter the forward event book only through a dated addendum before their first
  forward event, and are confirmed there by the e-process against random controls (`protocol_event_book_20261125.md`).
- One run and one fix per family: a data or parser fix is allowed once before a second run; no rule, grid or threshold
  changes after seeing results.
