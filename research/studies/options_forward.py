"""Weekday runner for protocol_llm_options_forward.md (GitHub Actions only, never the owner's computer).

    python research/studies/options_forward.py STATE.json SUMMARY.json

STATE.json is restored from / pushed to the branch data/options-forward by the workflow. Simulated money; no orders.
"""
import http.cookiejar
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from core import ai_news, data, news_backtest as nb, options_forward as of, sequential, studies as st   # noqa: E402

UA = "Mozilla/5.0 (X11; Linux x86_64)"


def log(*a):
    print(*a, file=sys.stderr, flush=True)


class Yahoo:
    """Option chains through Yahoo's v7 endpoint (needs a session cookie and crumb)."""

    def __init__(self):
        from urllib.parse import quote
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.op.addheaders = [("User-Agent", UA)]
        try:
            self.op.open("https://fc.yahoo.com", timeout=20).read()
        except Exception:
            pass                                    # answers 404 but sets the cookie
        crumb = self.op.open("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=20).read().decode().strip()
        if not crumb or "<" in crumb or len(crumb) > 64:
            raise RuntimeError(f"bad crumb {crumb[:40]!r}")
        self.crumb = quote(crumb, safe="")

    def chain(self, symbol, expiry=None):
        url = f"https://query1.finance.yahoo.com/v7/finance/options/{symbol}?crumb={self.crumb}"
        if expiry:
            url += f"&date={int(expiry)}"
        res = json.loads(self.op.open(url, timeout=20).read())["optionChain"]["result"][0]
        opts = res.get("options") or [{}]
        return {"expiries": res.get("expirationDates", []), "spot": (res.get("quote") or {}).get("regularMarketPrice"),
                "calls": opts[0].get("calls", []), "puts": opts[0].get("puts", []), "fetched_ts": int(time.time())}


def sec_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": nb.SEC_UA, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", "replace")
    time.sleep(0.15)
    return body


def feed_8k(since_ts, gaps, now):
    """Every 8-K in SEC's latest-filings feed newer than since_ts (pages of 100, newest first). Items and acceptance
    time are confirmed later from the issuer's submissions record, not taken from the feed."""
    out, reached = [], False
    for start in range(0, 2000, 100):
        page = of.parse_current_atom(sec_get(
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include"
            f"&start={start}&count=100&output=atom"))
        if not page:
            break
        out += [f for f in page if f["updated"] > since_ts - 6 * 3600]   # feed time is not acceptance time: wide net
        if min(f["updated"] for f in page) <= since_ts - 6 * 3600:
            reached = True
            break
    if not reached:
        gaps.append({"ts": now, "what": "feed", "error": "did not reach the previous cutoff; coverage may be incomplete"})
    uniq = {}
    for f in out:
        uniq.setdefault(f["accession"], f)
    return list(uniq.values())


def confirmed_202(feed, since_ts, until_ts, gaps, now):
    """Confirm form, items and acceptance time per accession from the issuer's submissions record; keep 8-K with
    item 2.02 accepted in (since_ts, until_ts]."""
    by_cik = {}
    for f in feed:
        by_cik.setdefault(f["cik"], set()).add(f["accession"])
    day = time.strftime("%Y-%m-%d", time.gmtime(since_ts - 3 * 86400))
    out = []
    for cik, accs in by_cik.items():
        try:
            for f in nb.sec_filings(cik, forms=("8-K",), since=day):
                if f["accession"] in accs and "2.02" in f["items"] and since_ts < f["ts"] <= until_ts:
                    out.append({**f, "cik": cik})
        except Exception as e:
            gaps.append({"ts": now, "what": f"submissions {cik}", "error": repr(e)[:200]})
    return out


def press_release(cik, f):
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{f['accession'].replace('-', '')}/"
    names = [x["name"] for x in json.loads(sec_get(base + "index.json"))["directory"]["item"]]
    return st.html_text(sec_get(base + st.pick_exhibit(names, f["doc"])))


def quote_of(chain, contract_symbol):
    for x in chain["calls"] + chain["puts"]:
        if x.get("contractSymbol") == contract_symbol:
            return x
    return None


def settle_close(symbol, expiry_ts):
    """Underlying close on the expiry date (last completed session on or before it)."""
    day = time.strftime("%Y-%m-%d", time.gmtime(expiry_ts))
    bars = [b for b in data.chart(symbol, "3mo", "1d")["bars"] if time.strftime("%Y-%m-%d", time.gmtime(b["t"])) <= day]
    return bars[-1]["c"] if bars else None


