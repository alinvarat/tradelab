"""The event-book protocol and its frozen components file are locked: any edit must fail CI (write a dated addendum)."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTO = ROOT / "research" / "studies" / "protocol_event_book_20261125.md"
COMP = ROOT / "research" / "event_book" / "components.json"


class Lock(unittest.TestCase):
    def test_protocol_unchanged(self):
        got = hashlib.sha256(PROTO.read_bytes()).hexdigest()
        self.assertEqual(got, PROTO.with_suffix(".sha256").read_text().strip(),
                         "protocol is locked; write a new dated protocol or an addendum instead")

    def test_components_hash_in_protocol(self):
        self.assertIn(hashlib.sha256(COMP.read_bytes()).hexdigest(), PROTO.read_text(),
                      "components.json changed after the protocol was locked")

    def test_components_shape(self):
        c = json.loads(COMP.read_text())
        self.assertGreaterEqual(c["forward_start_ts"], 1795564800)
        for comp in c["components"]:
            self.assertIn(comp["side"], (1, -1))
            self.assertGreater(comp["stop"], 0)
            self.assertLessEqual(comp["weight"] * comp["stop"], 0.25 + 1e-9)     # per-trade loss cap 25% of equity
            self.assertLessEqual(comp["weight"], 3.0)
            self.assertGreaterEqual(comp["effective_from"], c["forward_start_ts"])


if __name__ == "__main__":
    unittest.main()
