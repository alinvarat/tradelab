"""news_v3 split over parallel jobs (.github/workflows/research_sharded.yml; research/studies/sharding.py).

Why: the single-job run (Actions 45510805212) found 2390 held-out 2.02 filings, 1746 tradeable, so ~5238 sequential
Claude CLI calls (3 samples each, at most TRADELAB_CLAUDE_PARALLEL=2 at once) and hit the 240-minute job limit.

Protocol unchanged (research/studies/protocol_news_v3.md): the events, features, prompt, vote rule, returns, costs
and verdict below are the same code path as `study_news_v3` in run.py. Only the shape differs:
  symbols_news_v3()      plan job: find the held-out filings; the "universe" is one string per filing, ordered by
                         a hash of its accession number (so the [i::N] split is deterministic and balanced)
  rows_news_v3(slice)    shard job: features, documents, 3 Claude calls and returns for its own filings
  summarize_news_v3(all) merge job: pairing, bootstrap and verdict, exactly as study_news_v3
bind(g) closes the three functions over run.py's globals (helpers _sec_text, _calls_path, log) so this module never
imports run.py. Runs on GitHub Actions only.
"""
import hashlib
import json
import random
import threading
import time

from core import data, news_backtest as nb, studies as st

ASK_TRIES = 3          # a reply that comes back empty (rate limit, CLI error) is asked again; never silently a skip


def _key(accession):
    return hashlib.sha256(accession.encode()).hexdigest()[:10]