def run(state):
    now = int(time.time())
    try:
        spy = data.chart("SPY", "3mo", "1d")["bars"]
    except Exception as e:
        state["gaps"].append({"ts": now, "what": "SPY sessions", "error": repr(e)[:200]})
        return state                                # missing data is not a holiday: do not advance the cursor
    sessions = [time.strftime("%Y-%m-%d", time.gmtime(b["t"])) for b in spy]
    today = time.strftime("%Y-%m-%d", time.gmtime(now))
    if not sessions or sessions[-1] != today:
        log("no US session today; nothing to do")
        return state
    try:
        y = Yahoo()
    except Exception as e:
        state["gaps"].append({"ts": now, "what": "yahoo auth", "error": repr(e)[:200]})
        return state                                # retry at the next run; nothing is priced from a failed source
    # exits (and settlement of anything already expired)
    still = []
    for t in state["open"]:
        due = of.sessions_after(sessions, t["entry_date"]) >= of.HOLD_SESSIONS
        expired = any(t[leg] and today > time.strftime("%Y-%m-%d", time.gmtime(t[leg]["expiry"]))
                      for leg in ("model", "control"))
        if not (due or expired):
            still.append(t)
            continue
        ok = True
        for leg in ("model", "control"):
            c = t[leg]
            if c is None or c.get("exit_bid") is not None:
                continue
            try:
                if today > time.strftime("%Y-%m-%d", time.gmtime(c["expiry"])):
                    spot = settle_close(t["symbol"], c["expiry"])
                    if spot is None:
                        raise RuntimeError("no settlement close")
                    c["exit_bid"], c["exit_kind"] = of.intrinsic(c["direction"], c["strike"], spot), "expiry"
                else:
                    q = quote_of(y.chain(t["symbol"], c["expiry"]), c["contract"])
                    c["exit_bid"], c["exit_kind"] = float((q or {}).get("bid") or 0.0), "bid"
                c["exit_ts"] = now
                c["exit_session"] = of.sessions_after(sessions, t["entry_date"])
            except Exception as e:                  # source failure: not a zero; retried at the next run
                state["gaps"].append({"ts": now, "what": f"exit {t['symbol']} {leg}", "error": repr(e)[:200]})
                ok = False
        if ok or (t["model"] and t["model"].get("exit_bid") is not None and
                  (t["control"] is None or t["control"].get("exit_bid") is not None)):
            t["closed_ts"] = now
            t["late"] = (t["model"] or {}).get("exit_session", 0) > of.HOLD_SESSIONS
            state["closed"].append(t)
        else:
            still.append(t)
    state["open"] = still
    # entries: 2.02 filings accepted after the previous run and before this one
    lock_ts = 1795478400                            # 2026-11-24 00:00 UTC, the protocol lock date
    since = max(state.get("last_run_ts") or now - 86400, lock_ts)
    tick = {}
    for sym, cik in nb.sec_company_tickers().items():
        tick.setdefault(cik, sym)
    feed = [f for f in feed_8k(since, state["gaps"], now) if f["cik"] in tick]
    for f in confirmed_202(feed, since, now, state["gaps"], now):
        sym = tick[f["cik"]]
        if f["accession"] in state["calls"]:
            continue
        rec = {"symbol": sym, "accession": f["accession"], "accepted": f["accepted"], "accepted_ts": f["ts"]}
        try:
            bars = data.chart(sym, "3mo", "1d")["bars"]
            completed = [b for b in bars if time.strftime("%Y-%m-%d", time.gmtime(b["t"])) < today]
            mdv = of.median_dollar_volume(completed)
            if mdv is None or mdv < of.LIQ_MIN_USD:
                rec["skipped"] = f"liquidity {mdv}"
                state["calls"][f["accession"]] = rec
                continue
            ch = y.chain(sym)                       # snapshot before the model call, so the quote time is the run time
            exp = of.choose_expiry(ch["expiries"], now)
            ch = y.chain(sym, exp) if exp else None
            text = st.html_text(press_release(f["cik"], f), 12000)
            # v2-single reader (protocol addendum): run-up to the last completed close, and the move from that close
            # to the quote a trader would act on now, plus the previous earnings release
            last_close = completed[-1]["c"] if completed else None
            runup = round((last_close / completed[-6]["c"] - 1) * 100, 2) if len(completed) >= 6 else None
            gap = round((ch["spot"] / last_close - 1) * 100, 2) if ch and ch.get("spot") and last_close else None
            back = time.strftime("%Y-%m-%d", time.gmtime(f["ts"] - 200 * 86400))
            prevs = [p for p in nb.sec_filings(f["cik"], forms=("8-K",), since=back) if "2.02" in p["items"] and p["ts"] < f["ts"]]
            prev_text = st.html_text(press_release(f["cik"], max(prevs, key=lambda p: p["ts"])), 6000) if prevs else ""
            reply, model = ai_news.chat(st.NEWS_V2_SYSTEM, st.v2_message(sym, f["accepted"], runup, gap, prev_text, text),
                                        timeout=180, temperature=0.0)
            if not reply:
                state["gaps"].append({"ts": now, "what": f"model {sym}", "error": model})
                continue
            rec.update(model=model, **st.parse_direction(reply))
            state["calls"][f["accession"]] = rec
            if rec["direction"] == "skip":
                continue
            if not ch or not ch["spot"]:
                rec["skipped"] = "no chain"
                continue
            legs = {}
            for d in ("long", "short"):
                c = of.pick_contract(ch, ch["spot"], d)
                legs[d] = None if not c or not of.valid_ask(c.get("ask")) else {
                    "direction": d, "contract": c["contractSymbol"], "strike": c["strike"], "expiry": exp,
                    "entry_ask": float(c["ask"]), "entry_bid": c.get("bid"), "entry_ts": ch["fetched_ts"]}
            rec["legs_seen"] = {d: (legs[d] or {}).get("contract") for d in legs}
            if legs[rec["direction"]] is None:
                rec["skipped"] = "no valid ask"
                continue
            ctrl_dir = of.random_direction(sym, f["accession"])
            state["open"].append({"symbol": sym, "accession": f["accession"], "ts": f["ts"], "entry_date": today,
                                  "spot": ch["spot"], "model": legs[rec["direction"]], "control": legs[ctrl_dir],
                                  "control_direction": ctrl_dir, "both_sides": legs})
            log(f"  open {sym} {rec['direction']} {legs[rec['direction']]['contract']} ask {legs[rec['direction']]['entry_ask']}")
        except Exception as e:
            state["gaps"].append({"ts": now, "what": f"entry {sym} {f['accession']}", "error": repr(e)[:200]})
    state["last_run_ts"] = now
    return state


