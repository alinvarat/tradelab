#!/usr/bin/env bash
# Idempotent installer for an always-on Linux host (systemd user services). Usage: bash deploy/install.sh [--no-server]
# --no-server: install only collectors/watchdog/backups (use when the server already runs another way).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
UNITS="$HOME/.config/systemd/user"
mkdir -p "$UNITS"
names=(tradelab-news-archive tradelab-dvol-collect tradelab-watchdog tradelab-backup tradelab-state-backup)
[[ "${1:-}" == "--no-server" ]] || names+=(tradelab-server)
for src in "$REPO"/deploy/*.service "$REPO"/deploy/*.timer "$REPO"/research/ops/*.service "$REPO"/research/ops/*.timer \
           "$REPO"/research/news_archive/*.service "$REPO"/research/news_archive/*.timer \
           "$REPO"/research/threefold_plan/dvol_forward/systemd/*; do
  [ -f "$src" ] || continue
  base="$(basename "$src")"
  [[ "$base" == tradelab-server.service && "${1:-}" == "--no-server" ]] && continue
  sed -e "s#%h/Project/tradelab#$REPO#g" -e "s#%h/#$HOME/#g" "$src" > "$UNITS/$base"
done
systemctl --user daemon-reload
for n in "${names[@]}"; do
  if [ -f "$UNITS/$n.timer" ]; then systemctl --user enable --now "$n.timer"; else systemctl --user enable --now "$n.service"; fi
done
loginctl enable-linger "$USER" 2>/dev/null || echo "run once as admin: sudo loginctl enable-linger $USER"
systemctl --user list-units 'tradelab-*' --all --no-pager
