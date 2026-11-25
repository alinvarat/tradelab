"""Offline tests for the sharded research runner (research/studies/sharding.py, binance_vision.py, run.py modes)."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from research.studies import binance_vision as bv
from research.studies import sharding as sh

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "research" / "studies" / "run.py"
SYMS = [f"C{k:02d}USDT" for k in range(23)]


def parts_for(universe, n, study="x", rows_fn=None):
    rows_fn = rows_fn or (lambda sl: [{"symbol": s, "v": len(s)} for s in sl])
    return [sh.make_part(study, i, n, universe, rows_fn(sh.split(universe, i, n))) for i in range(n)]


class Split(unittest.TestCase):
    def test_disjoint_cover_and_deterministic(self):
        shuffled = list(reversed(SYMS)) + SYMS[:5]          # order and duplicates must not matter
        for n in (1, 2, 5, 23, 40):
            slices = [sh.split(shuffled, i, n) for i in range(n)]
            flat = [s for sl in slices for s in sl]
            self.assertEqual(sorted(flat), sorted(SYMS))
            self.assertEqual(len(flat), len(set(flat)))
            self.assertEqual(slices, [sh.split(SYMS, i, n) for i in range(n)])
        self.assertEqual(sh.split(SYMS, 1, 5), sorted(SYMS)[1::5])
        self.assertEqual(sh.split(SYMS, 30, 40), [])

    def test_bad_index(self):
        for i, n in ((5, 5), (-1, 5), (0, 0)):
            with self.assertRaises(ValueError):
                sh.split(SYMS, i, n)

    def test_hash_ignores_order(self):
        self.assertEqual(sh.universe_hash(SYMS), sh.universe_hash(list(reversed(SYMS)) + SYMS[:3]))
        self.assertNotEqual(sh.universe_hash(SYMS), sh.universe_hash(SYMS[1:]))


class Merge(unittest.TestCase):
    def test_merge_in_shard_order(self):
        parts = parts_for(SYMS, 12)
        rows, info = sh.merge_parts(list(reversed(parts)), "x")
        self.assertEqual([r["symbol"] for r in rows], [s for i in range(12) for s in sh.split(SYMS, i, 12)])
        self.assertEqual(info["shards"], 12)
        self.assertEqual(info["n_symbols"], 23)
        self.assertEqual(sum(info["shard_rows"]), 23)

    def test_gaps_summed(self):
        parts = parts_for(SYMS, 3, rows_fn=lambda sl: {"rows": [], "gaps": {"empty": len(sl), "note": "a"}})
        _, info = sh.merge_parts(parts, "x")
        self.assertEqual(info["shard_gaps"]["empty"], 23)
        self.assertEqual(info["shard_gaps"]["note"], ["a", "a", "a"])

    def test_rejects_missing_duplicate_and_mismatch(self):
        parts = parts_for(SYMS, 4)
        with self.assertRaisesRegex(sh.MergeError, r"missing shards: \[2\]"):
            sh.merge_parts(parts[:2] + parts[3:], "x")
        with self.assertRaisesRegex(sh.MergeError, "duplicate"):
            sh.merge_parts(parts + [parts[1]], "x")
        other = parts_for(SYMS[:-1], 4)
        with self.assertRaisesRegex(sh.MergeError, "different universes"):
            sh.merge_parts(parts[:3] + other[3:], "x")
        with self.assertRaisesRegex(sh.MergeError, "shard count"):
            sh.merge_parts(parts[:3] + parts_for(SYMS, 5)[3:4], "x")
        with self.assertRaisesRegex(sh.MergeError, "another study"):
            sh.merge_parts(parts, "y")
        with self.assertRaises(sh.MergeError):
            sh.merge_parts([], "x")

    def test_merge_dir_reads_only_part_files(self):
        with tempfile.TemporaryDirectory() as d:
            for i, p in enumerate(parts_for(SYMS, 11)):
                with open(os.path.join(d, f"x_{i}.json"), "w") as f:
                    json.dump(p, f)
            for junk in ("x.json", "x_summary.json", "xy_1.json", "x_1.json.bak"):
                Path(d, junk).write_text("{not json")
            self.assertEqual(sorted(sh.part_files(d, "x")), list(range(11)))
            rows, info = sh.merge_dir(d, "x")
            self.assertEqual(len(rows), 23)
            os.rename(os.path.join(d, "x_3.json"), os.path.join(d, "x_30.json"))
            with self.assertRaisesRegex(sh.MergeError, "holds shard 3"):
                sh.merge_dir(d, "x")


class RunnerEndToEnd(unittest.TestCase):
    """plan -> shards -> merge through run.py with the no-network selftest_shard study."""

    def run_py(self, *args):
        r = subprocess.run([sys.executable, str(RUN), *args], capture_output=True, text=True, cwd=ROOT, timeout=120)
        return r.returncode, r.stdout, r.stderr

    def test_plan_shard_merge(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, err = self.run_py("selftest_shard", "--plan", "--shards", "7", "--out", f"{d}/universe.json")
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out), list(range(7)))
            for i in range(7):
                code, out, err = self.run_py("selftest_shard", "--shard", str(i), "--shards", "7",
                                             "--universe", f"{d}/universe.json", "--out", f"{d}/selftest_shard_{i}.json")
                self.assertEqual(code, 0, err)
            code, out, err = self.run_py("selftest_shard", "--merge", d, "--out", f"{d}/selftest_shard.json")
            self.assertEqual(code, 0, err)
            summ = json.loads(out)
            self.assertEqual((summ["rows"], summ["symbols"], summ["shards"], summ["n_symbols"]), (103, 103, 7, 103))
            self.assertEqual(summ["shard_gaps"], {"empty": 0})
            # the same study unsharded (one shard) gives the same summary numbers
            os.makedirs(f"{d}/one")
            code, out1, err = self.run_py("selftest_shard", "--shard", "0", "--shards", "1", "--out", f"{d}/one/selftest_shard_0.json")
            self.assertEqual(code, 0, err)
            code, out1, err = self.run_py("selftest_shard", "--merge", f"{d}/one", "--out", f"{d}/one/selftest_shard.json")
            self.assertEqual(json.loads(out1)["value_sum"], summ["value_sum"])
            os.remove(f"{d}/selftest_shard_4.json")
            code, _, err = self.run_py("selftest_shard", "--merge", d, "--out", f"{d}/again.json")
            self.assertEqual(code, 2)
            self.assertIn("missing shards: [4]", err)

    def test_unsharded_study_is_refused(self):
        code, _, err = self.run_py("tom", "--shard", "0", "--shards", "2")
        self.assertEqual(code, 2)
        self.assertIn("does not support sharding", err)


def zip_bytes(text, name="f.csv"):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr(name, text)
    return b.getvalue()


class FakeHTTPError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class Opener:
    """Fake urlopen: answers[url] is bytes, an exception, or a list consumed one per call."""

    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def __call__(self, url, timeout):
        self.calls.append(url)
        a = self.answers.get(url, FakeHTTPError(404))
        if isinstance(a, list):
            a = a.pop(0)
        if isinstance(a, Exception):
            raise a
        return io.BytesIO(a)


NOSLEEP = {"sleep": lambda s: None}


class VisionUrls(unittest.TestCase):
    def test_every_kind(self):
        B = bv.BASE
        self.assertEqual(bv.vision_url("spot", "monthly", "klines", "BTCUSDT", (2024, 3), "1d"),
                         f"{B}/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2024-03.zip")
        self.assertEqual(bv.vision_url("spot", "daily", "klines", "BTCUSDT", "2026-11-24", "1h"),
                         f"{B}/spot/daily/klines/BTCUSDT/1h/BTCUSDT-1h-2026-11-24.zip")
        self.assertEqual(bv.vision_url("futures/um", "monthly", "fundingRate", "ETHUSDT", "2022-01"),
                         f"{B}/futures/um/monthly/fundingRate/ETHUSDT/ETHUSDT-fundingRate-2022-01.zip")
        self.assertEqual(bv.vision_url("futures/um", "monthly", "premiumIndexKlines", "ETHUSDT", (2023, 12), "1h"),
                         f"{B}/futures/um/monthly/premiumIndexKlines/ETHUSDT/1h/ETHUSDT-1h-2023-12.zip")
        self.assertEqual(bv.vision_url("futures/um", "daily", "markPriceKlines", "ETHUSDT", (2025, 1, 2), "5m"),
                         f"{B}/futures/um/daily/markPriceKlines/ETHUSDT/5m/ETHUSDT-5m-2025-01-02.zip")
        self.assertEqual(bv.vision_url("futures/um", "daily", "metrics", "SOLUSDT", bv.utc(2024, 2, 29) + 3600),
                         f"{B}/futures/um/daily/metrics/SOLUSDT/SOLUSDT-metrics-2024-02-29.zip")
        self.assertEqual(bv.vision_url("spot", "monthly", "aggTrades", "SOLUSDT", "2025-06"),
                         f"{B}/spot/monthly/aggTrades/SOLUSDT/SOLUSDT-aggTrades-2025-06.zip")

    def test_bad_arguments(self):
        for args in (("coin", "monthly", "klines", "BTCUSDT", "2024-01", "1d"),
                     ("spot", "weekly", "klines", "BTCUSDT", "2024-01", "1d"),
                     ("spot", "monthly", "klines", "BTCUSDT", "2024-01"),
                     ("spot", "monthly", "klines", "btc/../x", "2024-01", "1d"),
                     ("spot", "daily", "klines", "BTCUSDT", "2024-01", "1d")):
            with self.assertRaises(ValueError):
                bv.vision_url(*args)


KLINE_MS = "1704067200000,100,110,90,105,12,1704153599999,1260,30,6,630,0\n"
KLINE_US = "1735689600000000,200,220,190,210,5,1735775999999999,1050,9,2,420,0\n"
HEADER = "open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore\n"


class VisionParse(unittest.TestCase):
    def test_kline_ms_us_and_header(self):
        a, b = bv.parse_kline(KLINE_MS.strip().split(",")), bv.parse_kline(KLINE_US.strip().split(","))
        self.assertEqual(a[:5], (1704067200, 100.0, 110.0, 90.0, 105.0))
        self.assertEqual((a[7], a[8]), (1260.0, 30))
        self.assertEqual(b[0], 1735689600)
        self.assertEqual(b[6], 1735775999)
        self.assertTrue(bv.is_header(HEADER.strip().split(",")))
        self.assertFalse(bv.is_header(KLINE_MS.split(",")))
        self.assertFalse(bv.is_header(["2024-01-01 00:05:00", "BTCUSDT"]))

    def test_funding_metrics_aggtrades(self):
        self.assertEqual(bv.parse_funding(["1704096000000", "8", "0.00010000"]), (1704096000.0, 0.0001))
        m = bv.parse_metrics(["2024-01-01 00:05:00", "BTCUSDT", "100.5", "4000000", "1.2", "1.3", "0.9", ""])
        self.assertEqual(m["ts"], bv.utc(2024) + 300)
        self.assertEqual((m["sum_open_interest"], m["sum_taker_long_short_vol_ratio"]), (100.5, None))
        spot = bv.parse_aggtrade("1,42000.1,0.5,10,12,1735689600123456,True,True".split(","))
        fut = bv.parse_aggtrade("1,42000.1,0.5,10,12,1704067200123,false".split(","))
        self.assertAlmostEqual(spot[0], 1735689600.123456, places=5)
        self.assertTrue(spot[3])
        self.assertEqual((fut[0], fut[3]), (1704067200.123, False))

    def test_months_days(self):
        self.assertEqual(bv.months(bv.utc(2023, 11, 15), bv.utc(2024, 2)), [(2023, 11), (2023, 12), (2024, 1)])
        self.assertEqual(bv.days(bv.utc(2024, 2, 28) + 5, bv.utc(2024, 3, 1) + 1), [(2024, 2, 28), (2024, 2, 29), (2024, 3, 1)])


class VisionFetch(unittest.TestCase):
    def url(self, d):
        return bv.vision_url("spot", "monthly", "klines", "AUSDT", d, "1d")

    def test_ok_404_and_failure(self):
        op = Opener({self.url("2024-01"): zip_bytes(HEADER + KLINE_MS),
                     self.url("2024-02"): [ConnectionError("reset"), zip_bytes(KLINE_MS)],
                     self.url("2024-03"): ConnectionError("down")})
        kw = dict(opener=op, **NOSLEEP)
        got = bv.fetch("spot", "monthly", "klines", "AUSDT", "2024-01", "1d", bv.parse_kline, **kw)
        self.assertEqual([r[0] for r in got], [1704067200])
        self.assertEqual(len(bv.fetch("spot", "monthly", "klines", "AUSDT", "2024-02", "1d", **kw)), 1)   # retried
        self.assertEqual(bv.fetch("spot", "monthly", "klines", "AUSDT", "2024-04", "1d", **kw), [])        # 404
        self.assertIsNone(bv.fetch("spot", "monthly", "klines", "AUSDT", "2024-03", "1d", tries=3, **kw))   # failed
        self.assertEqual(op.calls.count(self.url("2024-03")), 3)
        self.assertEqual(op.calls.count(self.url("2024-04")), 1)                                            # no retry on 404

    def test_corrupt_zip_is_retried_then_failed(self):
        op = Opener({self.url("2024-01"): b"not a zip"})
        self.assertIsNone(bv.fetch("spot", "monthly", "klines", "AUSDT", "2024-01", "1d", tries=2, opener=op, **NOSLEEP))

    def test_series_dedupes_windows_and_lists_failures(self):
        jan = "".join(f"{1704067200000 + k * 86400000},1,1,1,{k},1,0,1,1,1,1,0\n" for k in range(31))
        feb = f"{1706745600000},1,1,1,99,1,0,1,1,1,1,0\n" + jan.splitlines()[-1] + "\n"      # overlap row repeated
        op = Opener({self.url("2024-01"): zip_bytes(jan), self.url("2024-02"): zip_bytes(feb),
                     self.url("2024-03"): ConnectionError("x")})
        rows, failed = bv.klines("AUSDT", bv.utc(2024, 1, 10), bv.utc(2024, 4), opener=op, tries=1, **NOSLEEP)
        ts = [r[0] for r in rows]
        self.assertEqual(ts, sorted(set(ts)))
        self.assertEqual(ts[0], int(bv.utc(2024, 1, 10)))
        self.assertEqual(len(ts), 22 + 1)
        self.assertEqual(failed, ["2024-03"])

    def test_iter_file_streams(self):
        url = bv.vision_url("futures/um", "monthly", "aggTrades", "AUSDT", "2024-01")
        body = "agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker\n" + \
            "".join(f"{k},1.5,2,{k},{k},{1704067200000 + k},true\n" for k in range(1000))
        it = bv.iter_file("futures/um", "monthly", "aggTrades", "AUSDT", "2024-01", parse=bv.parse_aggtrade,
                          opener=Opener({url: zip_bytes(body)}), **NOSLEEP)
        self.assertFalse(isinstance(it, list))
        self.assertEqual(next(iter(it))[1:], (1.5, 2.0, True))
        self.assertEqual(sum(1 for _ in it), 999)


def listing_page(names, prefix, next_marker=None):
    items = "".join(f"<CommonPrefixes><Prefix>{prefix}{n}/</Prefix></CommonPrefixes>" for n in names)
    trunc = "true" if next_marker else "false"
    nm = f"<NextMarker>{next_marker}</NextMarker>" if next_marker else ""
    return f"<ListBucketResult><Prefix>{prefix}</Prefix><IsTruncated>{trunc}</IsTruncated>{nm}{items}</ListBucketResult>".encode()


class Listing(unittest.TestCase):
    def test_pages_retries_and_filter(self):
        p = "data/futures/um/monthly/klines/"
        u1 = f"{bv.LISTING}?delimiter=/&prefix={p}"
        u2 = u1 + f"&marker={p}LUNAUSDT/"
        op = Opener({u1: [ConnectionError("x"), listing_page(["AUSDT", "BTCBUSD", "LUNAUSDT"], p, f"{p}LUNAUSDT/")],
                     u2: listing_page(["ZUSDT", "AUSDT", "BTCUSDT_240329"], p)})
        self.assertEqual(bv.list_symbols("futures/um", opener=op, **NOSLEEP), ["AUSDT", "LUNAUSDT", "ZUSDT"])

    def test_failure_raises(self):
        with self.assertRaises(RuntimeError):
            bv.list_symbols("spot", opener=Opener({f"{bv.LISTING}?delimiter=/&prefix=data/spot/monthly/klines/":
                                                   ConnectionError("x")}), tries=2, **NOSLEEP)


class ShardedWorkflow(unittest.TestCase):
    def setUp(self):
        from tests.test_workflows import keys_at
        self.keys_at = keys_at
        self.text = (ROOT / ".github" / "workflows" / "research_sharded.yml").read_text()
        self.lines = self.text.splitlines()

    def block(self, key, indent):
        import re
        i = next(n for n, l in enumerate(self.lines) if re.match(r"^ {%d}%s:\s*$" % (indent, re.escape(key)), l))
        return self.keys_at(self.lines, i + 1, indent + 2)

    def test_structure(self):
        self.assertEqual(self.block("on", 0), ["workflow_dispatch"])
        self.assertEqual(self.block("inputs", 4), ["study", "shards"])
        self.assertEqual(self.block("jobs", 0), ["plan", "shard", "merge"])
        self.assertIn('default: "20"', self.text)
        self.assertIn("fromJSON(needs.plan.outputs.matrix)", self.text)
        self.assertIn("merge-multiple: true", self.text)
        self.assertIn("--merge out/", self.text)
        self.assertEqual(self.text.count("CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"), 2)
        self.assertEqual(self.text.count("curl -fsSL https://claude.ai/install.sh | bash"), 2)
        self.assertNotIn("\t", self.text)

    def test_inputs_never_expanded_inside_scripts(self):
        in_run = False
        for line in self.lines:
            s = line.strip()
            if s.startswith("run:"):
                in_run, ind = True, len(line) - len(line.lstrip())
                continue
            if in_run and s and len(line) - len(line.lstrip()) <= ind:
                in_run = False
            if in_run:
                self.assertNotIn("${{", line, line)


if __name__ == "__main__":
    unittest.main()
