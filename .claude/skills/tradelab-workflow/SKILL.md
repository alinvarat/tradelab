---
name: tradelab-workflow
description: Use for any work in the TradeLab repo: a backtest screen, a forward ledger, a bot (llm_trader) upgrade, a workflow edit, a cost check or a status report. Enforces the data gate, red flags, protocol tags and definition of done from ops/RUNBOOK.md.
---

# TradeLab workflow

The procedure lives in `ops/RUNBOOK.md`; what runs where lives in `ops/SYSTEM_MAP.md`. This skill only makes sure the gates are not skipped.

## Before any change
1. `git switch main && git pull --rebase origin main`, then read `reports/STATUS.md` and `ROADMAP.md` section 1.4.
2. Never run the project locally (AGENTS.md rule 3). Verify through CI, GitHub Actions artifacts and the Kuber site through a browser.

## By type of work (do every step; RUNBOOK section 2.1 has the details)
- **Backtest screen:** pre-register pass/kill rules in `research/studies/RESULTS.md` before pulling data; pure functions with offline tests in `core/screens.py`; run with `gh workflow run "Research studies" -f study=<name> --ref <branch>` only; read `integrity` from `core.screens.judge` and stop if `ok` is false; check RUNBOOK 4.1 red flags (round row counts, p = 0.0005 everywhere, no losing events, results that do not change with parameters); report rows, unique rows and per-split counts.
- **Bot upgrade:** a failing test first; bump `PROTOCOL_VERSION` in `core/llm_trader.py` and add a dated addendum to `research/llm_trader/protocol.md`; after deploy open `/api/llm_trader` (and `/api/llm_log` for context fields) in the browser and confirm the new tag and the new fields in a real cycle.
- **Forward ledger:** lock the protocol before the first event; a test that walks one full entry and exit; after deploy confirm the ledger in the API or its data branch; add it to `ops/SYSTEM_MAP.md`.
- **Workflow file:** edit with enough context to be unique; `tests/test_workflows.py` must pass; after merge `gh workflow list --all` still shows "Research studies".

## Done means
CI green, deployed (when the app changed), checked on the live site or data branch, `reports/STATUS.md` updated. Otherwise report "merged but not live yet" or "not verified" plainly. A result found wrong later is marked "VOID, retracted" in RESULTS.md with the reason, never deleted, and the owner is told at once.
