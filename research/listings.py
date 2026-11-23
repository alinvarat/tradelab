"""New-listing study on Binance spot USDT pairs, including pairs that were later delisted (status BREAK),
to limit survivorship bias. For each pair: the first 90 daily candles after listing.
Questions: if you buy at the close of listing day 1 (the first price most people can get), how often does it
reach 6x within 30 days, how often does it lose 50% or more, and what does holding 7/30/90 days return?
python3 -m research.listings"""
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT = Path(__file__).resolve().parent
API = "https://api.binance.com/api/v3"
STABLE = {"USDC", "BUSD", "TUSD", "USDP", "FDUSD", "DAI", "PAX", "EUR", "GBP", "AUD", "TRY", "BRL", "USDS", "AEUR", "UST"}


def get(url):
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
                return json.loads(r.read())
        except Exception:  # noqa: BLE001
            time.sleep(2 + a * 3)
    return None


def first_days(sym):
    k = get(f"{API}/klines?symbol={sym}&interval=1d&startTime=0&limit=91")
    if not k or len(k) < 8:
        return None
    return {"symbol": sym, "t0": k[0][0] / 1000, "o": [float(x[1]) for x in k], "h": [float(x[2]) for x in k],
            "l": [float(x[3]) for x in k], "c": [float(x[4]) for x in k], "qv": [float(x[7]) for x in k]}


def main():
    info = get(f"{API}/exchangeInfo")
    syms = [s["symbol"] for s in info["symbols"] if s["quoteAsset"] == "USDT" and s["baseAsset"] not in STABLE
            and not s["baseAsset"].endswith(("UP", "DOWN", "BULL", "BEAR"))]
    with ThreadPoolExecutor(6) as ex:
        rows = [r for r in ex.map(first_days, syms) if r]
    rows = [r for r in rows if r["t0"] > 1546300800]  # listed 2019 or later (USDT was not the main quote before)
    res = []
    for r in rows:
        c, h, l = r["c"], r["h"], r["l"]
        p = c[0]  # buy at listing-day close
        w30 = range(1, min(31, len(c)))
        res.append({"symbol": r["symbol"], "year": time.gmtime(r["t0"]).tm_year,
                    "day1_vs_open": c[0] / r["o"][0] - 1,
                    "max30": max(h[i] for i in w30) / p if len(c) > 1 else 1,
                    "min30": min(l[i] for i in w30) / p if len(c) > 1 else 1,
                    "r7": c[7] / p - 1 if len(c) > 7 else None, "r30": c[30] / p - 1 if len(c) > 30 else None,
                    "r90": c[90] / p - 1 if len(c) > 90 else None, "vol_day1": r["qv"][0]})
    (OUT / "result_listings.json").write_text(json.dumps(res))
    return res


def report(res):
    def pc(x):
        return f"{x * 100:.1f}%"
    print(f"{len(res)} pairs listed since 2019 (delisted included where Binance still serves candles)")
    hit6 = [r for r in res if r["max30"] >= 6]
    hit2 = [r for r in res if r["max30"] >= 2]
    half = [r for r in res if r["min30"] <= 0.5]
    print(f"touched 6x within 30 days of day-1 close: {len(hit6)} ({pc(len(hit6) / len(res))}): {[r['symbol'] for r in hit6][:15]}")
    print(f"touched 2x: {pc(len(hit2) / len(res))}; fell 50%+ at some point: {pc(len(half) / len(res))}")
    for k in ("r7", "r30", "r90"):
        v = sorted(r[k] for r in res if r[k] is not None)
        print(f"hold {k[1:]:>2} days: median {pc(v[len(v) // 2])}, mean {pc(sum(v) / len(v))}, "
              f"positive {pc(sum(x > 0 for x in v) / len(v))}, n={len(v)}")
    by = {}
    for r in res:
        if r["r30"] is not None:
            by.setdefault(r["year"], []).append(r["r30"])
    print("median 30-day return by listing year:", {y: pc(sorted(v)[len(v) // 2]) for y, v in sorted(by.items())})
    # does a strong first day predict anything?
    for lab, f in [("day 1 up >50%", lambda r: r["day1_vs_open"] > 0.5), ("day 1 down", lambda r: r["day1_vs_open"] < 0)]:
        v = sorted(r["r30"] for r in res if r["r30"] is not None and f(r))
        if v:
            print(f"{lab}: n={len(v)} median 30d {pc(v[len(v) // 2])}, mean {pc(sum(v) / len(v))}")


if __name__ == "__main__":
    report(main())
