"""fundwin_okx_fwd: pure logic of the forward paper ledger that fades the paying side of OKX perpetual funding using OKX's own
published predicted rate (protocol: research/studies/protocol_fundwin_okx_fwd_20261125.md, locked). No network here.

Six cohorts: entry 15 / 5 / 1 minutes before the 8-hour settlement x threshold 0.3% / 0.5% on the predicted rate. Entry at the
measured bid (short) or ask (long) of the OKX ticker, exit 1 minute after the settlement at the opposite side of the book, taker
fee on both fills, the settled rate (OKX realizedRate) charged as funding, a random-side control on the same fills. One unit of
evidence = one settlement of one cohort (the mean over its trades), fed to a paired e-process (core.sequential).
"""
import hashlib
import math

from core import sequential as sq

GRID = 4 * 3600                    # settlements of OKX swaps fall on a 4-hour grid (addendum 2026-11-25: 8-hour and 4-hour interval swaps)
DAY8 = 8 * 3600
ENTRY_MINUTES = (15, 5, 1)
THRESHOLDS = (0.003, 0.005)
FEE_SIDE = 0.0005                  # OKX regular-user taker fee on swaps, per fill
CLIP = 0.05                        # unit returns are clipped to [-5%, +5%] for the e-process only (raw means are reported)
FAMILY_ALPHA = 0.05
N_COHORTS = len(ENTRY_MINUTES) * len(THRESHOLDS)
ALPHA = FAMILY_ALPHA / N_COHORTS
MIN_UNITS = 60


def cohort_id(minutes, thr):
    return f"m{minutes}_t{thr}"


COHORTS = [(cohort_id(m, t), m, t) for m in ENTRY_MINUTES for t in THRESHOLDS]


