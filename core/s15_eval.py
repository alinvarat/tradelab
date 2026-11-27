"""Verdicts for the 3-day S2 poll and the 48-snapshot S4 series (pre-registered in research/studies/RESULTS.md and
research/studies/protocol_s2s4_poll_20261127.md). Pure functions over the rows the collectors write; no network."""
import statistics

POLL_GAP_MAX_S = 120          # a gap between two answered polls longer than this is not covered time


def covered_hours(polls):
    ok = sorted(p["t"] for p in polls if p.get("ok"))
    return sum(b - a for a, b in zip(ok, ok[1:]) if b - a <= POLL_GAP_MAX_S) / 3600.0


def s2_evaluate(rows, polls, hours_required=66.0):
    """rows: entrants {qualifies, delay_s, sellers (None = not measured), truncated}; polls: {t, ok}."""
    hrs = covered_hours(polls)
    n_polls = len(polls)
    ok_share = (sum(1 for p in polls if p.get("ok")) / n_polls) if n_polls else 0.0
    qual = [r for r in rows if r.get("qualifies")]
    delays = [r["delay_s"] for r in rows if r.get("delay_s") is not None]
    meas = [r for r in qual if r.get("sellers") is not None and not r.get("truncated")]
    no_exit = sum(1 for r in meas if r["sellers"] < 2)
    out = {"covered_hours": hrs, "polls": n_polls, "poll_ok_share": ok_share, "entrants": len(rows), "qualifying": len(qual),
           "median_delay_s": statistics.median(delays) if delays else None,
           "sell_measured": len(meas), "sell_no_exit": no_exit,
           "monthly_qualifying": (len(qual) / hrs * 730.0) if hrs > 0 else None}
    kills = []
    if out["median_delay_s"] is not None and out["median_delay_s"] > 60:
        kills.append(f"delay: median {out['median_delay_s']:.0f} s > 60")
    if len(meas) >= 10 and no_exit / len(meas) > 0.20:
        kills.append(f"exit: {no_exit}/{len(meas)} qualifying entrants with < 2 distinct sellers (> 20%)")
    if out["monthly_qualifying"] is not None and out["monthly_qualifying"] < 100:
        kills.append(f"count: {out['monthly_qualifying']:.0f} qualifying entrants a month < 100")
    out["kills"] = kills
    if hrs < hours_required:
        out["status"] = "RUNNING"
    elif ok_share < 0.8:
        out["status"] = "VOID (poll coverage)"
    else:
        out["status"] = "KILL: " + "; ".join(kills) if kills else "SURVIVES stage 0 (forward protocol next)"
    return out


def s4_evaluate(snaps, need=44):
    """snaps: one dict per hourly snapshot {t, matched: [{k, p, mismatch, ...}], alloc_yield}."""
    n = len(snaps)
    pairs, bad = set(), set()
    for s in snaps:
        for m in s.get("matched", []):
            key = (m["k"], m["p"])
            pairs.add(key)
            if m.get("mismatch"):
                bad.add(key)
    days = n / 24.0
    ys = [s.get("alloc_yield") or 0.0 for s in snaps]
    out = {"snapshots": n, "distinct_pairs": len(pairs), "pairs_per_day": (len(pairs) / days) if days else None,
           "mismatch_pairs": len(bad), "mismatch_share": (len(bad) / len(pairs)) if pairs else None,
           "mean_alloc_yield_per_day": statistics.mean(ys) if ys else None, "max_alloc_yield_per_day": max(ys) if ys else None}
    kills, standalone = [], False
    if out["mean_alloc_yield_per_day"] is not None and out["mean_alloc_yield_per_day"] < 0.0373:
        standalone = True
    if out["mean_alloc_yield_per_day"] is not None and out["mean_alloc_yield_per_day"] < 0.005:
        kills.append(f"yield: mean {out['mean_alloc_yield_per_day']:.4%} a day < 0.5%")
    if out["pairs_per_day"] is not None and out["pairs_per_day"] < 10:
        kills.append(f"pairs: {out['pairs_per_day']:.1f} distinct matched pairs a day < 10")
    if len(pairs) >= 10 and len(bad) / len(pairs) > 0.20:
        kills.append(f"sources: {len(bad)}/{len(pairs)} pairs name different resolution sources (> 20%)")
    out["kills"], out["killed_as_standalone"] = kills, standalone
    if n < need:
        out["status"] = "RUNNING"
    elif kills:
        out["status"] = "KILL: " + "; ".join(kills)
    elif standalone:
        out["status"] = "KILLED as standalone (< 3.73% a day); component only"
    else:
        out["status"] = "SURVIVES stage 0 (forward protocol next)"
    return out
