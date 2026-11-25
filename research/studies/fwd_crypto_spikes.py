"""Hourly forward paper runner for L12B_F / L8B_F (protocol_fwd_crypto_spikes_20261125.md). I/O only; logic is in
core/fwd_crypto.py. Usage: python research/studies/fwd_crypto_spikes.py <state_dir>
Reads/writes <state_dir>/fwd_crypto_state.json and fwd_crypto_summary.json. Spot bars: data-api.binance.vision (Binance's
own hosts answer 451 from GitHub Actions); perp existence and funding: OKX public API (Bybit answers 403)."""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import fwd_crypto as fc   # noqa: E402

SPOT = "https://data-api.binance.vision/api/v3"
OKX = "https://www.okx.com/api/v5/public"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) tradelab-research", "Accept": "application/json"}
HOUR, DAY = fc.HOUR, fc.DAY
MAX_FAIL_SHARE = 0.10               # more failed symbol fetches than this: do not advance the processed time
ERRORS: list = []


def get_json(url: str, tries: int = 3, timeout: int = 25):
    last = None
    for n in range(tries):
        try:
            with urlopen(Request(url, headers=UA), timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:   # noqa: BLE001
            last = e
            time.sleep(1.5 * (n + 1))
    raise RuntimeError(f"{url.split('?')[0]}: {type(last).__name__} {last}")


def klines(symbol, interval, limit=None, start=None, now=None):
    q = f"{SPOT}/klines?symbol={symbol}&interval={interval}" + (f"&limit={limit}" if limit else "")
    if start is not None:
        q += f"&startTime={int(start * 1000)}"
    return fc.parse_klines(get_json(q), now=now)


def funding(symbol):
    time.sleep(0.25)    # OKX: 10 requests / 2 s
    return fc.parse_okx_funding(get_json(f"{OKX}/funding-rate-history?instId={fc.okx_inst(symbol)}&limit=100"))


def many(fn, items, workers=8):
    def one(x):
        try:
            return x, fn(x)
        except Exception as e:   # noqa: BLE001
            ERRORS.append(f"{x}: {e}"[:200])
            return x, None
    with ThreadPoolExecutor(workers) as ex:
        return dict(ex.map(one, items))


def by_ts(bars):
    return {b[0]: b for b in bars}


def btc_map(bars):
    return {b[0]: (b[1], b[4]) for b in bars}


def entry_inputs(ev, bars_by_sym, btc, pool, line):
    """Entry price/BTC open for the event and a seeded same-time control with data at that entry."""
    e = ev["entry_ts"]
    sym_bar = by_ts(bars_by_sym[ev["symbol"]]).get(e)
    if not sym_bar or e not in btc:
        return None
    control = None
    for c in fc.control_order(line, e, ev["symbol"], pool):
        b = by_ts(bars_by_sym.get(c) or []).get(e)
        if b:
            control = {"symbol": c, "entry_px": b[1], "btc_entry": btc[e][0]}
            break
    return sym_bar[1], btc[e][0], control


def process_line(state, now, line, perp_syms):
    cfg = fc.LINES[line]
    step = cfg["step"]
    last_closed = now - now % step - step
    key = "h_next" if line == "L12B_F" else "d_next"
    if last_closed < state[key]:
        return {"processed": 0}
    min_ev = max(state[key], last_closed - (23 * HOUR if line == "L12B_F" else 6 * DAY))
    if min_ev > state[key]:
        state["gap_hours_missed"] += int((min_ev - state[key]) / HOUR)
    lookback = 720 * HOUR if line == "L12B_F" else 22 * DAY
    n = 27 if line == "L12B_F" else 45
    syms = sorted(perp_syms)
    short = many(lambda s: klines(s, cfg["interval"], limit=n), syms)
    failed = [s for s, v in short.items() if v is None]
    if len(failed) > MAX_FAIL_SHARE * max(1, len(syms)):
        raise RuntimeError(f"{line}: {len(failed)}/{len(syms)} symbol fetches failed; not advancing")
    bars = {s: v for s, v in short.items() if v}
    btc = btc_map(klines("BTCUSDT", cfg["interval"], limit=1000 if line == "L12B_F" else 80,
                         start=(min_ev - lookback) if line == "L12B_F" else None))
    thr = 0.08 if line == "L12B_F" else 0.20
    pool, cands = [], []
    for s, b in bars.items():
        closed = [x for x in b if x[0] + step <= now]
        if line == "L12B_F":
            tail = closed[-24:]
            if len(tail) == 24 and sum(x[5] for x in tail) / 24 >= cfg["min_qv"]:
                pool.append(s)
        else:
            tail = closed[-20:]
            if len(tail) == 20 and sum(x[5] for x in tail) / 20 >= cfg["min_qv"]:
                pool.append(s)
        if any(x[0] >= min_ev and x[0] + step <= now and x[1] > 0 and x[4] / x[1] - 1 >= thr for x in closed):
            cands.append(s)
    events = []
    full = {}
    if cands:
        if line == "L12B_F":
            full = many(lambda s: klines(s, "1h", limit=1000, start=min_ev - lookback), cands)
        else:
            full = {s: bars[s] for s in cands}
        fund = many(funding, cands, workers=1)
        bad = [s for s in cands if not full.get(s) or fund.get(s) is None]
        if bad:      # never advance past an event we could not evaluate: the next hourly run retries
            raise RuntimeError(f"{line}: data missing for candidates {bad[:5]}; not advancing")
        for s in cands:
            last = state["lines"][line]["last_event"].get(s, 0.0)
            if line == "L12B_F":
                events += fc.detect_hourly(s, full[s], btc, fund[s], min_ev, last)
            else:
                events += fc.detect_daily(s, full[s], btc, fund[s], min_ev, last)
    events.sort(key=lambda e: (e["entry_ts"], e["symbol"]))
    opened = 0
    all_bars = {**bars}
    for ev in events:
        got = entry_inputs(ev, all_bars, btc, pool, line)
        if got is None:
            ERRORS.append(f"{line} {ev['symbol']}: entry bar missing")
            continue
        px, bpx, control = got
        if fc.open_event(state, ev, px, bpx, control):
            opened += 1
    state[key] = last_closed + step
    return {"processed": 1, "candidates": len(cands), "events": len(events), "opened": opened, "pool": len(pool),
            "failed_symbols": len(failed)}


def exit_fetch(symbol, entry_px, line, entry_ts, now):
    """(exit_px, btc_exit, funding_paid) for a position/control, or None when data is not yet available. The exit
    price is the last hold bar's close, or 2x entry when any bar of the hold reached it (collateral wiped out)."""
    cfg = fc.LINES[line]
    bt = fc.exit_bar_ts(line, entry_ts)
    nb = int(cfg["hold"] / cfg["step"])
    hold = klines(symbol, cfg["interval"], limit=nb, start=entry_ts, now=now)
    bb = klines("BTCUSDT", cfg["interval"], limit=1, start=bt, now=now)
    if len(hold) != nb or hold[-1][0] != bt or not bb or bb[0][0] != bt or bt + cfg["step"] > now:
        return None
    px, liq = fc.exit_price(entry_px, hold, hold[-1][4])
    f = funding(symbol)
    return px, bb[0][4], fc.funding_paid(f, entry_ts, entry_ts + cfg["hold"]), liq


def close_due(state, now):
    closed = 0
    for line in fc.LINES:
        for pos in list(state["lines"][line]["open"]):
            if not fc.due(pos, now):
                continue
            try:
                main = exit_fetch(pos["symbol"], pos["entry_px"], line, pos["entry_ts"], now)
            except Exception as e:   # noqa: BLE001
                ERRORS.append(f"close {pos['id']}: {e}"[:200])
                continue
            if main is None:
                continue
            cexit = None
            c = pos.get("control")
            if c:
                try:
                    r = exit_fetch(c["symbol"], c["entry_px"], line, pos["entry_ts"], now)
                    if r:
                        cexit = {"exit_px": r[0], "btc_exit": r[1], "funding": r[2]}
                except Exception as e:   # noqa: BLE001
                    ERRORS.append(f"close control {pos['id']}: {e}"[:200])
                if cexit is None and now < pos["entry_ts"] + fc.LINES[line]["hold"] + 3 * HOUR:
                    continue    # wait up to 3 h for the control's data, then close without a control
            fc.close_position(state, pos, main[0], main[1], main[2], now, cexit, main[3])
            closed += 1
    return closed


def main():
    d = Path(sys.argv[1])
    d.mkdir(parents=True, exist_ok=True)
    sp = d / "fwd_crypto_state.json"
    now = time.time()
    state = json.loads(sp.read_text()) if sp.exists() else fc.new_state(now)
    out = {"run_at": int(now)}
    try:
        info = get_json(f"{SPOT}/exchangeInfo?permissions=SPOT")
        spot = {x["symbol"] for x in info["symbols"] if x["status"] == "TRADING" and x["quoteAsset"] == "USDT"
                and fc.eligible_symbol(x["symbol"])}
        live = fc.parse_okx_live_swaps(get_json(f"{OKX}/instruments?instType=SWAP"))
        perp_syms = {s for s in spot if fc.okx_inst(s) in live}
        out["universe"] = {"spot_usdt": len(spot), "with_okx_perp": len(perp_syms)}
        if len(perp_syms) < 50:
            raise RuntimeError(f"only {len(perp_syms)} perps matched; refusing to run")
        out["closed_now"] = close_due(state, now)
        for line in fc.LINES:
            if not fc.line_active(state, line):
                out[line] = {"stopped": fc.evidence(state["lines"][line]["closed"])["verdict"]}
                continue
            try:
                out[line] = process_line(state, now, line, perp_syms)
            except Exception as e:   # noqa: BLE001
                ERRORS.append(f"{line}: {e}"[:300])
    except Exception as e:   # noqa: BLE001
        ERRORS.append(f"run: {e}"[:300])
    sp.write_text(json.dumps(state, indent=1))
    summary = {"protocol": "research/studies/protocol_fwd_crypto_spikes_20261125.md", "start_ts": state["start_ts"],
               "gap_hours_missed": state["gap_hours_missed"], "h_next": state["h_next"], "d_next": state["d_next"],
               "last_run": out, "errors": ERRORS[-20:], "n_errors": len(ERRORS),
               "lines": {k: fc.line_summary(state, k) for k in fc.LINES},
               "open_positions": {k: [{x: p[x] for x in ("symbol", "entry_ts", "entry_px", "stake", "move")} |
                                      {"control": (p["control"] or {}).get("symbol")} for p in state["lines"][k]["open"]]
                                  for k in fc.LINES},
               "closed_last": {k: [{x: r.get(x) for x in ("symbol", "entry_ts", "net", "control_net", "funding", "pnl_usd", "stake")}
                                   for r in state["lines"][k]["closed"][-10:]] for k in fc.LINES}}
    (d / "fwd_crypto_summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps({"last_run": out, "n_errors": len(ERRORS), "errors": ERRORS[-5:],
                      "lines": {k: {x: v for x, v in s.items() if x != "evidence"} for k, s in summary["lines"].items()}}, default=str))


if __name__ == "__main__":
    main()
