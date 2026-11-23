# Working on TradeLab as a team
Simulated money and public data only. No real orders, no broker/exchange keys, no insider data.

**Start here:** read `HANDOFF_3X_PROMPT.md` (goal, status, rules), then `reports/แผนวิจัยเทรดเป้าหมาย 3 เท่าต่อเดือน.md`. Setup: Python 3.13, no packages. Run from the repo root: `python3 -m unittest tests.test_engine tests.test_research tests.test_protocol_lock`.

## Workflow
1. Branch from `main` (`git switch -c your-topic`); do not push research or experiments straight to `main`. Open a pull request; the other person reviews.
2. `main` deploys the web app (Kuber) **only** when `server.py`, `core/`, `ui/`, `Dockerfile`, `compose.yml` or `data/events.csv` change, and only after tests pass. Treat changes to those files as production changes.
3. One owner per area at a time (say who in the PR): web app (`server.py`, `core/`, `ui/`) · research (`research/`, `reports/`) · collectors and ops (`research/ops`, `research/news_archive`, `deploy/`).

## Research rules (they protect the evidence)
- `research/threefold_plan/dvol_forward/protocol.md` is locked. CI fails if it changes. New idea = new dated protocol file, locked before looking at its test data.
- Fix rules, window, sizing and costs before opening any confirmation data; use new, non-overlapping periods; compare with a random control under the same costs; report ending equity, months at 3x, worst month and drawdown, and results at higher cost. Do not retune on data already used. Report "not found" when that is the result.
- Never edit collected data in `raw/` or `data/` by hand; missing weeks stay missing (counted as cash).
- Add an offline test for any new calculation (`tests/test_research.py`).

## Do not commit
Live account files (`data/*.json`), `data/backups/`, `server.log`, the news archive (`research/news_archive/data/`), tokens or credentials (the Kuber token lives only in GitHub secrets), personal details.

## Two places run things
- Web app: Kuber container at the dgnr.us hostname (own simulated account, `data/` volume).
- Collectors/watchdog/backups: a machine with systemd (`bash deploy/install.sh --no-server`). Only one place should run each collector, or the data will be duplicated or gapped.
Commits go in as `tradelab-research` or your own GitHub identity; keep real emails private (use the noreply address).
