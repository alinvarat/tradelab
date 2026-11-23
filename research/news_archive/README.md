# News archive (read-only)
`collector.py` runs every 60 s (systemd user timer, files `tradelab-news-archive.*`; copy to `~/.config/systemd/user/` and `systemctl --user enable --now tradelab-news-archive.timer`). It stores each new headline from the 6 RSS feeds and Bybit delisting announcements in `data/YYYY-MM-DD.jsonl` with `first_seen_utc` = when this machine first saw it. Backtests must use `first_seen_utc`, never the feed's `published_ts`. Archive starts 2026-11-23 13:53 UTC; gaps occur when the machine is off. `data/` is not committed (grows daily); each machine builds its own archive.

## Data-quality additions (2026-11-23)
- 19 live feeds (dead ones removed: Yahoo Finance rssindex returned 0 items; MarketWatch marketpulse and Investing.com were stale for over a year). Per-feed health in `data/feed_health.json`; the watchdog alerts when 3+ regular feeds are dead or older than 12 h.
- Each headline carries `symbols` (large caps it mentions, `core/entities.py`).
- `labels.jsonl`: for linked headlines the price at first sight and at +1h/+1d/+3d (open-market prices only; a horizon missed by more than 6 h is left unlabelled), with SPY-relative `abnormal` return. This table is the training/validation set for any future news signal; judge only on later data than it was built from.