def next_settlement(now, min_lead=60):
    """First 4-hour grid time (00:00, 04:00, ... 20:00 UTC) at least `min_lead` seconds ahead."""
    t = (int(now) // GRID + 1) * GRID
    return t if t - now >= min_lead else t + GRID


def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def parse_rates(resp):
    """OKX public/funding-rate (instId=ANY) -> {instId: (predicted rate, fundingTime seconds)} for live USDT swaps."""
    out = {}
    for d in (resp or {}).get("data") or []:
        inst, rate, ft = d.get("instId", ""), _f(d.get("fundingRate")), _f(d.get("fundingTime"))
        if inst.endswith("-USDT-SWAP") and rate is not None and ft is not None:
            out[inst] = (rate, int(ft // 1000))
    return out


def parse_books(resp):
    """OKX market/tickers?instType=SWAP -> {instId: (bid, ask)} with a positive two-sided quote."""
    out = {}
    for d in (resp or {}).get("data") or []:
        bid, ask = _f(d.get("bidPx")), _f(d.get("askPx"))
        if d.get("instId", "").endswith("-USDT-SWAP") and bid and ask and 0 < bid <= ask:
            out[d["instId"]] = (bid, ask)
    return out


def parse_realized(resp, fund_time):
    """OKX funding-rate-history -> the settled rate of the settlement at `fund_time` (seconds), else None."""
    for d in (resp or {}).get("data") or []:
        ft = _f(d.get("fundingTime"))
        if ft is not None and int(ft // 1000) == int(fund_time):
            r = _f(d.get("realizedRate"))
            return r if r is not None else _f(d.get("fundingRate"))
    return None


def entries(rates, books, T, thr):
    """Trades opened now: instruments settling at T whose predicted |rate| >= thr, against the payer (a positive rate means longs
    pay, so short). Entry price: bid for a short, ask for a long."""
    out = []
    for inst, (rate, ft) in sorted(rates.items()):
        if ft != T or abs(rate) < thr or inst not in books:
            continue
        bid, ask = books[inst]
        side = -1 if rate > 0 else 1
        out.append({"inst": inst, "side": side, "pred": rate, "entry_px": bid if side < 0 else ask, "entry_bid": bid, "entry_ask": ask})
    return out


def control_side(T, inst, cohort):
    """Random side of the control, fixed by a hash so a rerun gives the same draw."""
    h = hashlib.sha256(f"{T}|{inst}|{cohort}".encode()).digest()[0]
    return 1 if h % 2 == 0 else -1


def settle_trade(entry, exit_book, settled, T, cohort):
    """Close one trade at the exit book with the settled rate. Returns the full trade row."""
    bid, ask = exit_book
    s = entry["side"]
    exit_px = ask if s < 0 else bid                      # buy back a short at the ask, sell a long at the bid
    fees = 2 * FEE_SIDE

    def pnl(side, ep, xp):
        return side * (xp / ep - 1) - fees - side * settled
    cs = control_side(T, entry["inst"], cohort)
    # the control trades the same two fills but on a random side: it sells at the bid and buys back at the ask, or the reverse
    c_entry = entry["entry_bid"] if cs < 0 else entry["entry_ask"]
    c_exit = ask if cs < 0 else bid
    mid_in, mid_out = (entry["entry_bid"] + entry["entry_ask"]) / 2, (bid + ask) / 2
    spread_paid = (entry["entry_ask"] - entry["entry_bid"]) / 2 / mid_in + (ask - bid) / 2 / mid_out
    net = pnl(s, entry["entry_px"], exit_px)
    return {"T": T, "cohort": cohort, "inst": entry["inst"], "side": s, "pred": entry["pred"], "settled": settled,
            "entry_px": entry["entry_px"], "exit_px": exit_px, "net": net, "net_2x": net - fees - spread_paid,
            "ctrl_side": cs, "ctrl_net": pnl(cs, c_entry, c_exit)}


def clip(x):
    return max(-CLIP, min(CLIP, x))


class Ledger:
    """e-process state of the six cohorts."""

    def __init__(self, state=None):
        self.eps = {}
        self.stats = {}
        for cid, _, _ in COHORTS:
            ep = sq.EProcess(alpha=ALPHA, lo=CLIP, hi=CLIP, paired=True)
            st = (state or {}).get(cid)
            if st:
                for k in ("n", "sum", "sumsq", "log_up", "log_down", "decision", "decided_at"):
                    setattr(ep, k, st["ep"][k])
            self.eps[cid] = ep
            self.stats[cid] = (st or {}).get("stats") or {"trades": 0, "model": 0.0, "ctrl": 0.0, "net_2x": 0.0, "clipped": 0, "units": 0}

    def add_unit(self, cohort, trades):
        """One settlement of one cohort: the mean over its trades. Returns the e-process decision."""
        if not trades:
            return self.eps[cohort].decision
        m = sum(t["net"] for t in trades) / len(trades)
        c = sum(t["ctrl_net"] for t in trades) / len(trades)
        st = self.stats[cohort]
        st["trades"] += len(trades)
        st["model"] += sum(t["net"] for t in trades)
        st["ctrl"] += sum(t["ctrl_net"] for t in trades)
        st["net_2x"] += sum(t["net_2x"] for t in trades)
        st["clipped"] += sum(1 for t in trades if abs(t["net"]) > CLIP)
        st["units"] += 1
        return self.eps[cohort].update(clip(m) - clip(c))

    def dump(self):
        return {cid: {"ep": {k: getattr(ep, k) for k in ("n", "sum", "sumsq", "log_up", "log_down", "decision", "decided_at")},
                      "stats": self.stats[cid]} for cid, ep in self.eps.items()}

    def verdicts(self):
        """Per cohort: the frozen verdict rule. edge: paired e-process rejects at alpha/6, at least 60 units, raw mean net > 0 and raw
        mean net at twice the costs > 0. no edge: the paired e-process rejects the other way."""
        out = {}
        for cid, ep in self.eps.items():
            st = self.stats[cid]
            n = st["trades"]
            mean = st["model"] / n if n else None
            mean2 = st["net_2x"] / n if n else None
            if ep.decision == "edge" and ep.n >= MIN_UNITS and mean and mean > 0 and mean2 and mean2 > 0:
                v = "edge"
            elif ep.decision.startswith("no edge"):
                v = "no edge"
            else:
                v = "continue"
            out[cid] = {**ep.view(), "verdict": v, "trades": n, "mean_net": mean, "mean_net_2x": mean2,
                        "mean_ctrl": st["ctrl"] / n if n else None, "clipped_trades": st["clipped"]}
        return out


def tracking(rows):
    """rows: [{'minutes': 15, 'pred': x, 'settled': y}] -> per entry minute: n, median / p90 abs error, bias, correlation."""
    out = {}
    for m in ENTRY_MINUTES:
        pairs = [(r["pred"], r["settled"]) for r in rows if r["minutes"] == m and r.get("settled") is not None]
        if len(pairs) < 3:
            out[str(m)] = {"n": len(pairs)}
            continue
        errs = sorted(abs(p - s) for p, s in pairs)
        mp, ms = sum(p for p, _ in pairs) / len(pairs), sum(s for _, s in pairs) / len(pairs)
        sp = math.sqrt(sum((p - mp) ** 2 for p, _ in pairs))
        ss_ = math.sqrt(sum((s - ms) ** 2 for _, s in pairs))
        corr = sum((p - mp) * (s - ms) for p, s in pairs) / (sp * ss_) if sp > 0 and ss_ > 0 else None
        out[str(m)] = {"n": len(pairs), "median_abs_err": errs[len(errs) // 2], "p90_abs_err": errs[int(0.9 * (len(errs) - 1))],
                       "bias": mp - ms, "corr": corr}
    return out
