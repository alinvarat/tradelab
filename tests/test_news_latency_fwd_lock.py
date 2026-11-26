"""The news-latency forward protocol, its params and its Haiku prompt are locked: any edit must fail CI (write a dated addendum)."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTO = ROOT / "research" / "studies" / "protocol_news_latency_fwd_20261126.md"
PARAMS = ROOT / "research" / "news_latency" / "fwd_params.json"
PROMPT = ROOT / "research" / "news_latency" / "fwd_prompt.txt"


class Lock(unittest.TestCase):
    def test_protocol_unchanged(self):
        self.assertEqual(hashlib.sha256(PROTO.read_bytes()).hexdigest(), PROTO.with_suffix(".sha256").read_text().strip(),
                         "protocol is locked; write a new dated protocol or an addendum instead")

    def test_inputs_hashed_in_protocol(self):
        text = PROTO.read_text()
        for p in (PARAMS, PROMPT):
            self.assertIn(hashlib.sha256(p.read_bytes()).hexdigest(), text, f"{p.name} changed after the protocol was locked")

    def test_params_shape(self):
        P = json.loads(PARAMS.read_text())
        self.assertEqual(P["claude_parallel"], 6)
        self.assertEqual(P["min_trades"], 100)
        self.assertTrue(all(s["kind"] in ("sec_atom", "rss", "binance", "okx_ann") and s["poll_s"] >= 10 for s in P["sources"]))
        self.assertEqual(len({s["name"] for s in P["sources"]}), len(P["sources"]))


if __name__ == "__main__":
    unittest.main()
