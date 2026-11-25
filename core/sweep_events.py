"""sweep events: the funding-settlement window family (kind "funding_window"). Pure functions, no network.

An event is one funding settlement of one USDT perp with |rate| >= data.min_abs_funding. Around it the loader records, for every valid
(entry minute E, exit minute X) pair relative to the settlement, the long-side move xp/ep - 1 (entry at the open of the 1-minute bar
starting at E, exit at the open of the bar starting at X) and the highest high / lowest low of the bars held, as fractions of ep.
A rule picks a threshold, a mode (fade_payer: trade against the side that pays and collect the funding; take_payer: trade with it),
an entry offset, an exit offset and an entry delay (5 minutes: the same rule entered later; a rule must survive it).
Funding is charged when the entry is before the settlement and the exit after it. Costs are the perp round trip.
"""
import itertools
import math

from core import sweep_config as sc
from core import sweep_engine as se

OFFS_E = (-60, -55, -15, -10, -1, 4)
OFFS_X = (1, 15, 60)
PAIRS = tuple((e, x) for e in OFFS_E for x in OFFS_X if e < x)
MODES = ("fade_payer", "take_payer")


def pair_key(e, x):
    return f"{e}:{x}"


def make_event(sym, ts, rate, bars, prev=None, pairs=None):
    """bars: {minute open ts (s): (o, h, l, c)}. Returns the event dict or None when no pair has both prices."""
    vals = {}
    for e, x in (pairs or PAIRS):
        b0, b1 = bars.get(ts + e * 60), bars.get(ts + x * 60)
        if b0 is None or b1 is None:
            continue
        ep, xp = b0[0], b1[0]
        held = [bars[ts + m * 60] for m in range(e, x) if ts + m * 60 in bars]
        if ep <= 0 or xp <= 0 or not held:
            continue
        vals[pair_key(e, x)] = [round(xp / ep - 1, 7), round(max(h[1] for h in held) / ep - 1, 7),
                                round(min(h[2] for h in held) / ep - 1, 7)]
    return {"sym": sym, "ts": ts, "f": rate, "fp": prev, "v": vals} if vals else None


def events_for_symbol(sym, funding, bars_fn, min_abs, start_s, end_s):
    """funding: [(ts, rate)]. bars_fn(ts) -> {minute: bar} or None when its download failed. Returns (events, stats)."""
    out, st = [], {"extreme": 0, "no_bars": 0, "failed": 0}
    prev = None
    for t, rate in sorted(funding):
        ts = int(round(t / 60.0)) * 60
        fp, prev = prev, rate
        # an event is kept when the settled rate OR the previous settlement's rate (known before the entry) is extreme
        if (abs(rate) < min_abs and (fp is None or abs(fp) < min_abs)) or not start_s <= ts < end_s:
            continue
        st["extreme"] += 1
        bars = bars_fn(ts)
        if bars is None:
            st["failed"] += 1
            continue
        ev = make_event(sym, ts, rate, bars, fp)
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
    for sig, thr, mode, e, x, d in itertools.product(g.get("sig", ["realized"]), g["thr"], g["mode"], g["entry"], g["exit"], g["delay"]):
        ea = e + d
        if (ea, x) not in PAIRS:
            continue
        out.append({"id": rule_id(thr, mode, e, x, d, sig), "style": f"fw_{sig}_{mode}", "sig": sig, "thr": thr, "mode": mode, "entry": e, "exit": x,
                    "delay": d, "E": ea, "X": x, "size": dict(cfg["size"]), "cost": dict(cfg["cost"]), "bounds": bounds,
                    "tf": "1m", "n_symbols": 0, "lev": cfg["size"]["lev"], "k": cfg["size"].get("k", 1)})
    ids = [r["id"] for r in out]
    if len(ids) != len(set(ids)):
        raise sc.ConfigError("duplicate rule ids")
    return out


def rule_id(thr, mode, e, x, d, sig="realized"):
    """sig: 'realized' selects and signs events by the rate settled at the event (known only at the settlement: look-ahead for
    any entry before it); 'prev' uses the previous settlement's rate, known before every entry."""
    base = f"thr={thr},mode={mode},entry={e},exit={x},delay={d}"
    return f"fw[{base}]" if sig == "realized" else f"fw[sig={sig},{base}]"


