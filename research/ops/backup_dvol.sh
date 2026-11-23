#!/usr/bin/env bash
# Push newly collected DVOL snapshots to the private GitHub repo (only that folder is committed).
set -euo pipefail
cd "$(dirname "$0")/../.."
P=research/threefold_plan/dvol_forward/raw
git add "$P"
if ! git diff --cached --quiet -- "$P"; then
  git -c user.name="tradelab-research" -c user.email="tradelab-research@users.noreply.github.com" \
    commit -q -m "Backup DVOL forward-test snapshots" -- "$P"
  git pull -q --rebase --autostash origin main
  git push -q origin main
  echo "pushed"
else
  echo "nothing new"
fi
