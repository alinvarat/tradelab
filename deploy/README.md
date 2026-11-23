# Running TradeLab online long-term

**Kuber CI secrets:** In the GitHub repository, add `KUBER_API_TOKEN` and
`OPENROUTER_API_KEY` under **Settings → Secrets and variables → Actions**.
Run **Test and deploy** on `main` (or push to `main`). The workflow writes the
OpenRouter key to a private temporary file outside the checkout; `.kuberrc.ts`
passes it to Kuber as the `app` service's `env_file`. Kuber injects it through
the `app-env` Kubernetes Secret, not the image. Use CI for hosted deployments
so they keep receiving this Secret. After rollout, sign in and check
`/api/llm_trader`: it should report trader status rather than `disabled`.

`server.py` listens only on `127.0.0.1:8770` and has no login. Never open that port directly; publish it through a tunnel that does the authentication (Cloudflare Tunnel + Cloudflare Access for `tradelab.dgnr.us`, which already answers with an Access login).

**Current setup (2026-11-24): Kuber only.** The owner switched off every personal machine; nothing is run locally. Deploy = merge to `main` (GitHub Actions runs the tests, then `kuber ci --trust`). `deploy/install.sh`, `deploy/tradelab-server.service`, `research/ops/*` and the systemd files in `research/news_archive/` are LEGACY for a personal Linux host and must not be enabled. If a deploy job fails with `KuberApiError`, re-run the failed job (it was a platform problem: full source storage and a 64 MB tunnel, both fixed by the platform owner).

**Existing Kuber deployment (`compose.yml`, `Dockerfile`, `.github/workflows/kuber.yml`)**: it runs only `server.py` + `core` + `ui` with `data/` on a persistent volume and `TRADELAB_HOST=0.0.0.0` behind Cloudflare Access; the container does not include `research/` (collectors) or `deploy/`. Collectors, watchdog and DVOL backup therefore stay on a machine with systemd. That Kuber instance has its own simulated account (started fresh); do not also run the same account elsewhere. CI runs only `tests.test_engine`; `tests.test_research` can be added to the workflow.

**News archive inside the app (Kuber)**: the container sets `TRADELAB_NEWS_ARCHIVE=1` and `TRADELAB_NEWS_DIR=/app/data/news`, so the web app itself archives 19 feeds every 60 s with first-seen stamps, links headlines to large caps and builds the labelled news->return table on the persistent volume (no collector machine needed; the systemd collector on a personal machine keeps its own, separate copy). Headline AI scoring runs there only if a provider exists: set `OPENROUTER_API_KEY` as a secret of the Kuber service (never commit it) and the DeepSeek v4.1 flash 1017 scorer starts automatically; without it, scoring is skipped.

**LLM trader (DeepSeek, paper)**: `core/llm_trader.py`, locked in `research/llm_trader/protocol.md`. It runs either as its own process (`research/llm_trader/tradelab-llm-trader.service`, needs the opencode CLI) or inside the web app when `TRADELAB_LLM_TRADER=1` (needs opencode or the `OPENROUTER_API_KEY` secret). Every call/decision/order is in the append-only `data/llm_trader_log.jsonl`; the Events tab shows decisions with the model's reasons. `/healthz` also reports the news archive and LLM trader status.

**Social buzz monitor (`core/buzz.py`, Buzz tab, `/api/buzz`)**: on by default (`TRADELAB_BUZZ=0` turns it off). Scans ApeWisdom mention counts for ~750 US tickers every 10 minutes, records surges on liquid stocks (any size above $50M) with a liquidity-matched control, and scores +1h/+1d/+3d vs SPY. Data in `/app/data/buzz`. Analysis only, no trades; rules in `research/buzz/protocol.md`.

**Running with no personal computer (2026-11-23)**: everything runs inside the Kuber app on the persistent volume: web app and bots, news archive (30 s), social buzz study (2 min), event trader (10 s scan, positions every 2 s for the LLM trader), the Monday 09:00/09:05 UTC DVOL snapshots (`core/dvol_collect.py`, files in `/app/data/dvol`, list at `/api/dvol`), and an advisory DeepSeek steward (`/api/steward`, every 6 h, cannot act). The LLM trader starts by itself when `OPENROUTER_API_KEY` is set (secret, owner only) or opencode exists. `/healthz` returns 503 with the stale component names if any loop stalls, so a platform probe can restart the pod; a supervisor thread restarts dead loop threads. Data speed: Yahoo US quotes were measured at ~1-6 s old, so polling (not the source) was the limit; `data.quote_fast` caches ~1.5 s.
