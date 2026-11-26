"""Weekly review of the live bot (GitHub Actions only; workflow bot_weekly.yml, dispatched by keeper.yml on Sundays 04:00 UTC).
Reads the pod's published outcome rows (branch data/bot-desk) and the ingest log (branch data/news-ingest), recomputes the desk's
cells with shrinkage toward zero, scores each rule and each input, checks feed quality, and writes a report plus a proposal for
the next protocol tag. It changes nothing in the bot: behaviour changes ship as a reviewed PR with a tag bump (never auto-merged).

    python research/llm_trader/weekly.py <outcomes_root> <ingest_root> <out_dir> [YYYY-MM-DD]
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import desk_rules as dr   # noqa: E402
from core import desk_weekly as dw   # noqa: E402

WINDOW_DAYS = 7


def read_lines(root, pattern):
    out = []
    for f in sorted(Path(root).glob(pattern)):
        out += f.read_text(errors="replace").splitlines()
    return out


def run(outcomes_root, ingest_root, out_dir, today=None, now=None):
    now = now or time.time()
    today = today or time.strftime("%Y-%m-%d", time.gmtime(now))
    rows = [r for r in dw.load_rows(read_lines(outcomes_root, "desk_outcomes/*/*.jsonl")) if r.get("protocol") == dr.TAG]
    ing = []
    for line in read_lines(ingest_root, "news_ingest/*/*.jsonl"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("t_seen") and now - r["t_seen"] <= WINDOW_DAYS * 86400:
            ing.append(r)
    p = dw.propose(rows, ing, WINDOW_DAYS)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = today.replace("-", "")
    (out / f"{stamp}_proposal.json").write_text(json.dumps(p, indent=1, sort_keys=True))
    (out / f"{stamp}_review.md").write_text(dw.render_md(p, today))
    print(json.dumps({"window": p["window"], "changes": [c["id"] for c in p["changes"]], "note": p["note"]}, indent=1))
    return p


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    run(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
