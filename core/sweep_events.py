"""sweep events: the funding-settlement window family (kind "funding_window"). Pure functions, no network.

An event is one funding settlement of one USDT perp with |rate| >= data.min_abs_funding. Around it the loader records, for every valid
(entry minute E, exit minute X) pair relative to the settlement, the long-side move xp/ep - 1 (entry at the open of the 1-minute bar
starting at E, exit at the open of the bar starting at X) and the highest high / lowest low of the bars held, as fractions of ep.
A rule picks a threshold, a mode (fade_payer: trade against the side that pays and collect the funding; take_payer: trade with it),
an entry offset, an exit offset and an entry delay (5 minutes: the same rule entered later; a rule must survive it).
Funding is charged when the entry is before the settlement and the exit after it. Costs are the perp round trip.
"""
import itertools

from core import sweep_config as sc
from core import sweep_engine as se

OFFS_E = (-60, -55, -15, -10, -1, 4)
OFFS_X = (1, 15, 60)
PAIRS = tuple((e, x) for e in OFFS_E for x in OFFS_X if e < x)
MODES = ("fade_payer", "take_payer")


def pair_key(e, x):
    return f"{e}:{x}"


def make_event(sym, ts, rate, bars):
    """bars: {minute open ts (s): (o, h, l, c)}. Returns the event dict or None when no pair has both prices."""
    vals = {}
    for e, x in PAIRS:
        b0, b1 = bars.get(ts + e * 60), bars.get(ts + x * 60)
        if b0 is None or b1 is None:
            continue
        ep, xp = b0[0], b1[0]
        held = [bars[ts + m * 60] for m in range(e, x) if ts + m * 60 in bars]
        if ep <= 0 or xp <= 0 or not held:
            continue
        vals[pair_key(e, x)] = [round(xp / ep - 1, 7), round(max(h[1] for h in held) / ep - 1, 7),
                                round(min(h[2] for h in held) / ep - 1, 7)]
    return {"sym": sym, "ts": ts, "f": rate, "v": vals} if vals else None


def events_for_symbol(sym, funding, bars_fn, min_abs, start_s, end_s):
    """funding: [(ts, rate)]. bars_fn(ts) -> {minute: bar} or None when its download failed. Returns (events, stats)."""
    out, st = [], {"extreme": 0, "no_bars": 0, "failed": 0}
    for t, rate in funding:
        ts = int(round(t / 60.0)) * 60
        if abs(rate) < min_abs or not start_s <= ts < end_s:
            continue
        st["extreme"] += 1
        bars = bars_fn(ts)
        if bars is None:
            st["failed"] += 1
            continue
        ev = make_event(sym, ts, rate, bars)
        if ev is None:
            st["no_bars"] += 1
            continue
        out.append(ev)
    return out, st


def expand(cfg):
    """Rules of a funding_window config: cartesian grid, invalid (entry+delay >= exit) combinations skipped."""
    g = cfg["grid"]
    bounds = {k: [sc.day(cfg["splits"][k][0]), sc.day(cfg["splits"][k][1])] for k in sc.SPLIT_NAMES}
    for k in sc.SPLIT_NAMES:
        if not bounds[k][0] < bounds[k][1]:
            raise sc.ConfigError("splits must be ordered")
    if any(m not in MODES for m in g["mode"]):
        raise sc.ConfigError("bad mode")
    if cfg["cost"]["model"] != "perp":
        raise sc.ConfigError("funding_window supports the perp cost model only")
    out = []
    for thr, mode, e, x, d in itertools.product(g["thr"], g["mode"], g["entry"], g["exit"], g["delay"]):
        ea = e + d
        if (ea, x) not in PAIRS:
            continue
        out.append({"id": rule_id(thr, mode, e, x, d), "style": "fw_" + mode, "thr": thr, "mode": mode, "entry": e, "exit": x,
                    "delay": d, "E": ea, "X": x, "size": dict(cfg["size"]), "cost": dict(cfg["cost"]), "bounds": bounds,
                    "tf": "1m", "n_symbols": 0, "lev": cfg["size"]["lev"], "k": cfg["size"].get("k", 1)})
    ids = [r["id"] for r in out]
    if len(ids) != len(set(ids)):
        raise sc.ConfigError("duplicate rule ids")
    return out


def rule_id(thr, mode, e, x, d):
    return f"fw[thr={thr},mode={mode},entry={e},exit={x},delay={d}]"


def twin_id(rule):
    """The 5-minute-delay variant of a delay-0 rule (None when it does not exist or the rule is already delayed)."""
    if rule["delay"] != 0:
        return None
    return rule_id(rule["thr"], rule["mode"], rule["entry"], rule["exit"], 5)


def trades_for_rule(rule, events):
    """Capped trades of a rule in the dict format of core.sweep_engine (t, te, x, sym, side, gross, cost, fund, net, mfe, mae)."""
    cm = rule["cost"]
    cost = 2 * (float(cm.get("fee", 0.0005)) + float(cm.get("slip", 0.0002)))
    key = pair_key(rule["E"], rule["X"])
    out = []
    for ev in events:
        if abs(ev["f"]) < rule["thr"] or key not in ev["v"]:
            continue
        gl, hi, lo = ev["v"][key]
        payer = 1 if ev["f"] > 0 else -1
        s = -payer if rule["mode"] == "fade_payer" else payer
        fund = s * ev["f"] if rule["E"] < 0 < rule["X"] else 0.0
        gross = s * gl
        mfe, mae = (hi, -lo) if s > 0 else (-lo, hi)
        t = ev["ts"] + rule["E"] * 60
        out.append({"sym": ev["sym"], "side": s, "t": t, "te": t, "x": ev["ts"] + rule["X"] * 60, "ep": 0.0, "xp": 0.0,
                    "gross": gross, "cost": cost, "fund": fund, "net": gross - cost - fund, "mfe": max(mfe, 0.0), "mae": max(mae, 0.0),
                    "reason": "time"})
    return se.apply_cap(out, int(rule["size"].get("k", 1)))