def twin_id(rule):
    """The 5-minute-delay variant of a delay-0 rule (None when it does not exist or the rule is already delayed)."""
    if rule["delay"] != 0:
        return None
    return rule_id(rule["thr"], rule["mode"], rule["entry"], rule["exit"], 5, rule["sig"])


def trades_for_rule(rule, events):
    """Capped trades of a rule in the dict format of core.sweep_engine (t, te, x, sym, side, gross, cost, fund, net, mfe, mae)."""
    cm = rule["cost"]
    cost = 2 * (float(cm.get("fee", 0.0005)) + float(cm.get("slip", 0.0002)))
    key = pair_key(rule["E"], rule["X"])
    out = []
    for ev in events:
        sel = ev["f"] if rule.get("sig", "realized") == "realized" else ev.get("fp")
        if sel is None or abs(sel) < rule["thr"] or key not in ev["v"]:
            continue
        gl, hi, lo = ev["v"][key]
        payer = 1 if sel > 0 else -1
        s = -payer if rule["mode"] == "fade_payer" else payer
        fund = s * ev["f"] if rule["E"] < 0 < rule["X"] else 0.0
        gross = s * gl
        mfe, mae = (hi, -lo) if s > 0 else (-lo, hi)
        t = ev["ts"] + rule["E"] * 60
        out.append({"sym": ev["sym"], "side": s, "t": t, "te": t, "x": ev["ts"] + rule["X"] * 60, "ep": 0.0, "xp": 0.0,
                    "gross": gross, "cost": cost, "fund": fund, "net": gross - cost - fund, "mfe": max(mfe, 0.0), "mae": max(mae, 0.0),
                    "reason": "time"})
    return se.apply_cap(out, int(rule["size"].get("k", 1)))


# ------------------------------------------------------------------ fundwin3: the rate predicted from data available before entry
OFFS_E3 = (-60, -55, -15, -10, -5, 0, -1, 4)
PAIRS3 = tuple((e, x) for e in OFFS_E3 for x in OFFS_X if e < x)
INTEREST_8H = 0.0001           # Binance USD-M: interest 0.01% per 8h
CLAMP_8H = 0.0005              # clamp(interest - premium, -0.05%, +0.05%) per 8h
MIN_PREM_COVER = 0.9


def funding_formula(avg_premium, interval_h, cap=None):
    """Binance USD-M funding: F = P + clamp(I - P, -c, +c), P the time-weighted average premium index of the interval; interest and
    clamp are scaled by interval_h / 8 for symbols with shorter intervals (an assumption: the tracking report checks it)."""
    i = INTEREST_8H * interval_h / 8.0
    c = CLAMP_8H * interval_h / 8.0
    f = avg_premium + max(-c, min(c, i - avg_premium))
    if cap:
        f = max(-cap, min(cap, f))
    return f


