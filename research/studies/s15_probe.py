"""S1-S5 stage-0 probes (counts, reach, fees, depth; no rule return). Rules: RESULTS.md "S1-S5 stage-0 probes: pre-registration".
Run only on GitHub Actions: gh workflow run "Research studies" -f study=s1_hl_ladder|s2_dex_trending|s3_anchor_perps|s4_kalshi_poly|s5_stale_quote.
Each study returns (summary, rows) with `verdict`, `kills`, `pending`, `integrity`. Every study has a 20 minute budget and 20 s call timeouts."""
import json
import math
import os
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core import s15   # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 tradelab-research", "Accept": "application/json"}
BUDGET_S = 20 * 60
HL = "https://api.hyperliquid.xyz/info"
CALLS = {"ok": 0, "fail": 0, "429": 0}
_lock = threading.Lock()
ERR_SAMPLES = []


def log(m):
    print(m, file=sys.stderr, flush=True)


def jreq(url, body=None, timeout=20, tries=2, headers=None):
    """-> (status, parsed json | None). Per-call timeout; a failure is (status, None), never an empty result."""
    st = 0
    for k in range(tries):
        try:
            data = json.dumps(body).encode() if body is not None else None
            h = {**UA, **(headers or {}), **({"Content-Type": "application/json"} if data else {})}
            with urlopen(Request(url, data=data, headers=h), timeout=timeout) as r:
                out = json.loads(r.read())
            with _lock:
                CALLS["ok"] += 1
            return 200, out
        except Exception as e:  # noqa: BLE001
            st = getattr(e, "code", 0) or 0
            try:
                body = e.read()[:160].decode("utf-8", "replace") if hasattr(e, "read") else ""
            except Exception:  # noqa: BLE001
                body = ""
            with _lock:
                if len(ERR_SAMPLES) < 6 and st:
                    ERR_SAMPLES.append({"status": st, "url": url.split("?")[0][-70:], "q": url.split("?")[-1][:90], "body": body})
                CALLS["fail"] += 1
                if st == 429:
                    CALLS["429"] += 1
            if st in (400, 403, 404, 451):
                return st, None
            time.sleep(1.5 * (k + 1))
    return st, None


class Pacer:
    """Spend at most `per_min` request weight a minute (thread-safe)."""
    def __init__(self, per_min):
        self.rate = per_min / 60.0
        self.next = time.time()
        self.l = threading.Lock()

    def wait(self, weight):
        with self.l:
            now = time.time()
            t = max(self.next, now)
            self.next = t + weight / self.rate
        if t > now:
            time.sleep(t - now)


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def finish(name, t0, summ, rows, problems):
    summ["integrity"] = {"ok": not problems, "problems": problems}
    summ["kline_fail_diag"] = dict(FAIL_DIAG)
    summ["error_samples"] = list(ERR_SAMPLES)
    summ["gate_400_empty_pages"] = EMPTY_PAGES["gate_400"]
    summ["calls"] = dict(CALLS)
    summ["budget_s"] = BUDGET_S
    summ["elapsed_s"] = round(time.time() - t0, 1)
    if problems:
        summ["verdict"] = "VOID (not measured): " + "; ".join(problems)[:300]
    log(f"{name}: {summ['verdict']}")
    return summ, rows


