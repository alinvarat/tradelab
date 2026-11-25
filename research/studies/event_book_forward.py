"""Forward event book paper ledger (research/studies/protocol_event_book_20261125.md). Runs on GitHub Actions only
(workflow event_book.yml, mode forward, dispatched by the keeper). One job polls for ~9 minutes every 30 s, then
writes state; the next job is dispatched by the keeper, so latency from notice to entry is under a minute when the runner
is available.

    python research/studies/event_book_forward.py <state_dir> [minutes]

<state_dir>/state.json holds seen notices and open trades; <state_dir>/trades.jsonl is append-only (one closed trade with
the real net return and 200 control returns); <state_dir>/summary.json is the ledger view (e-process, cohorts).
Public market data only; no keys, no orders."""
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import event_book as eb   # noqa: E402
from core import sequential as sq   # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 tradelab-research"}
CONF = Path(ROOT) / "research" / "event_book" / "components.json"
MAX_NOTICE_AGE_S = 15 * 60
MIN_CONTROL_TURNOVER = 100_000.0     # 24h USD turnover a control perp needs
LATE_DROP_S = 6 * 3600


def get(url, timeout=15, tries=3):
    for k in range(tries):
        try:
            with urlopen(Request(url, headers=UA), timeout=timeout) as r:
                return json.loads(r.read())
        except Exception:  # noqa: BLE001
            if k == tries - 1:
                return None
            time.sleep(1 + k)


