#!/usr/bin/env bash
# Push the P3 tape directory ($1) to branch data/poly-rewards without touching the checked-out tree (the collector is running
# from it). Called by poly_rewards.py every 30 minutes and at the end of a run. Needs contents: write.
set -u
TAPE="$1"
WT=/tmp/poly-push-wt
git config user.name tradelab-research
git config user.email tradelab-research@users.noreply.github.com
git worktree remove --force "$WT" 2>/dev/null; rm -rf "$WT"
git fetch -q origin data/poly-rewards 2>/dev/null
if git rev-parse --verify -q origin/data/poly-rewards >/dev/null; then
  git worktree add -q -B data/poly-rewards "$WT" origin/data/poly-rewards || exit 1
  cd "$WT" || exit 1
else
  git worktree add -q --detach "$WT" HEAD || exit 1
  cd "$WT" || exit 1
  git checkout -q --orphan data/poly-rewards && git rm -rqf . >/dev/null 2>&1
fi
mkdir -p snaps trades
cp -r "$TAPE"/snaps/. snaps/ 2>/dev/null
cp -r "$TAPE"/trades/. trades/ 2>/dev/null
for f in markets.json state.json summary.json resolved.json epoch.json runs.jsonl; do [ -f "$TAPE/$f" ] && cp "$TAPE/$f" . ; done
git add -A snaps trades *.json runs.jsonl 2>/dev/null
git commit -qm "poly-rewards tape: $(date -u +%FT%TZ)" || { echo "nothing new"; exit 0; }
for i in 1 2 3; do
  git push -q origin data/poly-rewards && { echo pushed; exit 0; }
  git fetch -q origin data/poly-rewards && git rebase -q origin/data/poly-rewards || git rebase --abort
done
echo "push failed"; exit 1
