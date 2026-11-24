"""Pure calculations for the quick historical screens of ops/lines/ (no network calls here; fetchers live in
research/studies/run.py). Each screen picks its horizon on train, judges it on validation and only reports the sign on test.
"""
import random
import re
import time

from core.news_backtest import block_bootstrap_p

# ------------------------------------------------------------------ L1 listings
_TICK = re.compile(r"^[A-Z0-9]{2,12}$")


def _paren_symbols(title: str) -> list:
    out = []
    for grp in re.findall(r"\(([^()]*)\)", title):
        for tok in grp.split(","):
            tok = tok.strip()
            if _TICK.match(tok) and tok not in out:
                out.append(tok)
    return out


def binance_listing_symbols(title: str) -> list:
    """'Binance Will List Sapien (SAPIEN) with Seed Tag Applied' -> ['SAPIEN']. Futures, margin, Launchpool,
    Alpha and pair-only notices are not spot listings and give []."""
    if not re.match(r"^Binance Will List\b", title.strip()):
        return []
    return _paren_symbols(title)


def upbit_listing_symbols(title: str) -> list:
    """Upbit KRW-market additions: '로켓풀(RPL), 아큐라스트(ACU) 원화 마켓 디지털 자산 추가' or
    'KRW, BTC 마켓 디지털 자산 추가 (NEAR, YGG)'. BTC/USDT-market-only additions give []."""
    if "디지털 자산 추가" not in title or not ("KRW" in title or "원화" in title):
        return []
    return [s for s in _paren_symbols(title) if s not in ("KRW", "BTC", "USDT")]


def close_at(bars: list, t: float, width: int):
    """bars: [(open_ts_s, close)] sorted. Close of the bar that contains t, or None when that bar is missing."""
    lo, hi = 0, len(bars) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        o = bars[mid][0]
        if o <= t < o + width:
            return bars[mid][1]
        if o > t:
            hi = mid - 1
        else:
            lo = mid + 1
    return None


L1_HORIZONS = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400, "7d": 7 * 86400}
L1_DELAY = 60                    # enter one minute after the announcement
L1_COST = 0.006                  # round trip: taker 0.1% + slippage 0.2% per side


def listing_returns(ts: float, m1: list, h1: list, bench_m1: list, bench_h1: list, cost: float = L1_COST) -> dict:
    """Net log-free simple return of the coin minus the BTC return over the same window, per horizon.
    Entry at the close of the 1-minute bar containing ts+60s; horizons <= 4h exit on 1-minute bars, longer on 1-hour bars."""
    t0 = ts + L1_DELAY
    p0, b0 = close_at(m1, t0, 60), close_at(bench_m1, t0, 60)
    out = {}
    if not p0 or not b0:
        return out
    for name, h in L1_HORIZONS.items():
        if h <= 4 * 3600:
            p1, b1 = close_at(m1, t0 + h, 60), close_at(bench_m1, t0 + h, 60)
        else:
            p1, b1 = close_at(h1, t0 + h, 3600), close_at(bench_h1, t0 + h, 3600)
        if p1 and b1:
            raw = p1 / p0 - 1
            out[name] = {"raw": raw, "abn": raw - (b1 / b0 - 1), "net": raw - (b1 / b0 - 1) - cost}
    return out


def split_of(ts: float, bounds: dict) -> str:
    """bounds = {'train': (start, end), ...} in unix seconds, end exclusive."""
    for k, (a, b) in bounds.items():
        if a <= ts < b:
            return k
    return "out"


def day_key(row: dict) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(row["ts"]))


def judge(rows: list, horizons: list, bounds: dict, cost_extra: float = 0.0, seed: int = 7) -> dict:
    """rows: [{'ts', 'symbol', 'venue', 'ret': {h: {'net': x}}}]. Pick the horizon with the best train mean, then
    report validation mean / block p (cluster = UTC day) and test mean, plus the result without the best 1 and 5 events."""
    rng = random.Random(seed)

    def vals(split, h):
        r = [x for x in rows if split_of(x["ts"], bounds) == split and h in x["ret"]]
        return [x["ret"][h]["net"] - cost_extra for x in r], [day_key(x) for x in r]

    table = {}
    for h in horizons:
        t = {}
        for split in bounds:
            v, k = vals(split, h)
            t[split] = {"n": len(v), "mean": round(sum(v) / len(v), 5) if v else None,
                        "p": round(block_bootstrap_p(v, k, rng), 4) if v else None}
        table[h] = t
    train_ok = [h for h in horizons if table[h]["train"]["mean"] is not None]
    if not train_ok:
        return {"table": table, "pick": None, "verdict": "no data"}
    pick = max(train_ok, key=lambda h: table[h]["train"]["mean"])
    v, k = vals("validation", pick)
    robust = {}
    for drop in (1, 5):
        if len(v) > drop:
            keep = sorted(zip(v, k), key=lambda z: z[0])[:-drop]
            robust[f"without_best_{drop}"] = round(sum(z[0] for z in keep) / len(keep), 5)
    val = table[pick]["validation"]
    test = table[pick].get("test", {})
    passed = (val["mean"] is not None and val["mean"] > 0 and val["p"] < 0.05
              and all(x > 0 for x in robust.values())
              and (test.get("mean") is None or test["mean"] > 0))
    killed = val["mean"] is None or val["mean"] <= 0 or val["p"] > 0.2 or any(x <= 0 for x in robust.values())
    return {"table": table, "pick": pick, "robust": robust,
            "verdict": "passed" if passed else ("killed" if killed else "inconclusive")}
