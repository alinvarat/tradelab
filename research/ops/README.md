**LEGACY (2026-11-24): these systemd timers and scripts were for a personal machine, which the owner switched off. Everything now runs inside the Kuber app (see deploy/README.md). Do not enable them.**

# Ops (collectors, health check, backup)
Timers (copy `*.service`/`*.timer` to `~/.config/systemd/user/`, then `systemctl --user enable --now <name>.timer`):
- `tradelab-news-archive` every 60 s — see `../news_archive/README.md`
- `tradelab-dvol-collect` Mondays 09:00/09:05 UTC — see `../threefold_plan/dvol_forward/`
- `tradelab-watchdog` every 10 min — writes `status.json`, desktop notification when news stalls >3 h, a timer is inactive, or a Monday test week has <2 snapshots
- `tradelab-backup` Mon/Tue 10:00 UTC — commits and pushes only `dvol_forward/raw/`
Tests: `python3 -m unittest tests.test_research tests.test_engine` (offline, synthetic data).
Limits: machine must be on; the watchdog runs on the same machine, so a power-off is noticed only after it comes back.
