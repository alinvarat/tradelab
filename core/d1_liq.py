"""D1: fade of a forced-flow proxy (volume spike plus a one-sided taker move) on small Binance USDT-M perps, 5-60 minute holds.
Pure functions, no network. Spec: research/studies/protocol_d1_liq_20261126.md (locked before any D1 return was computed).

Per-symbol series are arrays of 1-minute bars indexed by (ts - T0) / 60, NaN where a minute is missing. Trades are dicts in the
core.sweep_engine format so that core.sweep_stats.gate / evaluate / judge_family apply unchanged.
"""
import calendar
import math
import random
import statistics
import time
from array import array

NAN = float("nan")


def utc(y, m, d):
    return float(calendar.timegm((y, m, d, 0, 0, 0)))


T0 = utc(2023, 12, 1)                      # a multiple of 300 s
START, END = utc(2024, 1, 1), utc(2026, 10, 29)
T_LAST = utc(2026, 11, 1)
NM = int((T_LAST - T0) // 60)
BOUNDS = {"train": (START, utc(2025, 7, 1)), "validation": (utc(2025, 7, 1), utc(2026, 3, 1)), "test": (utc(2026, 3, 1), END)}
MONTHS = (END - START) / 86400 / 30.4375

FEE_RT = 0.0010
SLIP_SIDE = 0.0015
COST = FEE_RT + 2 * SLIP_SIDE              # 0.40% round trip
FUND = 0.0001
STOP = 0.05
STOP_SLIP = 0.005
HOLDS = (300, 900, 3600)
DELAYS = (60, 300)
JUDGED_DELAY = 60
SIZES = {"s1": (10.0, 0.03), "s2": (20.0, 0.05)}
IMB = 0.60
BASE_W, MIN_BASE_W, MIN_DAY_QV = 288, 250, 5_000_000.0
CLUSTER_S = 1800
N_CTRL, CTRL_MIN, CTRL_TRIES = 3, 2, 8
SEED = 20261126
SIZE = {"lev": 3, "k": 1}
CFG = {"alpha": 0.05, "account_usd": 147.0,
       "gate": {"min_train_trades": 30, "target_multiple": 3.0, "mfe_quantile": 0.9, "min_vol_cost": 10, "min_x": 0.2},
       "pass": {"min_val_trades": 30, "min_test_trades": 20}}
MAJORS = {"BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "TRX", "AVAX", "LINK", "DOT", "LTC", "BCH", "NEAR", "UNI", "ATOM", "ETC",
          "XLM", "FIL", "APT", "ARB", "OP", "SUI", "TON", "SHIB", "PEPE", "AAVE", "HBAR", "INJ", "TAO"}


def base_of(sym):
    return sym[:-4].lstrip("0123456789") if sym.endswith("USDT") else sym


def is_small(sym):
    return sym.endswith("USDT") and "_" not in sym and sym.isascii() and base_of(sym) not in MAJORS


def rule_id(size, hold, delay):
    return f"{size}|h{hold // 60}m|d{delay // 60}m"


def judged_rules():
    return [(rule_id(s, h, JUDGED_DELAY), s, h, JUDGED_DELAY) for s in SIZES for h in HOLDS]


def reported_rules():
    return [(rule_id(s, h, d), s, h, d) for s in SIZES for h in HOLDS for d in DELAYS if d != JUDGED_DELAY]


# ---------------------------------------------------------------- series
class Series:
    def __init__(self):
        self.o, self.h, self.l, self.c, self.qv, self.tb = (array("d", [NAN]) * NM for _ in range(6))

    def add_rows(self, rows):
        """rows: parse_kline tuples (open_s, o, h, l, c, vol, close_s, qv, trades, taker_base, taker_quote)."""
        for r in rows:
            i = int((r[0] - T0) // 60)
            if 0 <= i < NM:
                self.o[i], self.h[i], self.l[i], self.c[i], self.qv[i], self.tb[i] = r[1], r[2], r[3], r[4], r[7], r[10]


def windows(s):
    """5-minute windows: (open, close, qv, taker-buy qv) arrays, NaN open/close when a window has a missing edge minute."""
    n = NM // 5
    wo, wc, wq, wt = (array("d", [NAN]) * n for _ in range(4))
    for k in range(n):
        m = 5 * k
        wo[k], wc[k] = s.o[m], s.c[m + 4]
        q = t = 0.0
        for j in range(m, m + 5):
            v = s.qv[j]
            if v == v:
                q += v
                t += s.tb[j]
        wq[k], wt[k] = (q if q > 0 else NAN), t
    return wo, wc, wq, wt


def find_events(s, a=START, b=END):
    """Trigger windows of one symbol with T (the window end) in [a, b). Returns dicts {ts, side, ret, vm, imb, s2}; side +1 = long
    (fade of a down move). Cluster rule: an event within 30 minutes of the symbol's previous event is dropped."""
    wo, wc, wq, wt = windows(s)
    n = len(wo)
    out, last = [], -1e18
    k0 = max(BASE_W, int((a - T0) // 300) - 1)
    for k in range(k0, n):
        T = T0 + (k + 1) * 300
        if T >= b:
            break
        o, c, q = wo[k], wc[k], wq[k]
        if o != o or c != c or q != q or o <= 0:
            continue
        ret = c / o - 1
        if abs(ret) < 0.03 or T < a:
            continue
        imb = wt[k] / q
        if (ret < 0 and imb > 1 - IMB) or (ret > 0 and imb < IMB):
            continue
        base = [v for v in wq[k - BASE_W:k] if v == v]
        if len(base) < MIN_BASE_W or sum(base) < MIN_DAY_QV:
            continue
        med = statistics.median(base)
        if med <= 0:
            continue
        vm = q / med
        if vm < SIZES["s1"][0]:
            continue
        if T - last < CLUSTER_S:
            continue
        last = T
        out.append({"ts": T, "side": 1 if ret < 0 else -1, "ret": round(ret, 5), "vm": round(vm, 2), "imb": round(imb, 3),
                    "s2": bool(vm >= SIZES["s2"][0] and abs(ret) >= SIZES["s2"][1])})
    return out


# ---------------------------------------------------------------- simulation
def trade(s, side, ts, delay, hold, stop=STOP):
    """One trade on the 1-minute series. Entry at the open of the first bar at or after ts + delay (<= 3 bars late), exit at the open of the
    bar `hold` later (<= 3 bars late) or at the stop (fill at stop plus 0.5% slippage). side +1 long, -1 short. dict(gross, mfe, mae, te, x,
    reason) or None. te / x are epoch seconds (exit = end of the stop bar)."""
    i0 = int(math.ceil((ts + delay - T0) / 60))
    e = next((i for i in range(i0, i0 + 3) if 0 <= i < NM and s.o[i] == s.o[i]), None)
    if e is None:
        return None
    entry = s.o[e]
    steps = hold // 60
    x = next((i for i in range(e + steps, e + steps + 3) if i < NM and s.o[i] == s.o[i]), None)
    if x is None or entry <= 0:
        return None
    hi = lo = entry
    gross, reason, end = None, "time", x
    for i in range(e, x):
        h, l = s.h[i], s.l[i]
        if h != h:
            continue
        hi, lo = max(hi, h), min(lo, l)
        if (side > 0 and l <= entry * (1 - stop)) or (side < 0 and h >= entry * (1 + stop)):
            gross, reason, end = -(stop + STOP_SLIP), "stop", i + 1
            break
    if gross is None:
        gross = side * (s.o[x] / entry - 1)
    mfe = (hi - entry) / entry if side > 0 else (entry - lo) / entry
    mae = (entry - lo) / entry if side > 0 else (hi - entry) / entry
    return {"gross": gross, "mfe": max(mfe, 0.0), "mae": max(mae, 0.0), "te": T0 + e * 60, "x": T0 + end * 60, "reason": reason}


def control_gross(s, sym, ts, side, delay, hold):
    """Mean gross of the same trade at 3 random minutes of the same symbol in the same calendar month (>= 2 usable), else None."""
    rng = random.Random(f"{SEED}:{sym}:{int(ts)}:{hold}:{delay}")
    g = time.gmtime(ts - 1)
    lo = max(0, int((calendar.timegm((g.tm_year, g.tm_mon, 1, 0, 0, 0)) - T0) // 60))
    hi = min(NM - 70, int((calendar.timegm((g.tm_year + (g.tm_mon == 12), g.tm_mon % 12 + 1, 1, 0, 0, 0)) - T0) // 60) - 70)
    vals = []
    for _ in range(CTRL_TRIES):
        if hi <= lo or len(vals) >= N_CTRL:
            break
        t = trade(s, side, T0 + rng.randrange(lo, hi) * 60 - delay, delay, hold)
        if t:
            vals.append(t["gross"])
    return sum(vals) / len(vals) if len(vals) >= CTRL_MIN else None


def event_row(s, sym, ev):
    """All outcomes of one event: {rule key 'h<sec>d<sec>': [gross, ctrl_gross, mfe, mae, reason, te, x]} (unusable ones listed in dropped)."""
    row = dict(ev, sym=sym, r={}, dropped=[])
    for d in DELAYS:
        for h in HOLDS:
            k = f"h{h}d{d}"
            t = trade(s, ev["side"], ev["ts"], d, h)
            if not t:
                row["dropped"].append(k)
                continue
            cg = control_gross(s, sym, ev["ts"], ev["side"], d, h)
            row["r"][k] = [round(t["gross"], 6), None if cg is None else round(cg, 6), round(t["mfe"], 5), round(t["mae"], 5),
                           t["reason"], t["te"], t["x"]]
    return row


# ---------------------------------------------------------------- selection and statistics
def make_trade(row, key):
    v = row["r"][key]
    t = {"sym": row["sym"], "side": row["side"], "t": row["ts"], "te": v[5], "x": v[6], "ep": 0.0, "xp": 0.0, "gross": v[0], "cost": COST,
         "fund": FUND, "net": v[0] - COST - FUND, "mfe": v[2], "mae": v[3], "reason": v[4]}
    if v[1] is not None:
        t["ctrl_net"] = v[1] - COST - FUND
    return t


def select(rows, size, hold, delay):
    """Trades of one rule, one at a time, first come in time order. Returns (trades, skipped_busy, skipped_no_trade)."""
    key = f"h{hold}d{delay}"
    out, free, busy, nobar = [], 0.0, 0, 0
    for r in sorted(rows, key=lambda r: (r["ts"], r["sym"])):
        if size == "s2" and not r["s2"]:
            continue
        if r["ts"] + delay < free:
            busy += 1
            continue
        if key not in r["r"]:
            nobar += 1
            continue
        t = make_trade(r, key)
        out.append(t)
        free = t["x"]
    return out, busy, nobar


def stats(values, months):
    n = len(values)
    if n < 2:
        return {"n": n}
    m = sum(values) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in values) / (n - 1))
    s = m / sd if sd > 0 else 0.0
    return {"n": n, "mean": round(m, 5), "sd": round(sd, 5), "s": round(s, 4), "per_month": round(n / months, 3),
            "x": round(n / months * s * s, 4), "hit": round(sum(1 for v in values if v > 0) / n, 3)}
