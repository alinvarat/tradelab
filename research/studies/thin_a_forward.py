"""One hourly poll of the Thin A forward collectors (protocol_thin_a_forward.md), run on GitHub Actions (job `thin_a` in
research.yml, dispatched hourly by a user timer on the owner's machine). State and ledgers live on the data branch
`data/thin-a-forward`.

    python research/studies/thin_a_forward.py <state_dir>

<state_dir>/state.json holds seen pairs, watch lists and last candidates; <state_dir>/ledger/*.jsonl are append-only
(f1_listings, f2_gaps, f3_announcements). No trading keys; only public market-data endpoints."""
import json
import os
import sys
import time
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import screens as sc   # noqa: E402
from core import thin_a as ta    # noqa: E402
from research.studies.thin_a import http   # noqa: E402

_LEV = ("3L", "3S", "5L", "5S", "UP", "DOWN", "BULL", "BEAR")


def books():
    """{venue: {base: {'bid','ask','bid_sz','ask_sz','vol'}}} for USDT pairs; a failed venue is an empty dict."""
    out = {"kucoin": {}, "gate": {}, "mexc": {}, "bitget": {}, "binance": {}}

    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return 0.0
    st, d, _ = http("https://api.kucoin.com/api/v1/market/allTickers")
    for x in ((d.get("data") or {}).get("ticker") or []) if isinstance(d, dict) else []:
        if x.get("symbol", "").endswith("-USDT"):
            out["kucoin"][x["symbol"][:-5]] = {"bid": num(x.get("buy")), "ask": num(x.get("sell")), "bid_sz": num(x.get("bestBidSize")),
                                               "ask_sz": num(x.get("bestAskSize")), "vol": num(x.get("volValue"))}
    st, d, _ = http("https://api.gateio.ws/api/v4/spot/tickers")
    for x in d if isinstance(d, list) else []:
        if x.get("currency_pair", "").endswith("_USDT"):
            out["gate"][x["currency_pair"][:-5]] = {"bid": num(x.get("highest_bid")), "ask": num(x.get("lowest_ask")),
                                                    "bid_sz": 0.0, "ask_sz": 0.0, "vol": num(x.get("quote_volume"))}
    st, d, _ = http("https://api.mexc.com/api/v3/ticker/bookTicker")
    for x in d if isinstance(d, list) else []:
        if x.get("symbol", "").endswith("USDT"):
            out["mexc"][x["symbol"][:-4]] = {"bid": num(x.get("bidPrice")), "ask": num(x.get("askPrice")), "bid_sz": num(x.get("bidQty")),
                                             "ask_sz": num(x.get("askQty")), "vol": 0.0}
    st, d, _ = http("https://api.bitget.com/api/v2/spot/market/tickers")
    for x in (d.get("data") or []) if isinstance(d, dict) else []:
        if x.get("symbol", "").endswith("USDT"):
            out["bitget"][x["symbol"][:-4]] = {"bid": num(x.get("bidPr")), "ask": num(x.get("askPr")), "bid_sz": num(x.get("bidSz")),
                                               "ask_sz": num(x.get("askSz")), "vol": num(x.get("usdtVolume"))}
    st, d, _ = http("https://data-api.binance.vision/api/v3/ticker/bookTicker")
    for x in d if isinstance(d, list) else []:
        if x.get("symbol", "").endswith("USDT"):
            out["binance"][x["symbol"][:-4]] = {"bid": num(x.get("bidPrice")), "ask": num(x.get("askPrice")), "bid_sz": num(x.get("bidQty")),
                                                "ask_sz": num(x.get("askQty")), "vol": 0.0}
    for v in out:
        out[v] = {b: q for b, q in out[v].items() if q["bid"] > 0 and q["ask"] > 0 and not b.endswith(_LEV)}
    return out


def coin_status():
    """{venue: {base: {'dep': bool, 'wd': bool}}}: public deposit/withdraw flags (MEXC has no public endpoint)."""
    out = {"kucoin": {}, "gate": {}, "bitget": {}}
    _, d, _ = http("https://api.kucoin.com/api/v3/currencies", timeout=40)
    for x in (d.get("data") or []) if isinstance(d, dict) else []:
        ch = x.get("chains") or []
        out["kucoin"][x.get("currency")] = {"dep": any(c.get("isDepositEnabled") for c in ch), "wd": any(c.get("isWithdrawEnabled") for c in ch)} if ch else {"dep": bool(x.get("isDepositEnabled")), "wd": bool(x.get("isWithdrawEnabled"))}
    _, d, _ = http("https://api.gateio.ws/api/v4/spot/currencies", timeout=40)
    for x in d if isinstance(d, list) else []:
        out["gate"][x.get("currency")] = {"dep": not x.get("deposit_disabled"), "wd": not x.get("withdraw_disabled")}
    _, d, _ = http("https://api.bitget.com/api/v2/spot/public/coins", timeout=40)
    for x in (d.get("data") or []) if isinstance(d, dict) else []:
        ch = x.get("chains") or []
        out["bitget"][x.get("coin")] = {"dep": any(str(c.get("rechargeable")).lower() == "true" for c in ch), "wd": any(str(c.get("withdrawable")).lower() == "true" for c in ch)}
    return out


