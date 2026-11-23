# TradeLab status (auto-generated 2026-11-23 14:19 UTC)

Simulated money only. Machine that ran the collectors wrote this file; gaps = that machine was off.

## Health
- Watchdog: OK (checked 2026-11-23T14:09:56.291977+00:00)

## DVOL forward test (locked protocol, 13 Mondays 2026-11-30 .. 2027-02-22)
| Monday | snapshots 09:00 / 09:05 | status |
|---|---|---|
| 2026-11-30 | 0/2 | upcoming |
| 2026-12-07 | 0/2 | upcoming |
| 2026-12-14 | 0/2 | upcoming |
| 2026-12-21 | 0/2 | upcoming |
| 2026-12-28 | 0/2 | upcoming |
| 2027-01-04 | 0/2 | upcoming |
| 2027-01-11 | 0/2 | upcoming |
| 2027-01-18 | 0/2 | upcoming |
| 2027-01-25 | 0/2 | upcoming |
| 2027-02-01 | 0/2 | upcoming |
| 2027-02-08 | 0/2 | upcoming |
| 2027-02-15 | 0/2 | upcoming |
| 2027-02-22 | 0/2 | upcoming |

Complete weeks: 0/13. Evaluate after 2027-02-26 with `python3 research/threefold_plan/dvol_forward/evaluate.py`; rules are locked (see `protocol.md`). Earlier checks say the expected result is poor (see the plan report).

## News archive (first-seen timestamps, 60 s polling)
- Days: 1, headlines: 242, first file 2026-11-23, last 2026-11-23

## Timers on the collector machine
```
NEXT                          LEFT LAST                          PASSED UNIT                        ACTIVATES
Mon 2026-11-23 21:19:56 +07    11s Mon 2026-11-23 21:09:56 +07 9min ago tradelab-watchdog.timer     tradelab-watchdog.service
Mon 2026-11-23 21:20:06 +07    22s Mon 2026-11-23 21:19:06 +07  37s ago tradelab-news-archive.timer tradelab-news-archive.service
Tue 2026-11-24 17:00:00 +07    19h -                                  - tradelab-backup.timer       tradelab-backup.service
Mon 2026-11-30 16:00:00 +07 6 days -                                  - tradelab-dvol-collect.timer tradelab-dvol-collect.service
-                                - -                                  - tradelab-state-backup.timer -

5 timers listed.
Pass --all to see loaded but inactive timers, too.
```
