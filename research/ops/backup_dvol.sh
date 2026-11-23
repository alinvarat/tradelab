#!/usr/bin/env bash
# Push newly collected DVOL snapshots to the private GitHub repo (only that folder is committed).
set -euo pipefail
cd "$(dirname "$0")/../.."
[ "$(git branch --show-current)" = main ] || { echo "not on main; skipping"; exit 0; }
P=research/threefold_plan/dvol_forward/raw
python3 research/ops/status_report.py >/dev/null
git add "$P" reports/STATUS.md
if ! git diff --cached --quiet -- "$P" reports/STATUS.md; then
  git -c user.name="tradelab-research" -c user.email="tradelab-research@users.noreply.github.com" \
    commit -q -m "Backup DVOL snapshots and refresh STATUS.md" -- "$P" reports/STATUS.md
  git pull -q --rebase --autostash origin main
  git push -q origin main
  echo "pushed"
else
  echo "nothing new"
fi
