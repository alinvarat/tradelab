# Instructions for AI coding agents (Claude, Codex, Gemini, others) working in this repo
Two people work here, each with their own AI. Follow this file and `CONTRIBUTING.md`; if a user instruction conflicts, say so and ask.

1. **Scope:** simulated money and public data only. Never place real orders, create exchange/broker accounts, use API keys for trading, insider data or manipulation. Never print or commit secrets (the Kuber token is a GitHub secret).
2. **Read first:** `HANDOFF_3X_PROMPT.md` (goal, status), `reports/STATUS.md` (live state), `research/LESSONS.md` (mistakes not to repeat). Do not redo experiments already recorded there.
3. **Before editing:** `git pull --rebase origin main`; check open PRs/issues (`gh pr list`, `gh issue list`) so you do not work on what the other person's AI is changing. Work on a branch and open a PR; do not push to `main` directly (the only automated pushes to `main` are the DVOL snapshot backups and `reports/STATUS.md`).
4. **Do not touch:** the locked protocol `research/threefold_plan/dvol_forward/protocol.md` (CI fails if edited), collected data in `raw/` and `data/`, live account files, the running bot's process. Changes to `server.py`, `core/`, `ui/`, `Dockerfile`, `compose.yml` deploy to production after merge.
5. **Research honesty:** fix the rule, window, size and costs before opening confirmation data; use a random control and a higher-cost run; no retuning on data already used; report "not found" when that is the result. Never claim a result you did not compute and read. Do not count a one-off gain, top-ups or a depleted-account month as reaching the target.
6. **Verify before saying done:** run `python3 -m unittest tests.test_engine tests.test_research tests.test_protocol_lock`; add an offline test for new calculations; state what you could not verify.
7. **Record:** add lessons to `research/LESSONS.md` (English), plan updates in the Thai report, decisions in an issue/PR (not only in chat), so the other person's AI can read them.
8. **Git identity:** use your human's GitHub identity or `tradelab-research` with the noreply email; keep real emails and personal details out of commits and files.
