# Running TradeLab online long-term
`server.py` listens only on `127.0.0.1:8770` and has no login. Never open that port directly; publish it through a tunnel that does the authentication (Cloudflare Tunnel + Cloudflare Access for `tradelab.dgnr.us`, which already answers with an Access login).

On an always-on Linux host (Python 3.13, no packages needed):
1. `git clone https://github.com/alinvarat/tradelab.git ~/Project/tradelab`
2. `cp deploy/*.service ~/.config/systemd/user/` (also `research/ops/*` and `research/news_archive/*` units if collectors should run there), `systemctl --user daemon-reload && systemctl --user enable --now tradelab-server.service`, and `loginctl enable-linger $USER`
3. Point the Cloudflare tunnel's public hostname `tradelab.dgnr.us` to `http://127.0.0.1:8770` (owner of the Cloudflare account does this; the tunnel token is a secret, never commit it)
4. Check: `curl -I http://127.0.0.1:8770/` returns 200

Notes: a fresh host starts a fresh simulated account (`data/*.json` is not in git), so long-term results accumulate only on the host that keeps running. Do not run two hosts for the same account.
