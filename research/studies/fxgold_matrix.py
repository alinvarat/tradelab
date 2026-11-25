"""Matrix for the fxgold_tick workflow: python -m research.studies.fxgold_matrix MODE -> JSON {fetch, events, sims}.
Candle chunks are calendar quarters (one job each, cached by key); tick-release chunks are symbol-years. pilot = gold only, 2023Q4..2026Q4."""
import json
import sys
from datetime import date, timedelta

SYMS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"]
END = date(2026, 11, 19)


def quarters(y0, q0):
    out = []
    y, q = y0, q0
    while True:
        s = date(y, 3 * q - 2, 1)
        if s > END:
            break
        e = date(y + (q == 4), (3 * q) % 12 + 1, 1) - timedelta(days=1)
        out.append((f"{y}Q{q}", s.isoformat(), min(e, END).isoformat()))
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


def main(mode):
    pilot = mode.startswith("pilot")
    syms = ["XAUUSD"] if pilot else SYMS
    qs = quarters(2023, 4) if pilot else quarters(2018, 1)
    years = [2023, 2024, 2025, 2026] if pilot else list(range(2018, 2027))
    print(json.dumps({"fetch": [{"sym": s, "chunk": c, "start": a, "end": b} for s in syms for c, a, b in qs],
                      "events": [{"sym": s, "year": y} for s in syms for y in years], "sims": syms}))


if __name__ == "__main__":
    main(sys.argv[1])