# ====================================================================== S1
def study_s1(_symbols):
    t0 = time.time()
    dl = t0 + BUDGET_S
    pacer = Pacer(s15.HL_PACE_PER_MIN)
    summ, rows, problems = {"line": "s1_hl_ladder"}, [], []

    pacer.wait(20)
    st, meta = jreq(HL, {"type": "metaAndAssetCtxs"})
    if not (isinstance(meta, list) and len(meta) == 2):
        return finish("s1", t0, summ | {"verdict": ""}, rows, [f"metaAndAssetCtxs status {st}"])
    uni = [(u["name"], c) for u, c in zip(meta[0]["universe"], meta[1]) if not u.get("isDelisted")]
    uni.sort(key=lambda x: -(fnum(x[1].get("dayNtlVlm")) or 0))
    coins = uni[20:50]
    summ["coins_ranked_21_50"] = [c for c, _ in coins]
    mids = {c: fnum(ctx.get("midPx") or ctx.get("markPx")) for c, ctx in coins}

    # frame
    st, lb = jreq("https://stats-data.hyperliquid.xyz/Mainnet/leaderboard", timeout=60)
    lrows = lb.get("leaderboardRows") if isinstance(lb, dict) else None
    if not lrows:
        problems.append(f"leaderboard status {st}")
        lrows = []
    lrows.sort(key=lambda r: -(fnum(r.get("accountValue")) or 0))
    frame = [r["ethAddress"] for r in lrows if r.get("ethAddress")][:2000]
    summ["leaderboard_rows"] = len(lrows)
    summ["frame_size"] = len(frame)

    # refresh arithmetic (pre-registered kill)
    refresh_s = s15.refresh_seconds(2000)
    summ["refresh_seconds_2000_at_weight2"] = refresh_s
    summ["max_addresses_per_60s"] = int(s15.HL_PACE_PER_MIN / s15.HL_CLEARINGHOUSE_WEIGHT)

    # books and round trip, 3 snapshots 2 minutes apart (spaced after the sample below to use the waiting time)
    books = {c: [] for c, _ in coins}

    def snap_books():
        for c, _ in coins:
            if time.time() > dl:
                return
            pacer.wait(2)
            st2, b = jreq(HL, {"type": "l2Book", "coin": c})
            lv = b.get("levels") if isinstance(b, dict) else None
            if lv and len(lv) == 2 and lv[0] and lv[1]:
                bids = [(fnum(x["px"]), fnum(x["sz"])) for x in lv[0]]
                asks = [(fnum(x["px"]), fnum(x["sz"])) for x in lv[1]]
                books[c].append({"bids": bids, "asks": asks})

    snap_books()

    # clearinghouseState sample: latency, 429s, liquidationPx presence; ladder snapshot from the first 300 frame addresses
    positions, lat, ch_fail, n_with_liq, n_pos = [], [], 0, 0, 0
    for a in frame[:300]:
        if time.time() > dl:
            break
        pacer.wait(s15.HL_CLEARINGHOUSE_WEIGHT)
        t1 = time.time()
        st2, d = jreq(HL, {"type": "clearinghouseState", "user": a}, timeout=20, tries=1)
        lat.append(time.time() - t1)
        if not isinstance(d, dict):
            ch_fail += 1
            continue
        for ap in d.get("assetPositions") or []:
            p = ap.get("position") or {}
            n_pos += 1
            liq = fnum(p.get("liquidationPx"))
            if liq:
                n_with_liq += 1
            szi = fnum(p.get("szi")) or 0
            positions.append({"coin": p.get("coin"), "side": "long" if szi > 0 else "short", "liq": liq,
                              "notional": abs(fnum(p.get("positionValue")) or 0)})
    summ["sample"] = {"addresses": min(300, len(frame)), "failed": ch_fail, "positions": n_pos, "with_liquidationPx": n_with_liq,
                      "latency_median_s": med(lat), "latency_max_s": max(lat) if lat else None, "http_429": CALLS["429"]}
    if ch_fail > 30 or not n_pos:
        problems.append(f"clearinghouseState sample failed {ch_fail} of {len(lat)}, positions {n_pos}")

    # second and third book snapshots, two minutes apart
    for _ in range(2):
        time.sleep(max(0, min(120, dl - time.time() - 120)))
        snap_books()

    # trades carry users?
    st3, rt = jreq(HL, {"type": "recentTrades", "coin": coins[0][0]})
    summ["recentTrades_has_users"] = bool(isinstance(rt, list) and rt and rt[0].get("users"))

    # candles and sd / round trip per coin
    now = int(time.time() * 1000)
    for c, _ in coins:
        if time.time() > dl:
            problems.append("budget hit before every coin was measured")
            break
        pacer.wait(32)
        st4, cs = jreq(HL, {"type": "candleSnapshot", "req": {"coin": c, "interval": "1h", "startTime": now - 30 * 86400000, "endTime": now}})
        closes = [fnum(x["c"]) for x in cs] if isinstance(cs, list) else []
        sd = s15.sd_step([x for x in closes if x], 1) if closes else None
        walks = []
        for b in books[c]:
            w = s15.book_round_trip(b["bids"], b["asks"], 441.0)
            if w is not None:
                walks.append(w)
        walk = med(walks)
        rt = (2 * 0.00045 + walk) if walk is not None else None
        rows.append({"coin": c, "hourly_sd": sd, "bars": len(closes), "book_walk": walk, "round_trip": rt,
                     "sd_over_rt": (sd / rt) if (sd and rt) else None, "snapshots": len(books[c])})
    ratios = [r["sd_over_rt"] for r in rows if r["sd_over_rt"] is not None]
    summ["coins_measured"] = len(ratios)
    summ["median_sd_over_rt"] = med(ratios)
    summ["median_round_trip"] = med([r["round_trip"] for r in rows])
    if len(ratios) < 20:
        problems.append(f"only {len(ratios)} of 30 coins measured")

    # illustrative ladder snapshot (no verdict use)
    cl = s15.ladder_clusters(positions)
    last_books = {c: b[-1] for c, b in books.items() if b}
    appr = s15.approaches(cl, mids, last_books)
    summ["illustration_300_addresses"] = {"clusters": len(cl), "approach_now": len(appr),
                                          "coins_with_positions": len({p["coin"] for p in positions if p["coin"] in mids})}

    kills = []
    if refresh_s > 60:
        kills.append(f"refresh: 2,000 addresses need {refresh_s:.0f} s at <= {s15.HL_PACE_PER_MIN} weight/min (limit 60 s)")
    if summ["median_sd_over_rt"] is not None and summ["median_sd_over_rt"] < 10:
        kills.append(f"gate: median sd/round trip {summ['median_sd_over_rt']:.2f} < 10")
    summ["kills"] = kills
    summ["pending"] = ["monthly count and coin concentration (pod collector, 7 days)"]
    summ["verdict"] = ("KILL: " + "; ".join(kills)) if kills else "PENDING (survives the Actions-measurable part; pod 7 days)"
    return finish("s1", t0, summ, rows, problems)


