"""The DVOL forward-test protocol is locked: any edit must fail CI (add a dated note file instead)."""
import hashlib
import unittest
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1] / "research/threefold_plan/dvol_forward"


class ProtocolLock(unittest.TestCase):
    def test_protocol_unchanged(self):
        actual = hashlib.sha256((FOLDER / "protocol.md").read_bytes()).hexdigest()
        self.assertEqual(actual, (FOLDER / "protocol.sha256").read_text().strip(),
                         "protocol.md is locked; do not edit it (write a new dated note file instead)")


if __name__ == "__main__":
    unittest.main()