def predict_rate(prem, ps, t_pred, interval_h, cap=None):
    """Predicted settled rate at time t_pred from the 1-minute premium index closes of the minutes [ps, t_pred) of the current
    interval (prem: {minute open ts: premium close}); None when under 90% of those minutes are present. cap: the largest |rate| this
    symbol settled at before (a causal stand-in for its cap/floor)."""
    n = int((t_pred - ps) // 60)
    if n <= 0:
        return None
    vals = [prem[m] for m in range(ps, ps + n * 60, 60) if m in prem]
    if len(vals) < MIN_PREM_COVER * n:
        return None
    return funding_formula(sum(vals) / len(vals), interval_h, cap)


def cs_spread(bars):
    """Corwin-Schultz (2012) high-low spread estimate as a fraction of price, averaged over consecutive minute pairs; bars:
    {minute open ts: (o, h, l, c)}. None when no pair is usable."""
    k = 3 - 2 * math.sqrt(2)
    out = []
    for m in sorted(bars):
        nxt = bars.get(m + 60)
        if nxt is None:
            continue
        h1, l1, h2, l2 = bars[m][1], bars[m][2], nxt[1], nxt[2]
        if min(l1, l2) <= 0 or h1 < l1 or h2 < l2:
            continue
        beta = math.log(h1 / l1) ** 2 + math.log(h2 / l2) ** 2
        gamma = math.log(max(h1, h2) / min(l1, l2)) ** 2
        alpha = (math.sqrt(2 * beta) - math.sqrt(beta)) / k - math.sqrt(gamma / k)
        e = math.exp(min(alpha, 5.0))
        out.append(max(2 * (e - 1) / (1 + e), 0.0))
    return sum(out) / len(out) if out else None


def spot_values(ts, bars, pairs):
    """{pair key: spot move xp/ep - 1} for the same entry/exit minutes."""
    out = {}
    for e, x in pairs:
        b0, b1 = bars.get(ts + e * 60), bars.get(ts + x * 60)
        if b0 and b1 and b0[0] > 0 and b1[0] > 0:
            out[pair_key(e, x)] = round(b1[0] / b0[0] - 1, 7)
    return out


def events_pred_for_symbol(sym, funding, hourly, prem_fn, bars_fn, spot_fn, cand_min, start_s, end_s):
    """Events of fundwin3 for one symbol. funding [(ts, settled rate)], hourly {hour open ts: premium close} (candidate filter only),
    prem_fn(ps, ts) -> {minute: premium close} | None, bars_fn(ts) -> perp 1m bars | None, spot_fn(ts) -> spot 1m bars | None.
    Every event carries est {E: predicted rate at entry minute E} computed from premium minutes before E only, the Corwin-Schultz
    spread of the perp (sp) and of the spot (sps), perp moves v and spot moves vs. Returns (events, stats)."""
    out, st = [], {"candidates": 0, "no_premium": 0, "no_bars": 0, "failed": 0, "with_spot": 0}
    prev_ts, prev_rate, cap_run = None, None, 0.0
    for t, rate in sorted(funding):
        ts = int(round(t / 60.0)) * 60
        ps, fp = prev_ts, prev_rate
        cap = cap_run if cap_run > 0 else None
        prev_ts, prev_rate, cap_run = ts, rate, max(cap_run, abs(rate))
        if ps is None or not start_s <= ts < end_s:
            continue
        interval_h = (ts - ps) / 3600.0
        if not 0 < interval_h <= 9:
            continue
        hrs = [hourly[h] for h in range(-(-ps // 3600) * 3600, ts - 3600, 3600) if h in hourly]
        if not hrs or abs(funding_formula(sum(hrs) / len(hrs), interval_h, cap)) < cand_min:
            continue
        st["candidates"] += 1
        prem = prem_fn(ps, ts)
        bars = bars_fn(ts)
        if prem is None or bars is None:
            st["failed"] += 1
            continue
        est = {str(e): predict_rate(prem, ps, ts + e * 60, interval_h, cap) for e in OFFS_E3}
        if all(v is None for v in est.values()):
            st["no_premium"] += 1
            continue
        ev = make_event(sym, ts, rate, bars, fp, PAIRS3)
        if ev is None:
            st["no_bars"] += 1
            continue
        ev["est"] = est
        ev["sp"] = cs_spread(bars)
        sb = spot_fn(ts)
        if sb:
            ev["vs"], ev["sps"] = spot_values(ts, sb, PAIRS3), cs_spread(sb)
            st["with_spot"] += 1
        out.append(ev)
    return out, st


def expand_pred(cfg):
    """Rules of a funding_window_pred config: sig is always 'pred' (the rate predicted at the entry minute)."""
    g = cfg["grid"]
    bounds = {k: [sc.day(cfg["splits"][k][0]), sc.day(cfg["splits"][k][1])] for k in sc.SPLIT_NAMES}
    for k in sc.SPLIT_NAMES:
        if not bounds[k][0] < bounds[k][1]:
            raise sc.ConfigError("splits must be ordered")
    if any(m not in ("fade_payer", "hedged") for m in g["mode"]) or cfg["cost"]["model"] != "perp":
        raise sc.ConfigError("funding_window_pred: modes fade_payer|hedged, perp cost model")
    out = []
    for thr, mode, e, x, d in itertools.product(g["thr"], g["mode"], g["entry"], g["exit"], g["delay"]):
        ea = e + d
        if (ea, x) not in PAIRS3:
            continue
        out.append({"id": rule_id(thr, mode, e, x, d, "pred"), "style": f"fwp_{mode}", "sig": "pred", "thr": thr, "mode": mode,
                    "entry": e, "exit": x, "delay": d, "E": ea, "X": x, "size": dict(cfg["size"]), "cost": dict(cfg["cost"]),
                    "bounds": bounds, "tf": "1m", "n_symbols": 0, "lev": cfg["size"]["lev"], "k": cfg["size"].get("k", 1)})
    if len({r["id"] for r in out}) != len(out):
        raise sc.ConfigError("duplicate rule ids")
    return out


def trades_pred(rule, events):
    """Capped trades of a fundwin3 rule. The event is selected and signed by est at the entry minute only. fade_payer: perp against
    the paying side, collecting the settled funding. hedged: positive predicted rate only, short perp plus the same notional of spot
    (delta-neutral), paying both venues' costs. Cost per trade: 2 * taker fee + max(Corwin-Schultz spread, floor) per venue."""
    cm = rule["cost"]
    fee, sfee, floor = float(cm.get("fee", 0.0005)), float(cm.get("spot_fee", 0.001)), float(cm.get("spread_floor", 0.0004))
    key, ek = pair_key(rule["E"], rule["X"]), str(rule["E"])
    out = []
    for ev in events:
        est = (ev.get("est") or {}).get(ek)
        if est is None or abs(est) < rule["thr"] or key not in ev["v"]:
            continue
        gl, hi, lo = ev["v"][key]
        fund_on = rule["E"] < 0 < rule["X"]
        cost = 2 * fee + max(ev.get("sp") or 0.0, floor)
        if rule["mode"] == "hedged":
            gs = (ev.get("vs") or {}).get(key)
            if est <= 0 or gs is None:
                continue
            s, gross = -1, -gl + gs
            cost += 2 * sfee + max(ev.get("sps") or 0.0, floor)
            fund = -ev["f"] if fund_on else 0.0
            mfe, mae = abs(est), max(0.0, -gross)
        else:
            s = -1 if est > 0 else 1
            gross = s * gl
            fund = s * ev["f"] if fund_on else 0.0
            mfe, mae = (hi, -lo) if s > 0 else (-lo, hi)
        t = ev["ts"] + rule["E"] * 60
        out.append({"sym": ev["sym"], "side": s, "t": t, "te": t, "x": ev["ts"] + rule["X"] * 60, "ep": 0.0, "xp": 0.0,
                    "gross": gross, "cost": cost, "fund": fund, "net": gross - cost - fund, "mfe": max(mfe, 0.0),
                    "mae": max(mae, 0.0), "reason": "time"})
    return se.apply_cap(out, int(rule["size"].get("k", 1)))


def tracking_error(events, a, b):
    """Formula check on [a, b): for every entry minute E, how well the predicted rate tracks the settled rate:
    {E: {n, median_abs_err, p90_abs_err, bias, corr}} with E minutes relative to the settlement (negative = before)."""
    out = {}
    for e in OFFS_E3:
        pairs = [(ev["est"][str(e)], ev["f"]) for ev in events if a <= ev["ts"] < b and (ev.get("est") or {}).get(str(e)) is not None]
        if len(pairs) < 3:
            out[str(e)] = {"n": len(pairs)}
            continue
        errs = sorted(abs(p - f) for p, f in pairs)
        mp, mf = sum(p for p, _ in pairs) / len(pairs), sum(f for _, f in pairs) / len(pairs)
        sp = math.sqrt(sum((p - mp) ** 2 for p, _ in pairs))
        sf = math.sqrt(sum((f - mf) ** 2 for _, f in pairs))
        corr = sum((p - mp) * (f - mf) for p, f in pairs) / (sp * sf) if sp > 0 and sf > 0 else None
        out[str(e)] = {"n": len(pairs), "median_abs_err": errs[len(errs) // 2], "p90_abs_err": errs[int(0.9 * (len(errs) - 1))],
                       "bias": mp - mf, "corr": corr}
    return out