# ====================================================================== S2
GT = "https://api.geckoterminal.com/api/v2"
GT_H = {"Accept": "application/json;version=20230302"}


def parse_ts(s):
    try:
        return time.mktime(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
    except Exception:  # noqa: BLE001
        return None


def study_s2(_symbols):
    t0 = time.time()
    dl = t0 + BUDGET_S - 120
    summ, rows, problems = {"line": "s2_dex_trending"}, [], []
    polls, info, failed_polls = [], {}, 0
    POLL = 30
    n_polls = 24
    for k in range(n_polls):
        if time.time() > dl:
            break
        ts = time.time()
        ids, ok = [], True
        for page in (1, 2):
            st, d = jreq(f"{GT}/networks/trending_pools?duration=1h&page={page}", headers=GT_H)
            if not (isinstance(d, dict) and isinstance(d.get("data"), list)):
                ok = False
                break
            for x in d["data"]:
                a = x.get("attributes") or {}
                pid = x.get("id")
                ids.append(pid)
                dex = (((x.get("relationships") or {}).get("dex") or {}).get("data") or {}).get("id")
                info.setdefault(pid, {"name": a.get("name"), "reserve": fnum(a.get("reserve_in_usd")), "dex": dex,
                                      "address": a.get("address"), "created": a.get("pool_created_at")})
        if ok:
            polls.append({"t": ts, "ids": ids})
        else:
            failed_polls += 1
        time.sleep(max(0, POLL - (time.time() - ts)))
    summ["polls_ok"], summ["polls_failed"] = len(polls), failed_polls
    summ["pools_in_list_per_poll_median"] = med([len(p["ids"]) for p in polls])
    if len(polls) < 0.9 * n_polls * 0.9 or len(polls) < 10:
        problems.append(f"only {len(polls)} of {n_polls} polls answered")

    ents = s15.new_entrants(polls)
    summ["entrants"] = len(ents)
    delays = []
    qual, no_reserve = [], 0
    for e in ents:
        i = info.get(e["id"], {})
        fee = s15.pool_fee(i.get("name"), i.get("dex"))
        rt = s15.cp_round_trip(i.get("reserve"), fee)
        if rt is None:
            no_reserve += 1
        row = {"id": e["id"], "name": i.get("name"), "dex": i.get("dex"), "reserve_usd": i.get("reserve"), "fee": fee,
               "round_trip": rt, "delay_s": e["first_t"] - e["prev_t"], "qualifies": rt is not None and rt <= 0.03}
        delays.append(row["delay_s"])
        rows.append(row)
        if row["qualifies"]:
            qual.append((row, e))
    summ["no_reserve"] = no_reserve
    summ["qualifying_entrants"] = len(qual)
    summ["median_first_sight_delay_s"] = med(delays)

    # sells in the 60 minutes before first sight, one call per qualifying entrant (public limit 30 a minute)
    no_exit = measured = 0
    for row, e in qual[:45]:
        if time.time() > t0 + BUDGET_S - 30:
            break
        i = info[e["id"]]
        net = e["id"].split("_")[0]
        st, d = jreq(f"{GT}/networks/{net}/pools/{i['address']}/trades", headers=GT_H, tries=1)
        if st == 429:
            time.sleep(25)
            st, d = jreq(f"{GT}/networks/{net}/pools/{i['address']}/trades", headers=GT_H, tries=1)
        if not (isinstance(d, dict) and isinstance(d.get("data"), list)):
            row["sellers"] = None
            continue
        tr = [{"kind": (x.get("attributes") or {}).get("kind"), "wallet": (x.get("attributes") or {}).get("tx_from_address"),
               "t": parse_ts((x.get("attributes") or {}).get("block_timestamp") or "")} for x in d["data"]]
        tr = [x for x in tr if x["t"]]
        row["sellers"] = s15.distinct_sellers(tr, e["first_t"])
        measured += 1
        if row["sellers"] < 2:
            no_exit += 1
        time.sleep(4.0)
    summ["sell_check"] = {"measured": measured, "fewer_than_2_distinct_sellers": no_exit}
    hours = (polls[-1]["t"] - polls[0]["t"]) / 3600.0 if len(polls) > 1 else 0
    summ["observed_hours"] = hours
    rate = len(qual) / hours * 730 if hours else None
    summ["qualifying_per_month_extrapolated"] = rate
    summ["qualifying_per_month_upper95"] = (s15.poisson_upper95(len(qual)) / hours * 730) if hours else None

    kills = []
    if summ["median_first_sight_delay_s"] is not None and summ["median_first_sight_delay_s"] > 60:
        kills.append(f"delay: median {summ['median_first_sight_delay_s']:.0f} s > 60")
    if measured >= 10 and no_exit / measured > 0.20:
        kills.append(f"exit: {no_exit}/{measured} entrants with < 2 distinct sellers (> 20%)")
    if summ["qualifying_per_month_upper95"] is not None and summ["qualifying_per_month_upper95"] < 100:
        kills.append(f"count: upper 95% bound {summ['qualifying_per_month_upper95']:.0f} a month < 100")
    summ["kills"] = kills
    summ["pending"] = ["3-day window for the monthly count (pod poll)"] + ([] if measured >= 10 else ["exit check (fewer than 10 entrants measured)"])
    summ["verdict"] = ("KILL: " + "; ".join(kills)) if kills else "PENDING (survives the Actions-measurable part; 3-day poll pending)"
    return finish("s2", t0, summ, rows, problems)


# ====================================================================== S3
def gate_contracts():
    st, d = jreq("https://api.gateio.ws/api/v4/futures/usdt/contracts")
    st2, tk = jreq("https://api.gateio.ws/api/v4/futures/usdt/tickers")
    vol = {t.get("contract"): fnum(t.get("volume_24h_quote")) or (fnum(t.get("volume_24h_settle")) or 0) * (fnum(t.get("last")) or 0)
           for t in (tk if isinstance(tk, list) else [])}
    out = []
    for c in d if isinstance(d, list) else []:
        out.append({"venue": "gate", "name": c["name"], "vol": vol.get(c["name"]), "mult": fnum(c.get("quanto_multiplier")) or 1.0,
                    "fee": fnum(c.get("taker_fee_rate"))})
    return out, bool(isinstance(d, list) and d)


def mexc_contracts():
    st, d = jreq("https://contract.mexc.com/api/v1/contract/detail")
    st2, tk = jreq("https://contract.mexc.com/api/v1/contract/ticker")
    vol = {t.get("symbol"): fnum(t.get("amount24")) for t in ((tk or {}).get("data") or []) if isinstance(t, dict)}
    out = []
    for c in (d or {}).get("data") or []:
        out.append({"venue": "mexc", "name": c["symbol"], "vol": vol.get(c["symbol"]), "mult": fnum(c.get("contractSize")) or 1.0,
                    "fee": fnum(c.get("takerFeeRate"))})
    return out, bool((d or {}).get("data"))


PAGE = {"gate": 1900, "mexc": 1900}      # bars per request
FAIL_DIAG = {}
MEXC_PACER = Pacer(5 * 60)               # 5 kline calls a second (documented limit is 20 per 2 s)
EMPTY_PAGES = {"gate_400": 0}


def klines(venue, name, step_s, t0, t1, want_vol=False):
    """{t: close} and {t: volume} for [t0, t1) in pages. A Gate 400 on a page (history older than the venue serves) is an
    empty page, counted; MEXC rate-limit code 510 backs off and retries the same page; any other failure -> (None, None)."""
    close, vol = {}, {}
    t = t0
    iv = {60: ("1m", "Min1"), 300: ("5m", "Min5")}[step_s]
    while t < t1:
        te = min(t + PAGE[venue] * step_s, t1)
        if venue == "gate":
            st, d = jreq(f"https://api.gateio.ws/api/v4/futures/usdt/candlesticks?contract={name}&interval={iv[0]}&from={int(t)}&to={int(te)}", tries=1)
            if d is None and st == 400:
                EMPTY_PAGES["gate_400"] += 1
            elif d is None:
                FAIL_DIAG["gate"] = st
                return None, None
            for k in d if isinstance(d, list) else []:
                close[int(k["t"])] = fnum(k["c"])
                vol[int(k["t"])] = fnum(k.get("v")) or 0
        else:
            x = None
            for attempt in range(6):
                MEXC_PACER.wait(1)
                st, d = jreq(f"https://contract.mexc.com/api/v1/contract/kline/{name}?interval={iv[1]}&start={int(t)}&end={int(te)}", tries=1)
                if isinstance(d, dict) and d.get("success") is False and d.get("code") == 510:
                    time.sleep(3 * (attempt + 1))
                    continue
                break
            if d is None or (isinstance(d, dict) and d.get("success") is False):
                FAIL_DIAG["mexc"] = {"status": st, "body": str(d)[:120]}
                return None, None
            x = d.get("data") if isinstance(d, dict) else None
            if x and x.get("time"):
                vv = x.get("vol") or [0] * len(x["time"])
                for tt, c, v in zip(x["time"], x["close"], vv):
                    close[int(tt)] = fnum(c)
                    vol[int(tt)] = fnum(v) or 0
        t = te
        time.sleep(0.05)
    return close, vol


def book(venue, name):
    if venue == "gate":
        st, d = jreq(f"https://api.gateio.ws/api/v4/futures/usdt/order_book?contract={name}&limit=20")
        if not isinstance(d, dict):
            return None
        return ([(fnum(x["p"]), fnum(x["s"])) for x in d.get("bids", [])], [(fnum(x["p"]), fnum(x["s"])) for x in d.get("asks", [])])
    st, d = jreq(f"https://contract.mexc.com/api/v1/contract/depth/{name}?limit=20")
    x = (d or {}).get("data") if isinstance(d, dict) else None
    if not x:
        return None
    return ([(fnum(a[0]), fnum(a[1])) for a in x.get("bids", [])], [(fnum(a[0]), fnum(a[1])) for a in x.get("asks", [])])


def yahoo_bars(sym):
    from core import data
    try:
        d = data.chart(sym, "60d", "5m")
    except Exception as e:  # noqa: BLE001
        return None, None, repr(e)[:100]
    return {int(b["t"]): b["c"] for b in d["bars"]}, d["meta"], None


def study_s3(_symbols):
    t0 = time.time()
    dl = t0 + BUDGET_S
    summ, rows, problems = {"line": "s3_anchor_perps"}, [], []
    g, ok1 = gate_contracts()
    m, ok2 = mexc_contracts()
    if not (ok1 and ok2):
        problems.append(f"contract lists: gate {ok1} mexc {ok2}")
    uni = s15.pick_s3_universe(g + m, 40)
    cmap = {(c["venue"], c["name"]): c for c in g + m}
    summ["universe"] = [{"venue": u["venue"], "name": u["name"], "yahoo": u["yahoo"], "cls": u["cls"], "vol": u["vol"]} for u in uni]
    summ["perps_matching_table"] = sum(1 for c in g + m if s15.norm_base(c["name"]) in s15.S3_UNDERLYING)
    summ["universe_size"] = len(uni)
    if len(uni) < 15:
        problems.append(f"universe only {len(uni)} symbols")

    # is the US regular session open?
    _, meta, err = yahoo_bars("AAPL")
    now = time.time()
    reg = ((meta or {}).get("currentTradingPeriod") or {}).get("regular") or {}
    session_open = bool(reg and reg.get("start", 0) <= now <= reg.get("end", 0))
    summ["us_session_open"] = session_open
    summ["run_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

    def one(u):
        if time.time() > dl:
            return {"base": u["base"], "error": "budget"}
        row = {"base": u["base"], "venue": u["venue"], "name": u["name"], "cls": u["cls"], "yahoo": u["yahoo"], "fee": u.get("fee")}
        ub, _, err = yahoo_bars(u["yahoo"])
        time.sleep(1.0)
        if not ub:
            row["error"] = f"yahoo {err}"
            return row
        ucl = sorted(ub)
        row["under_bars"] = len(ub)
        row["hourly_sd"] = s15.sd_step([ub[t] for t in ucl], 12)
        t1 = (ucl[-1] // 300 + 1) * 300
        pc, _ = klines(u["venue"], u["name"], 300, max(ucl[0], t1 - 60 * 86400), t1)
        if not pc:
            row["error"] = "no perp bars"
            return row
        pc = {t: v for t, v in pc.items() if v}
        gs = s15.gap_series(pc, ub)
        row["common_bars"] = len(gs)
        if len(gs) < 300:
            row["error"] = "fewer than 300 common bars"
            return row
        row["first_t"], row["last_t"] = gs[0][0], gs[-1][0]
        row["median_gap"] = med([v for _, v in gs])
        row["gaps"] = gs
        # book snapshots (valid for stock/index only in session)
        measure = session_open or u["cls"] not in s15.SESSION_CLASSES
        row["book_valid"] = measure
        if measure and u.get("fee") is not None:
            walks = []
            for k in range(6):
                if time.time() > dl:
                    break
                bk = book(u["venue"], u["name"])
                if bk:
                    w = s15.book_round_trip(bk[0], bk[1], 150.0, u["mult"])
                    if w is not None:
                        walks.append(w)
                if k < 5:
                    time.sleep(180 if session_open else 5)
            row["spread_walk"] = med(walks)
            row["snapshots"] = len(walks)
            if walks:
                row["round_trip"] = 2 * u["fee"] + row["spread_walk"]
        return row

    # symbols are processed in parallel; book snapshots wait 3 minutes between samples inside each worker
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(one, uni))
    errs = [r for r in res if r.get("error")]
    summ["errors"] = [{"base": r["base"], "error": r["error"]} for r in errs]
    good = [r for r in res if not r.get("error")]
    if len(good) < 15:
        problems.append(f"only {len(good)} symbols with bars")

    # (a) sd / round trip
    ratios = [r["hourly_sd"] / r["round_trip"] for r in good if r.get("hourly_sd") and r.get("round_trip")]
    summ["symbols_with_round_trip"] = len(ratios)
    summ["median_round_trip"] = med([r.get("round_trip") for r in good])
    summ["median_sd_over_rt"] = med(ratios)
    summ["round_trip_by_class"] = {c: med([r.get("round_trip") for r in good if r["cls"] == c]) for c in ("stock", "index", "fx", "commodity")}
    # (b) episodes, (c) same-sign days
    ep_by, total_ep, months = {}, 0, []
    days = same = 0
    for r in good:
        rt = r.get("round_trip")
        if rt is None:
            continue
        thr = rt + 0.0037
        eps = s15.episodes(r["gaps"], thr, 2, 300)
        sc = s15.month_scale(r["first_t"], r["last_t"])
        n = len(eps) * sc
        ep_by[r["base"]] = n
        total_ep += n
        d_, s_ = s15.same_sign_days(r["gaps"])
        days += d_
        same += s_
        r["episodes"], r["episodes_per_month"], r["threshold"] = len(eps), n, thr
    summ["episodes_per_month"] = total_ep
    summ["top4_share"] = s15.top_share(ep_by, 4)
    summ["symbol_days"] = days
    summ["same_sign_days"] = same
    summ["same_sign_share"] = (same / days) if days else None
    for r in res:
        r.pop("gaps", None)
        rows.append(r)

    complete = session_open and len(ratios) >= 0.8 * len(good) and len(good) >= 15
    kills, pending = [], []
    if not complete:
        pending.append("verdict needs the in-session run (T2) with round trips for the stock and index symbols")
    else:
        if summ["median_sd_over_rt"] is not None and summ["median_sd_over_rt"] < 10:
            kills.append(f"(a) median sd/round trip {summ['median_sd_over_rt']:.2f} < 10")
        if total_ep < 100:
            kills.append(f"(b) {total_ep:.0f} episodes a month < 100")
        if total_ep and summ["top4_share"] > 0.5:
            kills.append(f"(b) top 4 symbols hold {summ['top4_share']:.0%} > 50%")
        if days and same / days > 0.5:
            kills.append(f"(c) {same}/{days} symbol-days same sign > half")
    summ["kills"], summ["pending"] = kills, pending
    summ["verdict"] = ("KILL: " + "; ".join(kills)) if kills else ("PENDING: " + "; ".join(pending) if pending else "SURVIVES stage 0 counts (forward protocol next)")
    return finish("s3", t0, summ, rows, problems)


# ====================================================================== S4
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"


def cents(m, *keys):
    for k in keys:
        v = fnum(m.get(k))
        if v is not None:
            return v if k.endswith("_dollars") else v / 100.0
    return None


def iso(s):
    return parse_ts(s) if s else None


def snapshot_s4(dl):
    now = time.time()
    km, cursor, pages = [], None, 0
    while pages < 15 and time.time() < dl:
        url = (f"{KALSHI}/markets?status=open&limit=1000&mve_filter=exclude&min_close_ts={int(now + 1800)}"
               f"&max_close_ts={int(now + 48 * 3600)}" + (f"&cursor={cursor}" if cursor else ""))
        st, d = jreq(url)
        if not isinstance(d, dict):
            return None, None, f"kalshi status {st}"
        km += [m for m in d.get("markets", []) if not m.get("mve_collection_ticker")]
        cursor = d.get("cursor")
        pages += 1
        if not cursor:
            break
    pm, off = [], 0
    from datetime import datetime, timezone
    lo = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hi = datetime.fromtimestamp(now + 48 * 3600, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    while off < 8000 and time.time() < dl:
        st, d = jreq(f"{GAMMA}/markets?active=true&closed=false&limit=100&offset={off}&end_date_min={lo}&end_date_max={hi}")
        if not isinstance(d, list):
            return None, None, f"gamma status {st}"
        pm += d
        if len(d) < 100:
            break
        off += 100
        time.sleep(0.2)
    return km, pm, None


def study_s4(_symbols):
    t0 = time.time()
    dl = t0 + BUDGET_S - 60
    summ, rows, problems = {"line": "s4_kalshi_poly"}, [], []
    snaps = []
    for k in range(4):
        if time.time() > dl:
            break
        km, pm, err = snapshot_s4(dl)
        if err:
            problems.append(err)
            break
        snaps.append((time.time(), km, pm))
        if k < 3:
            time.sleep(300)
    if problems:
        return finish("s4", t0, summ | {"verdict": ""}, rows, problems)
    summ["snapshots"] = len(snaps)
    _, km, pm = snaps[0]
    summ["kalshi_markets_in_window"], summ["polymarket_markets_in_window"] = len(km), len(pm)
    kf, pf = [], []
    for m in km:
        f = s15.features(m.get("title") or m.get("yes_sub_title") or "", fnum(m.get("floor_strike")) if m.get("strike_type", "").startswith("greater") else fnum(m.get("cap_strike")) if m.get("strike_type", "").startswith("less") else None, m.get("strike_type"))
        if f:
            kf.append((m, f, iso(m.get("close_time"))))
    for m in pm:
        f = s15.features(m.get("question") or "")
        if f and f["level"] is not None:
            pf.append((m, f, iso(m.get("endDate"))))
    summ["kalshi_classified"], summ["polymarket_classified"] = len(kf), len(pf)
    summ["classified_by_cat"] = {"kalshi": count_by([f["cat"] for _, f, _ in kf]), "polymarket": count_by([f["cat"] for _, f, _ in pf])}
    summ["unclassified_titles"] = {"kalshi": [m.get("title") for m in km[:400:27]][:15], "polymarket": [m.get("question") for m in pm[:400:27]][:15]}
    pairs = []
    for km_, kfe, kc in kf:
        for pm_, pfe, pc in pf:
            if kc and pc and s15.pair_match(kfe, pfe, kc, pc):
                pairs.append((km_, pm_, kfe))
    summ["matched_pairs"] = len(pairs)
    # shape diagnostics so a field-name miss is visible, not silent
    summ["shape"] = {"kalshi_keys": sorted(km[0].keys())[:60] if km else [], "poly_keys": sorted(pm[0].keys())[:60] if pm else []}

    mism = unk = 0
    nofee = 0
    alloc_pairs = []
    for km_, pm_, f in pairs[:80]:
        ks = s15.sources_of((km_.get("rules_primary") or "") + " " + (km_.get("rules_secondary") or ""))
        ps = s15.sources_of((pm_.get("description") or "") + " " + (pm_.get("resolutionSource") or ""))
        bad = s15.source_mismatch(ks, ps)
        mism += bad
        unk += (not ks or not ps)
        row = {"kalshi": km_.get("ticker"), "poly": pm_.get("slug"), "cat": f["cat"], "k_sources": sorted(ks), "p_sources": sorted(ps),
               "mismatch": bad}
        ya = cents(km_, "yes_ask_dollars", "yes_ask")
        na = cents(km_, "no_ask_dollars", "no_ask")
        try:
            toks = json.loads(pm_.get("clobTokenIds") or "[]")
        except ValueError:
            toks = []
        books = []
        for tk in toks[:2]:
            st, b = jreq(f"{CLOB}/book?token_id={tk}")
            asks = sorted((fnum(x["price"]), fnum(x["size"])) for x in (b or {}).get("asks", [])) if isinstance(b, dict) else []
            books.append(asks[0] if asks else None)
        fee_known = pm_.get("feesEnabled") in (False, None) or pm_.get("feeSchedule")
        row["poly_fee_field"] = {"feesEnabled": pm_.get("feesEnabled"), "has_schedule": bool(pm_.get("feeSchedule"))}
        if pm_.get("feesEnabled"):
            nofee += 1
            row["excluded"] = "polymarket fee enabled: schedule not read"
        elif ya is not None and na is not None and len(books) == 2 and books[0] and books[1]:
            c = 20.0
            best = None
            for ka, pp in ((ya, books[1][0]), (na, books[0][0])):
                if ka is None or pp is None:
                    continue
                n = c / (ka + pp)
                net = s15.lock_net(ka, pp, s15.kalshi_fee(n, ka), 0.0, n)
                if best is None or net > best[0]:
                    best = (net, n * (ka + pp))
            if best:
                row["lock_net_usd_20"] = best[0]
                days = max(((iso(km_.get("close_time")) or time.time()) - time.time()) / 86400.0, 0.25)
                alloc_pairs.append({"net_usd": best[0], "cost_usd": best[1], "days": days})
        rows.append(row)
        time.sleep(0.3)
    nm = len(pairs[:80])
    summ["mismatch_pairs"], summ["unknown_source_pairs"], summ["fee_excluded"] = mism, unk, nofee
    summ["mismatch_share"] = (mism / nm) if nm else None
    summ["best_allocation_daily_yield_one_instant"] = s15.allocate(alloc_pairs) if alloc_pairs else None
    summ["pairs_with_locked_return"] = len(alloc_pairs)
    kills, pending = [], ["yield vs 3.73% and 0.5% a day, pairs a day: 48 hourly snapshots (pod or scheduled run)"]
    if nm >= 10 and mism / nm > 0.20:
        kills.append(f"resolution sources: {mism}/{nm} matched pairs differ (> 20%)")
    if nm < 10:
        pending.append(f"only {nm} matched pairs in one window (resolution-source kill needs >= 10); recall limited by the matcher")
    summ["kills"], summ["pending"] = kills, pending
    summ["verdict"] = ("KILL: " + "; ".join(kills)) if kills else "PENDING (survives the one-snapshot kill; hourly snapshots pending)"
    return finish("s4", t0, summ, rows, problems)


def count_by(xs):
    out = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out


# ====================================================================== S5
def study_s5(_symbols):
    t0 = time.time()
    dl = t0 + BUDGET_S
    summ, rows, problems = {"line": "s5_stale_quote"}, [], []
    g, ok1 = gate_contracts()
    m, ok2 = mexc_contracts()
    if not (ok1 and ok2):
        problems.append(f"contract lists: gate {ok1} mexc {ok2}")
        return finish("s5", t0, summ | {"verdict": ""}, rows, problems)
    gv = {s15.norm_base(c["name"]): c for c in g if c.get("vol") is not None}
    mv = {s15.norm_base(c["name"]): c for c in m if c.get("vol") is not None}
    common = [(b, min(gv[b]["vol"], mv[b]["vol"])) for b in gv if b in mv]
    common.sort(key=lambda x: -x[1])
    coins = [b for b, _ in common[20:60]]
    summ["common_coins"], summ["coins_ranked_21_60"] = len(common), coins
    if len(coins) < 30:
        problems.append(f"only {len(coins)} common coins")
    end = int(time.time() // 60 * 60)
    start = end - 30 * 86400

    def one(b):
        if time.time() > dl:
            return {"coin": b, "error": "budget"}
        a, va = klines("gate", gv[b]["name"], 60, start, end)
        c, vc = klines("mexc", mv[b]["name"], 60, start, end)
        if not a or not c:
            return {"coin": b, "error": "no bars"}
        mg = s15.median_abs_log_gap(a, c)
        row = {"coin": b, "gate_bars": len(a), "mexc_bars": len(c), "median_abs_log_gap": mg}
        if mg is None or mg > 0.01:
            row["excluded"] = "standing mismatch (median gap > 1%)" if mg is not None else "no common bars"
            return row
        ev = s15.bar_gap_events(a, c, va, vc)
        row["events"] = len(ev)
        row["event_times"] = [e[0] for e in ev]
        return row

    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(one, coins))
    errs = [r for r in res if r.get("error")]
    used = [r for r in res if "events" in r]
    if len(errs) > 6:
        problems.append(f"{len(errs)} coins without bars or budget")
    by = {r["coin"]: r["events"] for r in used}
    total = sum(by.values())
    cover = med([min(r["gate_bars"], r["mexc_bars"]) / 43200.0 for r in used])
    scale = 1.0 / cover if cover else None
    summ["coins_used"], summ["coins_excluded_mismatch"] = len(used), sum(1 for r in res if r.get("excluded"))
    summ["median_bar_coverage_of_30d"] = cover
    summ["events_total_in_window"] = total
    summ["events_per_month"] = total * scale if scale else None
    summ["top4_share"] = s15.top_share(by, 4)
    summ["events_by_coin"] = by
    if len(used) < 20:
        problems.append(f"only {len(used)} coins usable")
    if cover is None or cover < 0.15:
        problems.append(f"bar coverage {cover}: fewer than 5 days of common 1-minute bars (venue history limit); count not scalable")
    rows = res
    # unconditional context only
    kills = []
    epm = summ["events_per_month"]
    if epm is not None and epm < 60:
        kills.append(f"(a) {epm:.1f} events a month < 60")
    if total and summ["top4_share"] > 0.5:
        kills.append(f"(a) top 4 coins hold {summ['top4_share']:.0%} > 50%")
    summ["kills"] = kills
    summ["pending"] = ["seconds arm (b): pod sockets, 7 days", "gate line (c): conditional on a jump, not a counts quantity"]
    summ["verdict"] = ("KILL bar arm only: " + "; ".join(kills)) if kills else "bar arm SURVIVES counts; seconds arm PENDING"
    return finish("s5", t0, summ, rows, problems)


STUDIES = {"s1_hl_ladder": study_s1, "s2_dex_trending": study_s2, "s3_anchor_perps": study_s3,
           "s4_kalshi_poly": study_s4, "s5_stale_quote": study_s5}
