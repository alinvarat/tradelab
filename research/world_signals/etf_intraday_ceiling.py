"""Calculate a hindsight ceiling for unlevered long-only ETF open-to-close rules."""
import gzip
import json
from collections import defaultdict
from math import prod

from .vix_fear import HERE, months_in


def main():
    output = {}
    for asset, source in (("GLD", "gold_fear"), ("USO", "oil_fear"), ("UVXY", "vix_fear")):
        raw = (HERE / f"{source}_inputs.json.gz").read_bytes()
        sessions = defaultdict(list)
        for row in json.loads(gzip.decompress(raw))["bars"]:
            if "2019-01-01" <= row["d"] <= "2026-10-31":
                sessions[row["d"][:7]].append(max(1, row["c"] / row["o"] * .9975 / 1.0025))
        bounds = {m: prod(sessions[m]) for m in months_in("2019-01-01", "2026-10-31")}
        output[asset] = {"months_at_3x": sum(x >= 3 for x in bounds.values()),
                         "peak_multiple": max(bounds.values()), "bounds": bounds}
    (HERE / "etf_intraday_ceiling_results.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
