# Working on TradeLab as a team
Simulated money and public data only.
- Read `HANDOFF_3X_PROMPT.md` first. Everything runs on Kuber (no personal machine); see `deploy/README.md`.
- Branch from `main`, open a PR, merge when CI is green. App changes deploy to production on merge. One area per person at a time (say which in the PR): web app (`server.py`, `core/`, `ui/`), research (`research/`, `reports/`), deployment (`Dockerfile`, `compose.yml`, `.github/`, `deploy/`).
- Protocols are locked before data arrives; no tuning on seen data (see `AGENTS.md`, rules 5-6).
- Tests: `python -m unittest discover -s tests -t .` (offline, run by CI).
- Do not commit data files or secrets. The owner does not want the project run on their computer.