def summary(state):
    closed, daily = [], []
    for t in state["closed"]:
        m, c = t["model"], t["control"]
        if m is None or m.get("exit_bid") is None:
            continue
        closed.append({"symbol": t["symbol"], "ts": t["ts"],
                       "ret": of.trade_return(m["entry_ask"], m["exit_bid"]),
                       "ctrl_ret": of.trade_return(c["entry_ask"], c["exit_bid"])
                       if c and c.get("exit_bid") is not None else None,
                       "ret_haircut": of.trade_return(m["entry_ask"], m["exit_bid"], haircut=0.10)})
        if m.get("entry_ts", 0) >= sequential.FORWARD_START_TS:
            daily.append({"ts": t.get("closed_ts"), "model": closed[-1]["ret"], "control": closed[-1]["ctrl_ret"]})
    acct_trades = [{"entry_ts": t["model"]["entry_ts"], "exit_ts": t["model"]["exit_ts"],
                    "entry_ask": t["model"]["entry_ask"], "exit_bid": t["model"]["exit_bid"]}
                   for t in state["closed"] if t["model"] and t["model"].get("exit_bid") is not None]
    whole = of.simulate_account(acct_trades)
    frac = of.simulate_account(acct_trades, whole_contracts=False)
    # Use the day the record became complete, so late exits cannot revise an earlier unit.
    evidence = sequential.paired_daily(daily, start=sequential.FORWARD_START_TS, before=int(time.time()) // 86400 * 86400)
    return {"verdict": of.verdict(closed), "open": len(state["open"]), "closed": len(state["closed"]),
            "late_exits": sum(1 for t in state["closed"] if t.get("late")),
            "calls": len(state["calls"]), "gaps": len(state["gaps"]),
            "account_whole_contracts": {k: v for k, v in whole.items() if k != "curve"},
            "account_fractional": {k: v for k, v in frac.items() if k != "curve"},
            "sequential": evidence, "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def main():
    path, out = sys.argv[1], sys.argv[2]
    state = json.load(open(path)) if os.path.exists(path) else {"calls": {}, "open": [], "closed": [], "gaps": []}
    state = run(state)
    with open(path, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    summ = summary(state)
    with open(out, "w") as f:
        json.dump(summ, f, ensure_ascii=False, indent=1)
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