def announcements():
    """[(venue, ann_id, title, ts_s, [symbols])] from KuCoin and Bitget listing announcements."""
    out = []
    for page in (1, 2, 3):
        _, d, _ = http(f"https://api.kucoin.com/api/v3/announcements?annType=new-listings&lang=en_US&pageSize=50&currentPage={page}")
        items = ((d.get("data") or {}).get("items") or []) if isinstance(d, dict) else []
        for x in items:
            out.append(("kucoin", str(x.get("annId")), x.get("annTitle", ""), (x.get("cTime") or 0) / 1000, sc.kucoin_listing_symbols(x.get("annTitle", ""))))
        if len(items) < 50:
            break
    _, d, _ = http("https://api.bitget.com/api/v2/public/annoucements?language=en_US&annType=coin_listings&limit=50")
    for x in (d.get("data") or []) if isinstance(d, dict) else []:
        out.append(("bitget", str(x.get("annId")), x.get("annTitle", ""), int(x.get("cTime") or 0) / 1000, sc.bitget_listing_symbols(x.get("annTitle", ""))))
    return out


def append(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    d = Path(sys.argv[1])
    d.mkdir(parents=True, exist_ok=True)
    sp = d / "state.json"
    state = json.loads(sp.read_text()) if sp.exists() and sp.stat().st_size else {}
    state.setdefault("seen", {})
    state.setdefault("missing", {})
    state.setdefault("watch", {})
    state.setdefault("ann_seen", [])
    state.setdefault("f3_watch", [])
    state.setdefault("prev_cand", {})
    state.setdefault("polls", 0)
    now = time.time()
    led = d / "ledger"
    bk = books()
    small = {v: bk[v] for v in ("kucoin", "gate", "mexc", "bitget")}
    errors = {v: not bk[v] for v in bk}
    # F1: new listings, gone pairs, spread snapshots for 72 h
    new, gone, state["seen"], state["missing"] = ta.diff_listings(state["seen"], {v: set(q) for v, q in small.items()}, now, state["missing"])
    rows = []
    for v, b in new:
        q = small[v][b]
        state["watch"][f"{v}:{b}"] = {"t0": now}
        rows.append({"kind": "new", "t": now, "venue": v, "base": b, "bid": q["bid"], "ask": q["ask"], "vol24": q["vol"]})
    for v, b in gone:
        rows.append({"kind": "gone", "t": now, "venue": v, "base": b})
    for key, w in list(state["watch"].items()):
        if now - w["t0"] > ta.F1_WATCH_S:
            del state["watch"][key]
            continue
        v, b = key.split(":", 1)
        q = small.get(v, {}).get(b)
        if q and (now - w["t0"]) > 600:
            rows.append({"kind": "snap", "t": now, "venue": v, "base": b, "age_h": round((now - w["t0"]) / 3600, 2), "bid": q["bid"],
                         "ask": q["ask"], "bid_sz": q["bid_sz"], "ask_sz": q["ask_sz"], "vol24": q["vol"],
                         "spread": round(q["ask"] / q["bid"] - 1, 5)})
    append(led / "f1_listings.jsonl", rows)
    # F2: cross-exchange gaps against Binance
    status = coin_status()
    cand_rows, counts = [], {}
    for v in ("kucoin", "gate", "mexc", "bitget"):
        prev = set(state["prev_cand"].get(v, []))
        st = {b: status.get(v, {}).get(b) for b in small[v]}
        c, n, coll = ta.f2_candidates(small[v], bk["binance"], st, prev)
        counts[v] = {"compared": n, "collisions": coll, "candidates": len(c)}
        state["prev_cand"][v] = [x["base"] for x in c]
        cand_rows += [{"kind": "gap", "t": now, "venue": v, **x, "binance_status": None} for x in c]
    append(led / "f2_gaps.jsonl", cand_rows + [{"kind": "poll", "t": now, "counts": counts, "errors": errors}])
    # F3: announcements and the Binance reaction at +1h, +4h, +24h
    seen = set(state["ann_seen"])
    arows = []
    for v, aid, title, ts, syms in announcements():
        k = f"{v}:{aid}"
        if k in seen:
            continue
        seen.add(k)
        first_run = state["polls"] == 0
        arows.append({"kind": "ann", "t": now, "venue": v, "ann_id": aid, "title": title, "ann_ts": ts, "symbols": syms, "backfill": first_run})
        if not first_run:
            for s_ in syms:
                q = bk["binance"].get(s_)
                if q:
                    state["f3_watch"].append({"key": f"{k}:{s_}", "t0": now, "done": [], "p0": (q["bid"] + q["ask"]) / 2, "base": s_,
                                              "btc0": (bk["binance"]["BTC"]["bid"] + bk["binance"]["BTC"]["ask"]) / 2 if "BTC" in bk["binance"] else None})
    state["ann_seen"] = sorted(seen)
    due, state["f3_watch"] = ta.f3_due(state["f3_watch"], now)
    for w, off in due:
        q = bk["binance"].get(w["base"])
        arows.append({"kind": "reaction", "t": now, "key": w["key"], "offset_s": off, "p0": w["p0"], "btc0": w.get("btc0"),
                      "p1": None if not q else (q["bid"] + q["ask"]) / 2,
                      "btc1": (bk["binance"]["BTC"]["bid"] + bk["binance"]["BTC"]["ask"]) / 2 if "BTC" in bk["binance"] else None})
    append(led / "f3_announcements.jsonl", arows)
    state["polls"] += 1
    state["last_poll"] = now
    sp.write_text(json.dumps(state))
    summary = {"polls": state["polls"], "new_listings": len(new), "gone": len(gone), "watching": len(state["watch"]), "f2": counts,
               "errors": errors, "f2_candidates": len(cand_rows), "announcements_new": sum(1 for r in arows if r["kind"] == "ann")}
    (d / "thin_a_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
