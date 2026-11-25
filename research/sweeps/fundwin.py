"""Loader for the funding_window family (network; Actions only): extreme funding settlements and the 1-minute bars around them."""
import time
from concurrent.futures import ThreadPoolExecutor

from core import sweep_config as sc
from core import sweep_events as sev
from research.sweeps import loaders


def universe():
    """Every USDT-M perp symbol that ever had monthly klines (delisted included), quarterlies out."""
    from research.studies import binance_vision as bv
    return [s for s in bv.list_symbols("futures/um", "USDT") if "_" not in s]


def _minute_bars(bv, sym, ts, cache):
    """{minute open ts: (o, h, l, c)} for the day(s) around a settlement, or None when a daily file failed."""
    out = {}
    for t in (ts - 3700, ts + 3700):
        g = time.gmtime(t)
        key = (g.tm_year, g.tm_mon, g.tm_mday)
        if key not in cache:
            cache[key] = bv.fetch("futures/um", "daily", "klines", sym, key, "1m", bv.parse_kline)
        rows = cache[key]
        if rows is None:
            return None
        for r in rows:
            out[r[0]] = (r[1], r[2], r[3], r[4])
    return out


def load_symbol(sym, spec):
    from research.studies import binance_vision as bv
    start_s, end_s = sc.day(spec["start"]), sc.day(spec["end"])
    min_abs = float(spec["min_abs_funding"])

    def prod():
        fund, failed = bv.funding(sym, start_s, end_s)
        if failed:
            return {"events": [], "stats": {"funding_failed": len(failed)}}, False
        cache = {}
        events, st = sev.events_for_symbol(sym, fund, lambda ts: _minute_bars(bv, sym, ts, cache), min_abs, start_s, end_s)
        st["funding_rows"] = len(fund)
        return {"events": events, "stats": st}, st["failed"] == 0
    return loaders._cached(f"fw2|{sym}|{start_s}|{end_s}|{min_abs}", prod)


def load_events(symbols, spec, workers=12):
    """(events, gaps) for a list of symbols."""
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(lambda s: load_symbol(s, spec), symbols))
    events, gaps = [], {"symbols": len(symbols), "extreme": 0, "no_bars": 0, "failed": 0, "funding_failed": 0, "funding_rows": 0}
    for r in res:
        events.extend(r["events"])
        for k in gaps:
            if k != "symbols":
                gaps[k] += r["stats"].get(k, 0)
    return events, gaps


# ------------------------------------------------------------------ fundwin3 (predicted rate from premium index minutes)
def _day_rows(bv, market, kind, sym, ts_from, ts_to, cache, interval="1m"):
    """Rows of every daily file overlapping [ts_from, ts_to]; None when a download failed, [] pieces for missing files."""
    out = []
    t = int(ts_from) // 86400 * 86400
    while t <= ts_to:
        g = time.gmtime(t)
        key = (market, kind, g.tm_year, g.tm_mon, g.tm_mday)
        if key not in cache:
            cache[key] = bv.fetch(market, "daily", kind, sym, (g.tm_year, g.tm_mon, g.tm_mday), interval, bv.parse_kline)
        if cache[key] is None:
            return None
        out.extend(cache[key])
        t += 86400
    return out


def load_symbol_pred(sym, spec):
    from research.studies import binance_vision as bv
    start_s, end_s = sc.day(spec["start"]), sc.day(spec["end"])
    cand_min = float(spec["cand_min"])

    def prod():
        fund, failed = bv.funding(sym, start_s, end_s)
        hrows, f2 = bv.premium_index(sym, start_s - 86400, end_s, "1h")
        if failed or f2:
            return {"events": [], "stats": {"funding_failed": len(failed), "premium_failed": len(f2)}}, False
        hourly = {int(r[0]): r[4] for r in hrows}
        cache = {}

        def prem_fn(ps, ts):
            rows = _day_rows(bv, "futures/um", "premiumIndexKlines", sym, ps, ts, cache)
            return None if rows is None else {r[0]: r[4] for r in rows}

        def bars_fn(ts):
            rows = _day_rows(bv, "futures/um", "klines", sym, ts - 3700, ts + 3700, cache)
            return None if rows is None else {r[0]: (r[1], r[2], r[3], r[4]) for r in rows}

        def spot_fn(ts):
            rows = _day_rows(bv, "spot", "klines", sym, ts - 3700, ts + 3700, cache)
            return {r[0]: (r[1], r[2], r[3], r[4]) for r in rows} if rows else None
        events, st = sev.events_pred_for_symbol(sym, fund, hourly, prem_fn, bars_fn, spot_fn, cand_min, start_s, end_s)
        st["funding_rows"] = len(fund)
        return {"events": events, "stats": st}, st["failed"] == 0
    return loaders._cached(f"fw3|{sym}|{start_s}|{end_s}|{cand_min}", prod)


def load_events_pred(symbols, spec, workers=12):
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(lambda s: load_symbol_pred(s, spec), symbols))
    keys = ("candidates", "no_premium", "no_bars", "failed", "with_spot", "funding_failed", "premium_failed", "funding_rows")
    events, gaps = [], {"symbols": len(symbols), **{k: 0 for k in keys}}
    for r in res:
        events.extend(r["events"])
        for k in keys:
            gaps[k] += r["stats"].get(k, 0)
    return events, gaps
