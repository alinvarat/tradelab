import gzip
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from research.news_train import ingest_branch as B
from research.news_train import run_ingest_fwd as RUN

ROOT = Path(__file__).resolve().parent.parent
NT = ROOT / "research" / "news_train"


def item(src, key, t_pub, t_seen):
    return {"event": "item", "source": src, "key": key, "title": "t", "t_pub": t_pub, "res": "s", "t_seen": t_seen, "lat_s": t_seen - t_pub}


def llm(src, key, t_pub, t_seen, t_llm):
    return {"event": "llm", "source": src, "key": key, "t_pub": t_pub, "t_seen": t_seen, "t_llm": t_llm, "llm_s": t_llm - t_seen,
            "parsed": {"direction": "up"}}


def put(root, rel, rows, raw=""):
    p = Path(root) / "news_ingest" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows) + raw)


class Reader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def test_missing_branch_is_empty(self):
        self.assertEqual(B.load_rows(os.path.join(self.root, "nope")), [])
        self.assertEqual(B.load_rows(self.root), [])

    def test_parts_overlap_flat_files_junk_and_duplicates(self):
        a, b = item("sec_8k", "sec:1", 100, 130), llm("sec_8k", "sec:1", 100, 130, 140)
        put(self.root, "20261127/0000000000-0000000100.jsonl", [a], raw="not json\n[1]\n")
        put(self.root, "20261127/0000000050-0000000200.jsonl", [a, b])          # overlapping range from a lost cursor
        put(self.root, "20261128.jsonl", [item("eqn_rest", "eqn:9", 1, 2), {"event": "other", "source": "x", "key": "k"}])
        rows = B.load_rows(self.root)
        self.assertEqual(len(rows), 3)
        j = B.join(rows)
        d = j[("sec_8k", "sec:1")]
        self.assertEqual((d["t_seen"], d["t_llm"], d["llm_s"]), (130, 140, 10))
        self.assertNotIn("parsed", d)                      # the pod's own Haiku reading is never carried

    def test_timing_and_missing_items_are_reported_not_imputed(self):
        put(self.root, "20261127/a.jsonl", [item("sec_8k", "sec:A", 100, 400)])
        j = B.join(B.load_rows(self.root))
        res = B.r2_timing([{"key": "sec:A"}, {"key": "sec:B"}], j)
        self.assertEqual(res["coverage"]["items"], 2)
        self.assertEqual((res["coverage"]["with_pod_row"], res["coverage"]["missing"]), (1, 1))
        self.assertEqual(res["rows"]["sec:A"]["seen_minus_pub_s"], 300)
        self.assertEqual(res["rows"]["sec:A"]["seen_minus_proxy_s"], 300 - B.PROXY_LAG_S)
        self.assertNotIn("sec:B", res["rows"])
        self.assertEqual(res["coverage"]["n_seen_slower_than_proxy"], 1)

    def test_wrong_source_is_not_matched(self):
        put(self.root, "20261127/a.jsonl", [item("prnewswire", "sec:A", 1, 2)])
        self.assertIsNone(B.timing_for("sec:A", B.join(B.load_rows(self.root))))

    def test_r3_progress_counts_wires_only(self):
        put(self.root, "20261127/a.jsonl", [item("prnewswire", "p1", 10, 12), llm("prnewswire", "p1", 10, 12, 20),
                                           item("prnewswire", "p2", 10, 16), item("sec_8k", "sec:1", 1, 2), item("okx_announcements", "o", 1, 2)])
        p = B.r3_progress(B.join(B.load_rows(self.root)))
        self.assertEqual(list(p), ["prnewswire"])
        self.assertEqual((p["prnewswire"]["n"], p["prnewswire"]["n_llm"], p["prnewswire"]["median_seen_minus_pub_s"]), (2, 1, 4.0))


class Runner(unittest.TestCase):
    def test_r2_writes_timing_beside_forward_items_and_survives_missing_log(self):
        with tempfile.TemporaryDirectory() as t:
            out = os.path.join(t, "out")
            os.makedirs(os.path.join(out, "fwd"))
            with gzip.open(os.path.join(out, "fwd", "items.jsonl.gz"), "wt") as f:
                f.write(json.dumps({"key": "sec:A"}) + "\n")
            RUN.r2(out, os.path.join(t, "no_such_ingest_dir"))
            res = json.load(open(os.path.join(out, "fwd", "ingest_timing.json")))
            self.assertEqual((res["coverage"]["items"], res["coverage"]["missing"], res["pod_rows"]), (1, 1, 0))
            RUN.r3(out, os.path.join(t, "no_such_ingest_dir"))
            self.assertEqual(json.load(open(os.path.join(out, "fwd_ingest", "progress.json")))["wires"], {})

    def test_runner_imports_no_locked_module_and_no_model(self):
        src = (NT / "run_ingest_fwd.py").read_text() + (NT / "ingest_branch.py").read_text()
        for bad in ("logic_r2", "logic_r3", "run_r2", "ai_news", "import logic"):
            self.assertNotIn(bad, src, bad)


class Wiring(unittest.TestCase):
    def test_addendum_is_hash_locked_and_names_its_scope(self):
        a = NT / "protocol_ingest_addendum_20261126.md"
        self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(), a.with_suffix(".sha256").read_text().strip(),
                         "the ingest addendum is locked; write a new dated one")
        t = a.read_text()
        for s in ("data/news-ingest", "fwd/ingest_timing.json", "fwd_ingest", "never dropped, imputed or re-timed"):
            self.assertIn(s, t)

    def test_r2_fwd_job_reads_the_branch_optionally(self):
        wf = (ROOT / ".github" / "workflows" / "news_train_r2.yml").read_text()
        fwd = wf[wf.index("\n  fwd:"):]
        self.assertIn("run_ingest_fwd.py r2 out /tmp/ingest", fwd)
        self.assertIn("continue-on-error: true", fwd)
        self.assertLess(fwd.index("run_r2.py fwd out"), fwd.index("run_ingest_fwd.py r2"))
        self.assertEqual(wf.count("run_r2.py fwd out"), 1)

    def test_r3_job_is_counts_only_and_scheduled(self):
        wf = (ROOT / ".github" / "workflows" / "news_train_r3.yml").read_text()
        self.assertIn("\n  fwd_ingest:", wf)
        self.assertIn('cron: "50 22 * * 1-5"', wf)
        self.assertNotIn("\t", wf)
        self.assertIn("run_ingest_fwd.py r3 out /tmp/ingest", wf)

    def test_kuber_passes_the_optional_secret_single_line_only(self):
        wf = (ROOT / ".github" / "workflows" / "kuber.yml").read_text()
        self.assertIn("TRADELAB_DATA_PUSH_TOKEN: ${{ secrets.TRADELAB_DATA_PUSH_TOKEN }}", wf)
        self.assertIn("TRADELAB_DATA_PUSH_TOKEN must be a single line", wf)
        self.assertIn("unset CLAUDE_CODE_OAUTH_TOKEN TRADELAB_SEC_UA TRADELAB_DATA_PUSH_TOKEN", wf)


if __name__ == "__main__":
    unittest.main()
