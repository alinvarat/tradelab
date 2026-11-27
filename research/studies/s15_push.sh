#!/usr/bin/env bash
# Push the flat files of directory $1 to data branch $2 (data/s2-poll or data/s4-poll) without touching the checked-out tree.
# Called by s15_long.py every 30 minutes and at the end of a run. Needs contents: write.
set -u
DIR="$1"; BR="$2"
[ -n "$BR" ] || { echo "no branch"; exit 1; }
WT=/tmp/s15-push-wt
git config user.name tradelab-research
git config user.email tradelab-research@users.noreply.github.com
git worktree remove --force "$WT" 2>/dev/null; rm -rf "$WT"
git fetch -q origin "$BR" 2>/dev/null
if git rev-parse --verify -q "origin/$BR" >/dev/null; then
  git worktree add -q -B "$BR" "$WT" "origin/$BR" || exit 1
  cd "$WT" || exit 1
else
  git worktree add -q --detach "$WT" HEAD || exit 1
  cd "$WT" || exit 1
  git checkout -q --orphan "$BR" && git rm -rqf . >/dev/null 2>&1
fi
for f in "$DIR"/*.jsonl "$DIR"/*.json; do [ -f "$f" ] && cp "$f" . ; done
git add -A . >/dev/null 2>&1
git commit -qm "s15 poll: $(date -u +%FT%TZ)" || { echo "nothing new"; exit 0; }
for i in 1 2 3; do
  git push -q origin "$BR" && { echo pushed; exit 0; }
  git fetch -q origin "$BR" && git rebase -q "origin/$BR" || git rebase --abort
done
echo "push failed"; exit 1
