"""Offline tests for the Sonnet-vs-Haiku comparison (research/news_train/protocol_cmp_20261126.md). Synthetic data only, no network, no model call."""
import hashlib
import json
import unittest
from pathlib import Path

from core import ai_news
from research.news_train import logic as L
from research.news_train import logic_cmp as C
from research.news_train import logic_r2 as R
from research.news_train import run_cmp as X

ROOT = Path(__file__).resolve().parents[1]
NT = ROOT / "research" / "news_train"
P = C.load_params()
P2 = R.load_params()


class Lock(unittest.TestCase):
    def test_protocol_hash_and_params(self):
        f = NT / "protocol_cmp_20261126.md"
        self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(), f.with_suffix(".sha256").read_text().strip())
        self.assertIn(hashlib.sha256((NT / "params_cmp.json").read_bytes()).hexdigest(), f.read_text())
        for n in ("protocol_cmp_addendum_20261126", "protocol_cmp_addendum2_20261126", "protocol_cmp_addendum3_20261127"):
            a = NT / (n + ".md")
            self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(), a.with_suffix(".sha256").read_text().strip())
        a3 = (NT / "protocol_cmp_addendum3_20261127.md").read_text()
        self.assertIn(hashlib.sha256((NT / "params_cmp_a3.json").read_bytes()).hexdigest(), a3)
        self.assertTrue(set(json.loads((NT / "params_cmp_a3.json").read_text())) >= {"cap_per_day", "min_n", "seed"})

    def test_models_and_registry(self):
        self.assertEqual(P["models"], {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5"})
        for s in X.SETS:
            X.version_of(s)                                   # prompt sha256 equals the locked registry
        self.assertEqual(ai_news.CLAUDE_MODEL, "claude-haiku-5-5")   # core default untouched

    def test_workflow_structure(self):
        t = (ROOT / ".github" / "workflows" / "news_train_cmp.yml").read_text()
        self.assertNotIn("\t", t)
        for j in ("  leak:", "  hist_prep:", "  hist_call:", "  hist_merge:", "  fwd:"):
            self.assertIn(j, t)
        self.assertIn("claude-sonnet-5-5", t)
        self.assertIn("workflow_dispatch:", t)
        self.assertNotIn("pull_request", t)


class Gate(unittest.TestCase):
    def table(self, last_known):
        out = []
        for m in ("2025-10", "2025-11", "2025-12", "2026-06", "2026-07"):
            known = m <= last_known
            out.append({"asset": "^GSPC", "month": m, "answered": 6 if known else 0, "acc_answered": 0.8 if known else None})
        return out

    def test_cutoff_rule_matches_round1_haiku(self):
        self.assertEqual(C.leak_cutoff(self.table("2025-11"), P["leak_rule"]), "2025-11")
        self.assertEqual(C.leak_cutoff(self.table("2026-06"), P["leak_rule"]), "2026-06")
        self.assertIsNone(C.leak_cutoff([{"month": "2025-01", "answered": 3, "acc_answered": 1.0}], P["leak_rule"]))
        self.assertIsNone(C.leak_cutoff([{"month": "2025-01", "answered": 9, "acc_answered": 0.5}], P["leak_rule"]))

    def test_eligibility(self):
        self.assertEqual(C.first_eligible_day("2026-06"), "2026-07-01")
        self.assertEqual(C.first_eligible_day("2025-12"), "2026-01-01")
        self.assertTrue(C.eligible(L.day_ts("2026-07-01"), "2026-06"))
        self.assertFalse(C.eligible(L.day_ts("2026-06-30"), "2026-06"))
        self.assertTrue(C.eligible(L.day_ts("2020-01-01"), None))
        self.assertEqual(C.combined_cutoff("2025-11", "2026-06"), "2026-06")


class Stats(unittest.TestCase):
    def test_sign_test(self):
        self.assertEqual(C.sign_test([1, 1, 1, 1, 1])["p"], 2 * 1 / 32)
        s = C.sign_test([1, -1, 0, 0])
        self.assertEqual((s["n_nonzero"], s["ties"], s["p"]), (2, 2, 1.0))
        self.assertIsNone(C.sign_test([0, 0])["p"])

    def test_paired_summary_detects_shift(self):
        diffs = [0.01 + 0.001 * (i % 3) for i in range(300)]
        days = [f"d{i // 10}" for i in range(300)]
        r = C.paired_summary(diffs, days, 300, 1)
        self.assertGreater(r["lo"], 0)
        self.assertLess(r["sign"]["p"], 0.001)
        z = C.paired_summary([0.01, -0.01] * 100, [f"d{i // 4}" for i in range(200)], 300, 1)
        self.assertLess(abs(z["mean_diff"]), 1e-9)

    def test_pair_direction_own_entry_and_discordance(self):
        items = {"a": {"day": "d1"}, "b": {"day": "d1"}, "c": {"day": "d2"}}
        long_ = {"ok": True, "d": {"1h": "long"}, "exp": {"1h": 1.0}}
        none = {"ok": True, "d": {"1h": "none"}, "exp": {"1h": 0.0}}
        dh = {"a": long_, "b": none, "c": long_}
        ds = {"a": long_, "b": long_, "c": {"ok": False}}
        # Sonnet enters later: a smaller gross on item a; item c has no Sonnet reply and is excluded
        lh = {k: {"gross": {"1h": 0.02}} for k in items}
        ls = {k: {"gross": {"1h": 0.01}} for k in items}
        rows = C.pair_direction(items, dh, ds, lh, ls, "crypto", "1h", {"1h": 0}, True, P2)
        self.assertEqual([r["key"] for r in rows], ["a", "b"])
        self.assertLess(rows[0]["d"], 0)                       # later entry earns less
        self.assertEqual(rows[1]["a"], 0.0)                    # Haiku abstained
        self.assertEqual(C.discordant(rows), 1)

    def test_project_and_fire(self):
        p = C.project(50, 300, 0, 5 * 86400)
        self.assertEqual(p["rate_per_day"], 10.0)
        self.assertEqual(p["days_left"], 25.0)
        self.assertIsNone(C.project(0, 300, 0, 100))
        now = L.day_ts("2026-12-01")
        self.assertEqual(C.fire_reason(300, 100, now, P), "min_n")
        self.assertIsNone(C.fire_reason(299, 100, now, P))
        self.assertIsNone(C.fire_reason(300, 99, now, P))
        self.assertEqual(C.fire_reason(1, 0, L.day_ts("2027-03-31"), P), "hard_stop_underpowered")

    def test_latency(self):
        s = C.latency_stats([1, 2, 3, 4, 10])
        self.assertEqual((s["n"], s["median_s"]), (5, 3))
        self.assertEqual(C.latency_stats([None]), {"n": 0})


class Forward(unittest.TestCase):
    def test_pre_label_has_no_outcome(self):
        t = 1_800_000_000
        bars = [(t - 7200 + 60 * i, 1.0, 1.0, 100.0 + i * 0.01) for i in range(130)]
        lab = C.crypto_pre_label(bars, t, P2)
        self.assertIsNotNone(lab)
        self.assertEqual(lab["gross"], {})
        self.assertIsNotNone(lab["pre_1h"])
        self.assertIsNone(C.crypto_pre_label([], t, P2))

    def test_junk_filter(self):
        for t in ("@telsopian Bitcoin is good crypto", "RT @lsanger: bitcoin crypto database", "Bitcoin crypto news https://t.co/abc", "  "):
            self.assertTrue(C.is_junk(t), t)
        self.assertFalse(C.is_junk("Bitcoin ETF sees record crypto inflows today"))

    def test_widened_coin_rule(self):
        f = C.coin_from_title
        self.assertEqual(f("\U0001F7E2 [ZECUSDT] Longs building: Binance OI +1.1%"), "ZEC")
        self.assertEqual(f("Binance Perp Monitor: BULLAUSDT (BULLA) +22% in the past 10 seconds"), "BULLA")
        self.assertEqual(f("Binance Will List XYZ/USDT with Seed Tag"), "XYZ")
        self.assertEqual(f("OKX to support ZETA (ZETA) migration"), "ZETA")
        self.assertIsNone(f("Cash Dividend of The Wendy's Company (WEN), NVIDIA Corporation (NVDA)"))   # two symbols
        self.assertIsNone(f("Deposits in (USDT) and (USD) paused"))
        self.assertIsNone(f("Notice of Temporary Suspension of Upbit Lounge Operations"))

    def test_symbol_redaction_and_candidates_widened(self):
        it = C.title_to_item("binance_news", "k", "Binance Perp Monitor: BULLAUSDT (BULLA) +22%", 1_800_000_000, "BULLA", P2)
        self.assertNotIn("BULLA", it["text"].replace("[COIN]", ""))
        start = L.day_ts("2026-11-27")
        j = {("binance_news", "1"): {"t_seen": start + 10, "title": "Binance Perp Monitor: BULLAUSDT (BULLA) +22% in the past 10 seconds"},
             ("okx_announcements", "2"): {"t_seen": start + 20, "title": "OKX to support ZETA crypto migration notice (ZETA) today"},
             ("eqn_rest", "3"): {"t_seen": start + 30, "title": "@someone BULLAUSDT is great https://t.co/x"}}
        c = X.fwd_crypto_candidates(j, start)
        self.assertEqual(sorted(x["coin"] for x in c), ["BULLA", "ZETA"])

    def test_unpriceable_item_skipped_after_3h(self):
        import tempfile
        start = L.day_ts("2026-11-27")
        with tempfile.TemporaryDirectory() as d:
            import os
            os.makedirs(d + "/ing/news_ingest/20261127")
            row = {"event": "item", "source": "binance_news", "key": "z", "title": "Binance Perp Monitor: NOPEUSDT (NOPE) +9% in the past 10 seconds", "t_pub": start + 5, "t_seen": start + 10}
            open(d + "/ing/news_ingest/20261127/0-1.jsonl", "w").write(json.dumps(row) + "\n")
            X.fwd(d + "/out", d + "/state", d + "/ing", d + "/r2", now=start + 4 * 3600, bars_fn=lambda *a: [], run=lambda *a, **k: ([], False, {}))
            prog = json.load(open(d + "/out/fwd/progress.json"))
            self.assertEqual(prog["skipped_no_market"], 1)
            self.assertEqual(prog["crypto_items"], 0)

    def test_item_redacts_and_keys(self):
        it = C.title_to_item("eqn_rest", "k1", "Bitcoin jumps 5% on 2026-11-28", 1_800_000_000, "BTC", P2)
        self.assertNotIn("itcoin", it["text"])
        self.assertEqual(it["key"], "ing:eqn_rest:k1")

    def test_candidates_dedupe_and_start(self):
        start = L.day_ts("2026-11-27")
        j = {("eqn_rest", "1"): {"t_seen": start + 10, "title": "Bitcoin ETF sees record crypto inflows today"},
             ("eqn_rest", "2"): {"t_seen": start + 20, "title": "Bitcoin ETF sees record crypto inflows today"},
             ("eqn_rest", "3"): {"t_seen": start - 5, "title": "Ethereum crypto network upgrade goes live this week"},
             ("sec_8k", "4"): {"t_seen": start + 30, "title": "Bitcoin crypto treasury 8-K filing disclosed here"}}
        c = X.fwd_crypto_candidates(j, start)
        self.assertEqual([x["url"] for x in c], ["1"])

    def test_decide_once_and_prompt_identity(self):
        calls = []

        def fake(mk, jobs, parse, **kw):
            calls.append((mk, [j["user_sha"] for j in jobs]))
            return [{"key": j["key"], "ok": True, "model": mk, "lat_s": 1.0 if mk == "haiku" else 3.0, "d": {}, "user_sha": j["user_sha"]} for j in jobs], False, {}
        decs = {}
        todo = {"w1": [("k1", "same prompt")]}
        X.decide_heads(todo, decs, {"w1": "sys"}, {"w1": None}, fake)
        self.assertEqual(calls[0][1], calls[1][1])             # both models got identical bytes
        n = len(calls)
        X.decide_heads(todo, decs, {"w1": "sys"}, {"w1": None}, fake)
        self.assertEqual(len(calls), n)                        # an answered item is never called again
        self.assertEqual(decs[("sonnet", "w1", "k1")]["attempts"], 1)

    def test_run_model_switches_model_and_stops_on_limit(self):
        old = ai_news.CLAUDE_MODEL
        try:
            seen = []

            def empty_chat(system, user, timeout=0):
                seen.append(ai_news.CLAUDE_MODEL)
                return "", "claude exit 1"
            jobs = [{"key": str(i), "system": "s", "user": "u", "user_sha": "x"} for i in range(40)]
            res, stopped, _ = X.run_model("sonnet", jobs, lambda t: {"ok": False}, parallel=1, stop_after=3, retries=0, chat=empty_chat)
            self.assertTrue(stopped)
            self.assertLess(len(res), 10)                      # stopped after a run of empty replies, did not hammer the limit
            self.assertEqual(set(seen), {"claude-sonnet-5-5"})
            ok_chat = lambda system, user, timeout=0: ('{"d":{"5m":"none","1h":"none","1d":"none"}}', "claude/claude-haiku-5-5")  # noqa: E731
            res, stopped, _ = X.run_model("haiku", jobs[:2], lambda t: X.R.parse_reply2(t, "crypto"), parallel=1, retries=0, chat=ok_chat)
            self.assertFalse(stopped)
            self.assertTrue(all(r["ok"] and r["lat_s"] >= 0 for r in res))
        finally:
            ai_news.CLAUDE_MODEL = old

    def test_cap_per_coin_day(self):
        base = L.day_ts("2026-11-28")
        items = {f"k{i}": {"t_seen": base + i, "sym": "BTC", "text_named": f"title number {i}"} for i in range(20)}
        keep = X.capped_keys(items, list(items))
        self.assertEqual(len(keep), P["fwd"]["cap_per_coin_day"])
        self.assertEqual(keep, X.capped_keys(items, list(items)))

    def test_fwd_without_ingest_reports_blocker(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out, state, r2 = d + "/out", d + "/state", d + "/r2"
            X.fwd(out, state, d + "/none", r2, now=L.day_ts("2026-11-28"), bars_fn=lambda *a: [], run=lambda *a, **k: ([], False, {}))
            prog = json.load(open(out + "/fwd/progress.json"))
            self.assertIn("blocker", prog)
            self.assertEqual(prog["crypto"]["paired_settled_capped"], 0)
            self.assertFalse(prog["stock"]["scoring_open"])


# ------------------------------------------------------------------ addendum 3: the stock-wide forward arm
W = X.W
PW = X.PW


def pod_row(key, t_pub, cik, form="8-K", source="sec_8k", t_seen=None):
    return (source, key), {"source": source, "key": key, "title": f"{form} - ACME Corp ({cik:010d}) (Filer)", "t_pub": t_pub, "t_seen": t_seen or t_pub + 5,
                           "res": "s", "t_llm": None, "llm_s": None}


class WideLogic(unittest.TestCase):
    start = L.day_ts("2026-11-27")

    def test_parse_title_and_pool(self):
        self.assertEqual(W.parse_title("8-K - ACME Corp (0000001234) (Filer)"), ("8-K", "ACME Corp", 1234))
        self.assertIsNone(W.parse_title("no cik here"))
        j = dict([pod_row("sec:0001-26-000001", self.start + 100, 1), pod_row("sec:0001-26-000002", self.start + 200, 2, form="8-K/A"),
                  pod_row("sec:0001-26-000003", self.start - 50, 3), pod_row("prn:x", self.start + 300, 4), pod_row("sec:0001-26-000005", self.start + 400, 5, source="prnewswire")])
        j[("sec_8k", "sec:bad")] = {"source": "sec_8k", "key": "sec:bad", "title": "garbage", "t_pub": self.start + 10, "t_seen": self.start + 12}
        j[("sec_8k", "sec:nopub")] = {"source": "sec_8k", "key": "sec:nopub", "title": "8-K - X (0000000009) (Filer)", "t_pub": None, "t_seen": self.start + 12}
        rows = W.pool(j, self.start, PW)
        self.assertEqual([r["key"] for r in rows], ["sec:0001-26-000001"])
        self.assertEqual((rows[0]["acc"], rows[0]["cik"], rows[0]["day"]), ("0001-26-000001", 1, "2026-11-27"))

    def test_day_ready_waits_after_close(self):
        end = self.start + 86400
        self.assertFalse(W.day_ready("2026-11-27", end + PW["day_close_wait_s"] - 1, PW))
        self.assertTrue(W.day_ready("2026-11-27", end + PW["day_close_wait_s"], PW))

    def rows(self, n):
        return [{"key": f"sec:{i:04d}", "acc": f"{i:04d}", "cik": i + 1, "t_pub": self.start + i, "t_seen": self.start + i + 5, "day": "2026-11-27"} for i in range(n)]

    def test_select_day_cap_order_and_independence_of_input_order(self):
        p = dict(PW, cap_per_day=5, max_examine_per_day=100)
        rows = self.rows(40)
        ok = lambda r: ({"key": r["key"]}, "ok")                         # noqa: E731
        a, st = W.select_day(rows, p, ok)
        b, _ = W.select_day(list(reversed(rows)), p, ok)
        self.assertEqual([x["key"] for x in a], [x["key"] for x in b])
        self.assertEqual((len(a), st["examined"], st["pool"]), (5, 5, 40))
        self.assertEqual([x["key"] for x in a], sorted((r["key"] for r in rows), key=lambda k: W.rank(p["seed"], k))[:5])

    def test_select_day_rejections_errors_and_examine_limit(self):
        p = dict(PW, cap_per_day=100, max_examine_per_day=10)
        seen = []

        def chk(r):
            seen.append(r["key"])
            n = len(seen)
            if n % 3 == 0:
                raise RuntimeError("sec down")
            return ({"key": r["key"]}, "ok") if n % 3 == 1 else (None, "sp500")
        items, st = W.select_day(self.rows(40), p, chk)
        self.assertEqual(st["examined"], 10)
        self.assertEqual((st["errors"], st["rejected"], st["admitted"]), (3, {"sp500": 3}, 4))
        self.assertEqual(len(items), 4)

    def test_universe_helpers(self):
        self.assertEqual(W.pick_ticker(["GOOGL", "GOOG", "ZZ"]), "ZZ")
        self.assertIsNone(W.pick_ticker([]))
        sp = {"GOOGL": [("2010-01-01", None)], "OLD": [("2010-01-01", "2020-01-01")]}
        self.assertTrue(W.in_spell(sp, ["GOOG", "GOOGL"], "2026-11-27"))      # any ticker of the issuer
        self.assertFalse(W.in_spell(sp, ["OLD"], "2026-11-27"))
        self.assertTrue(W.in_spell(sp, ["OLD"], "2019-06-01"))
        self.assertFalse(W.in_spell(sp, ["NEW"], "2026-11-27"))


class WideCheck(unittest.TestCase):
    start = L.day_ts("2026-11-27")
    r = {"key": "sec:0001-26-000007", "acc": "0001-26-000007", "cik": 7, "t_pub": start + 14 * 3600, "t_seen": start + 14 * 3600 + 5, "day": "2026-11-27"}

    def run_check(self, tickers=None, spells=None, filing=None, item_ok=True):
        f = filing if filing is not None else {"accession": "0001-26-000007", "form": "8-K", "doc": "a.htm", "items": ["2.02"], "ts": 0}
        calls = []
        gj = lambda url: {"sicDescription": "Biotech"}                    # noqa: E731
        fn = lambda cik, g, since: ([f], ["ACME"])                        # noqa: E731

        def item_fn(c, cache):
            calls.append(c)
            return {"key": "sec:" + c["acc"], "market": "stock", "src": "sec_8k", "t_pub": c["ts"], "sym": c["sym"], "items": c["items"], "text": "x" * 100,
                    "descr": "old"} if item_ok else None
        res = X.wide_check(self.r, {7: ["ACMEW", "ACME"]} if tickers is None else tickers, {} if spells is None else spells, PW,
                           filings_fn=fn, get_json=gj, item_fn=item_fn)
        return res, calls

    def test_admits_non_sp500_with_arm_and_descr(self):
        (it, why), calls = self.run_check()
        self.assertEqual(why, "ok")
        self.assertEqual((it["arm"], it["split"], it["sym"]), ("wide", "fwd", "ACME"))
        self.assertEqual(it["descr"], "Issuer: a US-listed company (sector: Biotech).")
        self.assertEqual(len(calls), 1)

    def test_rejections(self):
        self.assertEqual(self.run_check(tickers={})[0], (None, "no_ticker"))
        self.assertEqual(self.run_check(spells={"ACME": [("2000-01-01", None)]})[0], (None, "sp500"))
        self.assertEqual(self.run_check(filing={"accession": "other", "form": "8-K", "doc": "a", "items": [], "ts": 0})[0], (None, "no_filing"))
        self.assertEqual(self.run_check(filing={"accession": "0001-26-000007", "form": "8-K/A", "doc": "a", "items": [], "ts": 0})[0], (None, "no_filing"))
        self.assertEqual(self.run_check(filing={"accession": "0001-26-000007", "form": "8-K", "doc": "a", "items": ["9.01"], "ts": 0})[0], (None, "item_filtered"))
        self.assertEqual(self.run_check(item_ok=False)[0], (None, "short_text"))

    def test_no_item_code_listed_is_allowed(self):
        (it, why), _ = self.run_check(filing={"accession": "0001-26-000007", "form": "8-K", "doc": "a", "items": [], "ts": 0})
        self.assertEqual(why, "ok")


class WideStep(unittest.TestCase):
    start = L.day_ts("2026-11-27")

    def pods(self, n):
        return dict(pod_row(f"sec:0001-26-{i:06d}", self.start + 3600 * 13 + i, i + 1) for i in range(n))

    def test_day_selected_once_after_close_and_only_when_due(self):
        j = self.pods(10)
        ws, wi, calls = {"days": {}}, {}, []

        def chk(r, t, s, p):
            calls.append(r["key"])
            return {"key": r["key"], "sym": "S", "t_pub": r["t_pub"]}, "ok"
        uni = lambda: ({}, {})                                          # noqa: E731
        info = X.wide_step(j, self.start, self.start + 86400 + 60, ws, wi, uni, chk)       # closed, but not yet 3 h later
        self.assertEqual((info["days_due"], calls, wi), (0, [], {}))
        now = self.start + 86400 + PW["day_close_wait_s"]
        X.wide_step(j, self.start, now, ws, wi, uni, chk)
        self.assertEqual(len(wi), 10)
        self.assertEqual(ws["days"]["2026-11-27"]["admitted"], 10)
        n = len(calls)
        X.wide_step(j, self.start, now + 7200, ws, wi, uni, chk)
        self.assertEqual(len(calls), n)                                  # never selected twice

    def test_sec_outage_retries_the_day_and_universe_failure_is_reported(self):
        j = self.pods(10)
        ws, wi = {"days": {}}, {}

        def down(r, t, s, p):
            raise RuntimeError("503")
        now = self.start + 86400 + PW["day_close_wait_s"]
        info = X.wide_step(j, self.start, now, ws, wi, lambda: ({}, {}), down)
        self.assertEqual((info["retry_days"], ws["days"], wi), (["2026-11-27"], {}, {}))

        def boom():
            raise OSError("no network")
        info = X.wide_step(j, self.start, now, ws, wi, boom, down)
        self.assertIn("blocker", info)
        self.assertEqual(ws["days"], {})


def hourly_bars(first_day, n_days):
    out = []
    t0 = L.day_ts(first_day)
    for d in range(n_days):
        day0 = t0 + d * 86400
        for i in range(7):
            o = 100.0 + d + i * 0.1
            out.append({"t": day0 + 14 * 3600 + 1800 + i * 3600, "o": o, "h": o * 1.002, "l": o * 0.998, "c": o * (1.002 if (i + d) % 2 else 0.999)})
    return out


class WideForward(unittest.TestCase):
    """The whole forward step on synthetic pod rows: selection, bars, both heads, both models, the arm's own one-shot, no change to the S&P 500 arm."""
    start = L.day_ts("2026-11-27")

    def test_wide_arm_end_to_end_offline(self):
        import os
        import shutil
        import tempfile
        W3 = '{"d": {"1h": "long", "eod": "none"}, "exp": {"1h": 1.0, "eod": 0.5}, "conf": 60, "why": "x"}'
        M1 = '{"abs1h": 1.2, "p_big": 40, "why": "x"}'
        asked = []

        def fake(mk, jobs, parse, **kw):
            out = []
            for j in jobs:
                r = parse(W3)
                if not r.get("ok"):
                    r = parse(M1)
                asked.append((mk, j["key"]))
                out.append(dict(r, key=j["key"], model=mk, lat_s=2.0, user_sha=j["user_sha"]))
            return out, False, {}

        def chk(r, t, s, p):
            return {"key": r["key"], "market": "stock", "src": "sec_8k", "t_pub": r["t_pub"], "sym": "SYM%d" % (r["cik"] % 3), "items": ["2.02"], "text": "Acme reports quarterly results " * 10,
                    "text_kind": "main", "descr": "Issuer: a US-listed company (sector: x).", "arm": "wide", "split": "fwd"}, "ok"
        intraday = lambda sym, p1, p2, interval: hourly_bars("2026-11-20", 14)      # noqa: E731
        old = X.PW
        X.PW = dict(PW, min_n=4)
        try:
            with tempfile.TemporaryDirectory() as d:
                os.makedirs(d + "/ing/news_ingest/20261127")
                rows = []
                for i in range(6):
                    k, v = pod_row(f"sec:0001-26-{i:06d}", self.start + 14 * 3600 + 60 * i, i + 1)
                    rows.append({"event": "item", "source": "sec_8k", "key": v["key"], "title": v["title"], "t_pub": v["t_pub"], "t_seen": v["t_seen"], "res": "s"})
                open(d + "/ing/news_ingest/20261127/0-1.jsonl", "w").write("\n".join(json.dumps(r) for r in rows) + "\n")
                now = L.day_ts("2026-12-03")
                X.fwd(d + "/out", d + "/state", d + "/ing", d + "/r2", now=now, bars_fn=lambda *a: [], run=fake,
                      universe_fn=lambda: ({}, {}), check_fn=chk, intraday_fn=intraday)
                prog = json.load(open(d + "/out/fwd/progress.json"))
                w = prog["stock_wide"]
                self.assertEqual((w["admitted"], w["rows_built"], w["with_pod_row"], w["both_answered_w3_m1"], w["settled"]), (6, 6, 6, 6, 6))
                self.assertEqual(w["days_selected"], 1)
                self.assertEqual(prog["stock"]["both_answered_w3_m1"], 0)            # the S&P 500 arm is untouched
                self.assertEqual(prog["stock_items"], 0)
                self.assertTrue(w.get("fired_now"))
                res = json.load(open(d + "/out/fwd/result_stock_wide.json"))
                self.assertEqual(res["n_settled"], 6)
                self.assertFalse(res["underpowered"])
                self.assertEqual(len(asked), 6 * 2 * 2)                              # items x heads x models
                self.assertFalse(os.path.exists(d + "/out/fwd/result_stock.json"))
                # next run from the kept state: no second selection, no second call, the result is not rewritten
                shutil.copytree(d + "/out/fwd", d + "/state2/fwd")

                def never(*a, **k):
                    raise AssertionError("called again")
                X.fwd(d + "/out2", d + "/state2", d + "/ing", d + "/r2", now=now + 3600, bars_fn=lambda *a: [], run=never,
                      universe_fn=never, check_fn=never, intraday_fn=intraday)
                prog2 = json.load(open(d + "/out2/fwd/progress.json"))
                self.assertEqual(prog2["stock_wide"]["both_answered_w3_m1"], 6)
                self.assertFalse(os.path.exists(d + "/out2/fwd/result_stock_wide.json"))
        finally:
            X.PW = old


if __name__ == "__main__":
    unittest.main()
