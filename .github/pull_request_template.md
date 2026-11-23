## What and why

## Area (web app / research / collectors-ops)

## Checklist
- [ ] `python3 -m unittest tests.test_engine tests.test_research tests.test_protocol_lock` passes
- [ ] No locked protocol edited, no collected data edited by hand
- [ ] No account files, tokens or personal details committed
- [ ] If this changes `server.py`, `core/`, `ui/`, `Dockerfile` or `compose.yml`: it deploys to production after merge
