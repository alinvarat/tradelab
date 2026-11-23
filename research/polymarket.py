"""Polymarket calibration study. For resolved binary markets with real volume: take the price of an outcome
N days before the market ended and compare with how often that outcome actually won.
If cheap outcomes (5-15 cents) win more often than their price says, buying longshots has an edge; if less often,
selling them (buying the favourite) does. python3 -m research.polymarket"""
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent
GAMMA = "https://gamma-api.polymarket.com/markets"
CLOB = "https://clob.polymarket.com/prices-history"


def get(url):
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
                return json.loads(r.read())
        except Exception:  # noqa: BLE001
            time.sleep(2 + a * 3)
    return None


def markets(n=3000):
    out, off = [], 0
    while len(out) < n and off < 20000:
        q = {"closed": "true", "limit": 500, "offset": off, "order": "volumeNum", "ascending": "false"}
        page = get(GAMMA + "?" + urllib.parse.urlencode(q))
        if not page:
            break
        for m in page:
            try:
                prices = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
                toks = json.loads(m.get("clobTokenIds") or "[]")
            except Exception:  # noqa: BLE001
                continue
            if len(prices) == 2 and len(toks) == 2 and sorted(prices) == [0.0, 1.0] and m.get("endDate"):
                out.append({"q": m["question"], "end": m["endDate"], "token": toks[0], "won": prices[0] == 1.0,
                            "vol": float(m.get("volumeNum") or 0), "cat": (m.get("category") or "")})
        off += 500
    return out[:n]


def price_before(m, days):
    h = get(f"{CLOB}?market={m['token']}&interval=max&fidelity=720")
    if not h or not h.get("history"):
        return None
    end = datetime.fromisoformat(m["end"].replace("Z", "+00:00")).timestamp()
    out = {}
    for d in days:
        t = end - d * 86400
        pts = [p for p in h["history"] if p["t"] <= t]
        out[d] = pts[-1]["p"] if pts else None
    return out


def main():
    ms = markets()
    with ThreadPoolExecutor(8) as ex:
        prices = list(ex.map(lambda m: price_before(m, (1, 7, 30)), ms))
    rows = [{**m, "p": p} for m, p in zip(ms, prices) if p]
    (OUT / "result_polymarket.json").write_text(json.dumps(rows))
    return rows


def report(rows):
    print(f"{len(rows)} resolved binary markets with price history")
    bins = [(0.01, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.35), (0.35, 0.65), (0.65, 0.80), (0.80, 0.90), (0.90, 0.95), (0.95, 0.99)]
    for d in (30, 7, 1):
        print(f"\nprice {d} day(s) before end -> actual win rate (both sides of each market counted)")
        for lo, hi in bins:
            pts = []
            for r in rows:
                p = r["p"].get(d)
                if p is None:
                    continue
                for price, won in ((p, r["won"]), (1 - p, not r["won"])):
                    if lo <= price < hi:
                        pts.append((price, won))
            if len(pts) >= 20:
                avg = sum(p for p, _ in pts) / len(pts)
                wr = sum(w for _, w in pts) / len(pts)
                roi = (wr - avg) / avg * 100
                print(f"  {lo:.2f}-{hi:.2f}: n={len(pts):5}  price {avg:.3f}  won {wr:.3f}  return per $ if bought {roi:+.0f}%")


if __name__ == "__main__":
    report(main())