# ---------------------------------------------------------------- venue: Bybit linear USDT perps, else OKX swaps
class Venue:
    name = "bybit"

    def __init__(self):
        self.inst = {}
        self.books = {}
        self.name = "okx"                       # Bybit answers 403 (country block) to GitHub runners, probe 2026-11-25
        self.refresh()

    def refresh(self) -> bool:
        """Reload instruments (rarely) and the all-symbol book. Returns False when the venue does not answer."""
        if self.name == "bybit":
            d = get("https://api.bybit.com/v5/market/tickers?category=linear")
            if not d or d.get("retCode") != 0:
                return False
            books = {}
            for t in d["result"]["list"]:
                s = t["symbol"]
                if s.endswith("USDT") and t.get("bid1Price") and t.get("ask1Price"):
                    try:
                        books[s[:-4]] = (float(t["bid1Price"]), float(t["ask1Price"]), float(t.get("turnover24h") or 0))
                    except ValueError:
                        pass
            self.books = books
            if not self.inst:
                cur, out = "", {}
                for _ in range(10):
                    dd = get("https://api.bybit.com/v5/market/instruments-info?category=linear&limit=1000"
                             + (f"&cursor={cur}" if cur else ""))
                    if not dd or dd.get("retCode") != 0:
                        break
                    for i in dd["result"]["list"]:
                        if i.get("quoteCoin") == "USDT" and i.get("status") == "Trading":
                            lf = i.get("lotSizeFilter") or {}
                            out[i["baseCoin"]] = {"symbol": i["symbol"], "min_qty": float(lf.get("minOrderQty") or 0),
                                                  "qty_step": float(lf.get("qtyStep") or 0),
                                                  "min_notional": float(lf.get("minNotionalValue") or eb.MIN_NOTIONAL_USD)}
                    cur = dd["result"].get("nextPageCursor") or ""
                    if not cur:
                        break
                self.inst = out
            return bool(self.books)
        d = get("https://www.okx.com/api/v5/market/tickers?instType=SWAP")
        if not d or d.get("code") != "0":
            return False
        books = {}
        for t in d["data"]:
            iid = t["instId"]
            if iid.endswith("-USDT-SWAP") and t.get("bidPx") and t.get("askPx"):
                try:
                    books[iid[:-10]] = (float(t["bidPx"]), float(t["askPx"]), float(t.get("volCcy24h") or 0) * float(t["last"]))
                except ValueError:
                    pass
        self.books = books
        if not self.inst:
            dd = get("https://www.okx.com/api/v5/public/instruments?instType=SWAP")
            out = {}
            for i in (dd or {}).get("data", []):
                if i["instId"].endswith("-USDT-SWAP") and i.get("state") == "live":
                    ct = float(i["ctVal"])
                    out[i["instId"][:-10]] = {"symbol": i["instId"], "min_qty": float(i["minSz"]) * ct,
                                              "qty_step": float(i["lotSz"]) * ct, "min_notional": eb.MIN_NOTIONAL_USD}
            self.inst = out
        return bool(self.books)

    def resolve(self, base: str):
        """Perp base coin for a notice ticker (tries the 1000x contract names too), or None."""
        for cand in (base, "1000" + base, "10000" + base, "1000000" + base):
            if cand in self.inst and cand in self.books:
                return cand
        return None

    def bars(self, base: str, t0: float, t1: float):
        """[(open_ts, high, low, close)] 1-minute bars covering [t0, t1], or None on failure."""
        sym = self.inst[base]["symbol"] if base in self.inst else base + "USDT"
        if self.name == "bybit":
            d = get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol={sym}&interval=1"
                    f"&start={int(t0 * 1000)}&end={int(t1 * 1000)}&limit=1000")
            if not d or d.get("retCode") != 0:
                return None
            return sorted((int(k[0]) // 1000, float(k[2]), float(k[3]), float(k[4])) for k in d["result"]["list"])
        out, after = {}, int(t1 * 1000) + 60000
        for _ in range(8):                      # history-candles: <= 100 bars, newest first, older than `after`
            d = get(f"https://www.okx.com/api/v5/market/history-candles?instId={sym}&bar=1m&after={after}&limit=100")
            if not d or d.get("code") != "0":
                return None
            rows = d.get("data") or []
            if not rows:
                break
            for k in rows:
                out[int(k[0]) // 1000] = (float(k[2]), float(k[3]), float(k[4]))
            oldest = min(int(k[0]) for k in rows)
            if oldest / 1000 <= t0:
                break
            after = oldest
        return sorted((t, *v) for t, v in out.items() if t0 - 60 <= t <= t1 + 60) or None


# ---------------------------------------------------------------- components, state, notices
def load_components() -> dict:
    return json.loads(CONF.read_text())


def load_state(d: Path) -> dict:
    try:
        return json.loads((d / "state.json").read_text())
    except Exception:  # noqa: BLE001
        return {"seen": [], "open": [], "polls": 0, "first_poll_ts": None, "skipped": {}, "events": 0}


def save_state(d: Path, st: dict):
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "state.tmp"
    tmp.write_text(json.dumps(st, separators=(",", ":")))
    tmp.replace(d / "state.json")


def notices():
    from core import market_collect as mc
    mc.UA = mc.BROWSER_UA
    return mc.listing_notices()


def match(conf: dict, ev: dict) -> list:
    """Components that take this notice event."""
    return [c for c in conf["components"] if ev["kind"] in c["kinds"] and ev["venue"] in c["venues"]]


def open_trades(st, conf, ven, ev, now, rng):
    skipped = st["skipped"]
    for c in match(conf, ev):
        if ev["ts"] < c["effective_from"]:
            continue
        if len({t["key"] for t in st["open"]}) >= eb.MAX_UNITS:
            skipped[f"{c['name']}:cap_open_units"] = skipped.get(f"{c['name']}:cap_open_units", 0) + 1
            continue
        sym_list = ev["symbols"]
        coins = [(s, ven.resolve(s)) for s in sym_list]
        tradable = [(s, b) for s, b in coins if b]
        for s, b in coins:
            if not b:
                skipped[f"{c['name']}:no_perp"] = skipped.get(f"{c['name']}:no_perp", 0) + 1
        for s, b in tradable:
            bid, ask, _ = ven.books[b]
            side = c["side"]
            entry = ask if side > 0 else bid
            universe = [k for k, v in ven.books.items() if v[2] >= MIN_CONTROL_TURNOVER and k in ven.inst]
            ctrl = eb.random_controls(rng, universe, {b}, eb.N_CONTROLS)
            mn = max(ven.inst[b]["min_notional"], ven.inst[b]["min_qty"] * entry)
            st["open"].append({"key": ev["key"], "comp": c["name"], "sym": b, "venue": ven.name, "side": side,
                               "w": eb.split_unit(c["weight"], len(tradable)), "entry_ts": now, "notice_ts": ev["ts"],
                               "entry_px": entry, "half_spread": (ask - bid) / (ask + bid), "hold_s": c["hold_s"],
                               "stop": c["stop"], "min_notional": mn,
                               "ctrl": [(k, ven.books[k][1] if side > 0 else ven.books[k][0], (ven.books[k][1] - ven.books[k][0]) / (ven.books[k][1] + ven.books[k][0])) for k in ctrl]})


def settle(t, ven, now):
    """Real and control net returns for one due trade, from 1-minute bars and the entry half-spread."""
    t0, t1 = t["entry_ts"], t["entry_ts"] + t["hold_s"]

    def one(base, entry, hs):
        bars = ven.bars(base, t0, t1 + 60)
        if not bars:
            return None
        inside = [(h, lo) for ts, h, lo, c in bars if t0 <= ts < t1]
        last = [c for ts, h, lo, c in bars if ts <= t1][-1:] or [bars[-1][3]]
        adverse = 1 - hs if t["side"] > 0 else 1 + hs
        net, stopped = eb.trade_return(t["side"], entry, inside, last[0] * adverse, t["stop"])
        return (net, stopped)
    real = one(t["sym"], t["entry_px"], t["half_spread"])
    if real is None:
        return None
    with ThreadPoolExecutor(12) as ex:
        ctrl = list(ex.map(lambda c: one(*c), t["ctrl"]))
    return {"key": t["key"], "comp": t["comp"], "sym": t["sym"], "venue": t["venue"], "side": t["side"], "w": t["w"],
            "entry_ts": t["entry_ts"], "exit_ts": t1, "notice_ts": t["notice_ts"], "entry_px": t["entry_px"],
            "ret": real[0], "stopped": real[1], "min_notional": t["min_notional"],
            "ctrl": [c[0] if c else None for c in ctrl], "ctrl_missing": sum(1 for c in ctrl if c is None)}


def poll(d: Path, conf: dict, ven: Venue, rng: random.Random):
    st = load_state(d)
    now = time.time()
    st["polls"] += 1
    st["first_poll_ts"] = st["first_poll_ts"] or now
    ven.refresh()
    new = 0
    groups = {}                                  # one notice = one risk unit: group the symbols of a notice
    for ev in notices():
        key = f"{ev['venue']}:{ev['kind']}:{ev['symbol']}:{int(ev['ts'])}"
        if key in st["seen"]:
            continue
        st["seen"].append(key)
        if now - ev["ts"] > MAX_NOTICE_AGE_S:
            st["skipped"]["stale_at_first_sight"] = st["skipped"].get("stale_at_first_sight", 0) + 1
            continue
        g = groups.setdefault((ev["venue"], ev["kind"], int(ev["ts"])), {**ev, "symbols": []})
        g["symbols"].append(ev["symbol"])
    for (venue, kind, ts), g in groups.items():
        st["events"] += 1
        new += 1
        open_trades(st, conf, ven, {**g, "key": f"{venue}:{kind}:{ts}"}, now, rng)
    st["seen"] = st["seen"][-3000:]
    keep, closed = [], []
    for t in st["open"]:
        if now < t["entry_ts"] + t["hold_s"] + 90:
            keep.append(t)
            continue
        res = settle(t, ven, now)
        if res:
            closed.append(res)
        elif now - (t["entry_ts"] + t["hold_s"]) < LATE_DROP_S:
            keep.append(t)
        else:
            st["skipped"]["unpriced_at_exit"] = st["skipped"].get("unpriced_at_exit", 0) + 1
    st["open"] = keep
    if closed:
        with open(d / "trades.jsonl", "a") as f:
            for c in closed:
                f.write(json.dumps(c, separators=(",", ":")) + "\n")
    save_state(d, st)
    return st, new, len(closed)


def view(d: Path, conf: dict, st: dict) -> dict:
    trades = []
    try:
        trades = [json.loads(l) for l in (d / "trades.jsonl").read_text().splitlines() if l.strip()]
    except Exception:  # noqa: BLE001
        pass
    now = time.time()
    t_start = conf["forward_start_ts"]
    day0 = (int(t_start) // 86400) * 86400
    day1 = (int(now) // 86400) * 86400            # up to yesterday: whole days only
    out = {"run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "venue": None, "polls": st["polls"],
           "events_seen": st["events"], "open": len(st["open"]), "closed": len(trades), "skipped": st["skipped"],
           "components": {c["name"]: sum(1 for t in trades if t["comp"] == c["name"]) for c in conf["components"]}}
    if trades:
        real = eb.run_wallet(trades, -1, t0=t_start)
        out["real_wallet"] = {k: real[k] for k in ("equity", "banked", "halted", "trades", "skipped")}
        out["mean_net_per_trade"] = round(sum(t["ret"] for t in trades) / len(trades), 5)
        ctrl_means = [sum(t["ctrl"][k] for t in trades if t["ctrl"][k] is not None) / max(1, sum(1 for t in trades if t["ctrl"][k] is not None))
                      for k in range(eb.N_CONTROLS)]
        out["control_mean_net_per_trade"] = round(sum(ctrl_means) / len(ctrl_means), 5)
        starts = eb.monday_starts(t_start, now)
        out["cohorts"] = eb.cohort_outcomes(trades, starts, now)
    if day1 > day0 and trades:
        series = eb.paired_series(trades, day0, day1)
        e = sq.EProcess(paired=True, lo=eb.E_LO, hi=eb.E_HI)
        for v in series:
            e.update(v)
        out["e_process"] = e.view()
    return out


def main():
    d = Path(sys.argv[1])
    minutes = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    d.mkdir(parents=True, exist_ok=True)
    conf = load_components()
    ven = Venue()
    rng = random.Random()
    end = time.time() + minutes * 60
    st = None
    while True:
        st, new, closed = poll(d, conf, ven, rng)
        print(json.dumps({"t": time.strftime("%H:%M:%S"), "venue": ven.name, "new": new, "closed": closed,
                          "open": len(st["open"]), "events": st["events"]}), flush=True)
        if time.time() + 30 >= end:
            break
        time.sleep(30)
    v = view(d, conf, st)
    v["venue"] = ven.name
    (d / "summary.json").write_text(json.dumps(v, indent=1, default=str))
    print(json.dumps({k: v.get(k) for k in ("events_seen", "open", "closed", "components", "e_process", "skipped")}, default=str))


if __name__ == "__main__":
    main()
