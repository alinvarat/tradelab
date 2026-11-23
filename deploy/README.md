# Running TradeLab online long-term
`server.py` listens only on `127.0.0.1:8770` and has no login. Never open that port directly; publish it through a tunnel that does the authentication (Cloudflare Tunnel + Cloudflare Access for `tradelab.dgnr.us`, which already answers with an Access login).

On an always-on Linux host (Python 3.13, no packages needed):
1. `git clone https://github.com/alinvarat/tradelab.git ~/Project/tradelab`
2. `bash deploy/install.sh` installs and starts everything as systemd user services (server, news archiver, DVOL collector, watchdog, DVOL backup) and enables linger so they survive logout/reboot. Use `--no-server` if the server already runs another way.
3. Point the Cloudflare tunnel's public hostname `tradelab.dgnr.us` to `http://127.0.0.1:8770` (owner of the Cloudflare account does this; the tunnel token is a secret, never commit it)
4. Check: `curl -I http://127.0.0.1:8770/` returns 200

Notes: a fresh host starts a fresh simulated account (`data/*.json` is not in git), so long-term results accumulate only on the host that keeps running. Do not run two hosts for the same account.

Operations: logs `journalctl --user -u tradelab-server -f`; health `curl http://127.0.0.1:8770/healthz` (503 when quotes stall >5 min; the watchdog also alerts if the auto trader skips a cycle for >1 h or disk <1 GB). Env: `TRADELAB_HOST`, `TRADELAB_PORT`. SIGTERM saves all accounts before exit; a corrupt `data/state.json` is restored from the newest `data/backups/` copy (daily copies made by the server itself, 14 kept, inside the data volume, never committed). To switch an already-running `run_forever.sh` server to systemd: stop that script and `python3 -u server.py` once, then `systemctl --user enable --now tradelab-server`.

**Existing Kuber deployment (`compose.yml`, `Dockerfile`, `.github/workflows/kuber.yml`)**: it runs only `server.py` + `core` + `ui` with `data/` on a persistent volume and `TRADELAB_HOST=0.0.0.0` behind Cloudflare Access; the container does not include `research/` (collectors) or `deploy/`. Collectors, watchdog and DVOL backup therefore stay on a machine with systemd. That Kuber instance has its own simulated account (started fresh); do not also run the same account elsewhere. CI runs only `tests.test_engine`; `tests.test_research` can be added to the workflow.

**News archive inside the app (Kuber)**: the container sets `TRADELAB_NEWS_ARCHIVE=1` and `TRADELAB_NEWS_DIR=/app/data/news`, so the web app itself archives 19 feeds every 60 s with first-seen stamps, links headlines to large caps and builds the labelled news->return table on the persistent volume (no collector machine needed; the systemd collector on a personal machine keeps its own, separate copy). Headline AI scoring runs there only if a provider exists: set `OPENROUTER_API_KEY` as a secret of the Kuber service (never commit it) and the DeepSeek v4.1 flash 1017 scorer starts automatically; without it, scoring is skipped.