def bind(g):
    log, sec_text = g["log"], g["_sec_text"]

    def symbols_news_v3():
        import calendar as _cal
        import urllib.error
        cik_ticker = {}
        for t, c in nb.sec_company_tickers().items():
            cik_ticker.setdefault(c, t)
        day = _cal.timegm(time.strptime(st.NEWS_V3_FIRST_DAY, "%Y-%m-%d"))
        end = _cal.timegm(time.strptime(st.NEWS_V3_LAST_DAY, "%Y-%m-%d")) + 86400
        idx_rows = []
        while day < end:
            gm = time.gmtime(day)
            if gm.tm_wday < 5:
                url = (f"https://www.sec.gov/Archives/edgar/daily-index/{gm.tm_year}/QTR{(gm.tm_mon - 1) // 3 + 1}/"
                       f"form.{time.strftime('%Y%m%d', gm)}.idx")
                try:
                    idx_rows += st.parse_form_idx(sec_text(url))
                except urllib.error.HTTPError as e:
                    log(f"  index {url}: {e}")
            day += 86400
        out = []
        for cik in sorted({r["cik"] for r in idx_rows if r["cik"] in cik_ticker}):
            try:
                fs = nb.sec_filings(cik, forms=("8-K",), since="2026-04-01")
            except Exception as e:
                log(f"  submissions {cik}: {e}")
                continue
            e202 = sorted([f for f in fs if "2.02" in f["items"]], key=lambda f: f["ts"])
            for k, f in enumerate(e202):
                if st.NEWS_V3_FIRST_DAY <= f["date"] <= st.NEWS_V3_LAST_DAY:
                    prev = [p for p in e202[:k] if f["ts"] - p["ts"] <= 200 * 86400]
                    ev = {**f, "cik": cik, "symbol": cik_ticker[cik], "prev": prev[-1] if prev else None}
                    out.append(_key(ev["accession"]) + "|" + json.dumps(ev, sort_keys=True))
        log(f"held-out 2.02 filings: {len(out)}")
        return out

    def rows_news_v3(slice_):
        from concurrent.futures import ThreadPoolExecutor
        from core import ai_news
        v1 = json.load(open(g["_calls_path"]()))
        events = [json.loads(s.split("|", 1)[1]) for s in slice_]
        gaps = {"filings_in_slice": len(events), "no_reaction_or_liquidity": 0, "no_text": 0, "empty_replies": 0,
                "failed_samples": 0}
        bars, kept = {}, []
        for ev in events:
            s = ev["symbol"]
            if s not in bars:
                try:
                    bars[s] = data.chart(s, "6mo", "1d")["bars"]
                except Exception:
                    bars[s] = []
            feat = st.reaction_features(bars[s], ev["ts"])
            cost = st.liquidity_cost(bars[s], feat["entry_index"]) if feat else None
            if not feat or cost is None:
                gaps["no_reaction_or_liquidity"] += 1
                continue
            kept.append({**ev, **feat, "cost_side": cost})
        log(f"tradeable: {len(kept)} of {len(events)}")
        spy = data.chart("SPY", "6mo", "1d")["bars"]
        for ev in kept:
            sf = st.reaction_features(spy, ev["ts"])
            ev["spy_gap_pct"], ev["spy_runup_pct"] = (sf["gap_pct"], sf["runup_5d_pct"]) if sf else (None, None)

        def doc(cik, f, limit):
            base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{f['accession'].replace('-', '')}/"
            names = [x["name"] for x in json.loads(sec_text(base + "index.json"))["directory"]["item"]]
            return st.html_text(sec_text(base + st.pick_exhibit(names, f["doc"])), limit)

        for ev in kept:
            try:
                ev["text"] = doc(ev["cik"], ev, 12000)
                ev["prev_text"] = doc(ev["cik"], ev["prev"], 6000) if ev["prev"] else ""
            except Exception as e:
                ev["text"] = None
                log(f"  document {ev['symbol']}: {e}")
        gaps["no_text"] = sum(1 for ev in kept if not ev.get("text"))
        kept = [ev for ev in kept if ev.get("text")]
        spent0 = ai_news.spend()

        lock = threading.Lock()

        def ask(ev):
            user = st.v3_message(ev["symbol"], ev["accepted"], ev["runup_5d_pct"], ev["gap_pct"], ev["spy_runup_pct"],
                                 ev["spy_gap_pct"], ev["prev_text"], ev["text"])
            replies = []
            for _ in range(st.NEWS_V3_SAMPLES):
                text = ""
                for k in range(ASK_TRIES):
                    text = ai_news.chat(st.NEWS_V3_SYSTEM, user, timeout=180, temperature=0.7)[0]
                    if text and text.strip():
                        break
                    with lock:
                        gaps["empty_replies"] += 1
                    time.sleep(5 * (k + 1))
                if not (text and text.strip()):
                    with lock:
                        gaps["failed_samples"] += 1
                replies.append(text)
            return ev, st.vote_v3(replies)

        with ThreadPoolExecutor(6) as ex:
            voted = list(ex.map(ask, kept))
        spent1 = ai_news.spend()
        rows = [{"reader": "_shard", "calls_cli": spent1["calls"] - spent0["calls"],
                 "tokens_in": spent1["tokens_in"] - spent0["tokens_in"],
                 "tokens_out": spent1["tokens_out"] - spent0["tokens_out"],
                 "cost_usd": spent1["total_usd"] - spent0["total_usd"],
                 "notional_usd": spent1.get("notional_usd", 0.0) - spent0.get("notional_usd", 0.0)}]
        for ev, v in voted:
            old = v1.get(ev["accession"], {})
            rows.append({"reader": "_event", "accession": ev["accession"], "symbol": ev["symbol"]})
            for h in nb.HORIZONS:
                r = nb.event_return(bars[ev["symbol"]], ev["ts"], h)
                m = nb.event_return(spy, ev["ts"], h)
                if not r or not m or m["entry_t"] != r["entry_t"]:
                    continue
                r = {**r, "gross": r["gross"] - m["gross"]}          # SPY-adjusted
                base = {"symbol": ev["symbol"], "ts": ev["ts"], "entry_t": r["entry_t"], "horizon": h,
                        "gross": r["gross"], "accession": ev["accession"], "cost_side": ev["cost_side"],
                        "gap_pct": ev["gap_pct"],
                        "rand_sign": random.Random(f"dir:{ev['symbol']}:{ev['ts']}").choice((1, -1))}
                rows.append({**base, "reader": "v3", "direction": v["direction"], "confidence": v["confidence"],
                             "votes": v["votes"], "expected_median": v["expected_median"]})
                rows.append({**base, "reader": "v3_majority", "direction": v["majority"], "confidence": 0})
                if old.get("direction"):
                    rows.append({**base, "reader": "v1", "direction": old["direction"],
                                 "confidence": old.get("confidence", 0)})
        return {"rows": rows, "gaps": gaps}

    def summarize_news_v3(all_rows):
        """Same pairing, bootstrap and verdict as study_news_v3 (run.py)."""
        v2r = [r for r in all_rows if r["reader"] == "v3"]
        v1r = [r for r in all_rows if r["reader"] == "v1"]
        maj = [r for r in all_rows if r["reader"] == "v3_majority"]
        filings = sum(1 for r in all_rows if r["reader"] == "_event")
        shard = [r for r in all_rows if r["reader"] == "_shard"]
        pair = []
        by1 = {(r["accession"], r["horizon"]): r for r in v1r}
        for r in v2r:
            o = by1.get((r["accession"], r["horizon"]))
            if not o:
                continue
            a = st.signed_net(r["gross"], st.sign_of(r["direction"]), 1.0, r["cost_side"])
            b = st.signed_net(o["gross"], st.sign_of(o["direction"]), 1.0, o["cost_side"])
            pair.append({"symbol": r["symbol"], "ts": r["ts"], "horizon": r["horizon"], "diff": a - b})
        rng = random.Random(20261124)
        paired = {}
        for h in nb.HORIZONS:
            x = [p for p in pair if p["horizon"] == h]
            if x:
                paired[f"H{h}"] = {"n": len(x), "mean_diff": sum(p["diff"] for p in x) / len(x),
                                   "p_block": nb.block_bootstrap_p([p["diff"] for p in x],
                                                                   [nb.cluster_key(p) for p in x], rng)}
        h5 = st.llm_summary(v2r, 5)
        edge = (h5.get("n", 0) >= 60 and h5.get("mean_net", 0) > 0 and h5.get("p_net_block", 1) < 0.05
                and h5.get("hit", 0) >= 0.55 and h5.get("mean_net_2x", 0) > 0)
        better = paired.get("H5", {}).get("mean_diff", 0) > 0 and paired.get("H5", {}).get("p_block", 1) < 0.05
        return {"verdict": "v3 edge" if edge else "v3 no edge shown", "v3_better_than_v1": better, "filings": filings,
                "llm_cost_usd": round(sum(s["cost_usd"] for s in shard), 4),
                "claude_cli_calls": sum(s["calls_cli"] for s in shard),
                "claude_tokens_in": sum(s["tokens_in"] for s in shard),
                "claude_tokens_out": sum(s["tokens_out"] for s in shard),
                "claude_notional_usd": round(sum(s["notional_usd"] for s in shard), 2),
                "model": "claude-haiku-5-5 (Claude Code CLI, Max plan; 3 samples, default sampling)",
                "returns": "SPY-adjusted", "paired_v3_minus_v1": paired,
                **{f"v3_H{h}": st.llm_summary(v2r, h) for h in nb.HORIZONS},
                **{f"v3_majority_H{h}": st.llm_summary(maj, h) for h in nb.HORIZONS},
                **{f"v1_H{h}": st.llm_summary(v1r, h) for h in nb.HORIZONS}}

    return {"symbols_news_v3": symbols_news_v3, "rows_news_v3": rows_news_v3, "summarize_news_v3": summarize_news_v3}
