import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from core import okx_fund_fwd as of

ROOT = Path(__file__).resolve().parents[1]
PROTO = ROOT / "research" / "studies" / "protocol_fundwin_okx_fwd_20261125.md"
T = 1_800_000_000 // of.DAY8 * of.DAY8


class Lock(unittest.TestCase):
    def test_protocol_unchanged(self):
        got = hashlib.sha256(PROTO.read_bytes()).hexdigest()
        self.assertEqual(got, PROTO.with_suffix(".sha256").read_text().strip(),
                         "protocol is locked; write a new dated protocol instead")

    def test_protocol_matches_code_constants(self):
        text = PROTO.read_text()
        self.assertEqual(of.ENTRY_MINUTES, (15, 5, 1))
        self.assertEqual(of.THRESHOLDS, (0.003, 0.005))
        self.assertEqual(len(of.COHORTS), 6)
        self.assertAlmostEqual(1 / of.ALPHA, 120.0)
        self.assertIn("e-value >= 120", text)
        self.assertIn("0.05/6", text)
        self.assertIn("at least 60 units", text)
        self.assertEqual((of.MIN_UNITS, of.CLIP, of.FEE_SIDE), (60, 0.05, 0.0005))


class Parsing(unittest.TestCase):
    def test_rates_books_realized(self):
        resp = {"data": [{"instId": "AAA-USDT-SWAP", "fundingRate": "0.0041", "fundingTime": str((T) * 1000)},
                         {"instId": "BBB-USD-SWAP", "fundingRate": "0.01", "fundingTime": str(T * 1000)},
                         {"instId": "CCC-USDT-SWAP", "fundingRate": "", "fundingTime": str(T * 1000)}]}
        self.assertEqual(of.parse_rates(resp), {"AAA-USDT-SWAP": (0.0041, T)})
        self.assertEqual(of.parse_rates(None), {})
        tk = {"data": [{"instId": "AAA-USDT-SWAP", "bidPx": "1.00", "askPx": "1.01"}, {"instId": "BBB-USDT-SWAP", "bidPx": "", "askPx": "2"},
                       {"instId": "CCC-USDT-SWAP", "bidPx": "3", "askPx": "2"}]}
        self.assertEqual(of.parse_books(tk), {"AAA-USDT-SWAP": (1.0, 1.01)})
        hist = {"data": [{"fundingTime": str((T + 8 * 3600) * 1000), "realizedRate": "0.1"},
                         {"fundingTime": str(T * 1000), "fundingRate": "0.004", "realizedRate": "0.0039"}]}
        self.assertEqual(of.parse_realized(hist, T), 0.0039)
        self.assertEqual(of.parse_realized({"data": [{"fundingTime": str(T * 1000), "fundingRate": "0.004", "realizedRate": ""}]}, T), 0.004)
        self.assertIsNone(of.parse_realized(hist, T + 5))

    def test_next_settlement(self):
        self.assertEqual(of.next_settlement(T - 1800), T)
        self.assertEqual(of.next_settlement(T - 30), T + of.DAY8)            # under a minute of lead: take the next one
        self.assertEqual(of.next_settlement(T + 10), T + of.DAY8)


class Trades(unittest.TestCase):
    def setUp(self):
        self.rates = {"A-USDT-SWAP": (0.004, T), "B-USDT-SWAP": (-0.006, T), "C-USDT-SWAP": (0.002, T), "D-USDT-SWAP": (0.01, T + 3600),
                      "E-USDT-SWAP": (0.01, T)}
        self.books = {"A-USDT-SWAP": (100.0, 100.2), "B-USDT-SWAP": (10.0, 10.1), "C-USDT-SWAP": (1.0, 1.01), "D-USDT-SWAP": (5.0, 5.1)}

    def test_entries_against_the_payer_at_the_measured_side(self):
        e = of.entries(self.rates, self.books, T, 0.003)
        self.assertEqual([x["inst"] for x in e], ["A-USDT-SWAP", "B-USDT-SWAP"])       # C below threshold, D other schedule, E no book
        a, b = e
        self.assertEqual((a["side"], a["entry_px"]), (-1, 100.0))                       # positive rate: short at the bid
        self.assertEqual((b["side"], b["entry_px"]), (1, 10.1))                         # negative rate: long at the ask
        self.assertEqual([x["inst"] for x in of.entries(self.rates, self.books, T, 0.005)], ["B-USDT-SWAP"])

    def test_settle_trade_math(self):
        a = of.entries(self.rates, self.books, T, 0.003)[0]
        t = of.settle_trade(a, (99.5, 99.7), 0.0042, T, "m15_t0.003")
        # short sold at 100.0, bought back at the ask 99.7: +0.3%; fees 0.1%; receives the settled 0.42%
        self.assertAlmostEqual(t["net"], (1 - 99.7 / 100.0) - 0.001 + 0.0042)
        self.assertEqual(t["exit_px"], 99.7)
        spread_paid = (0.2 / 2) / 100.1 + (0.2 / 2) / 99.6
        self.assertAlmostEqual(t["net_2x"], t["net"] - 0.001 - spread_paid)
        self.assertEqual(t["ctrl_side"], of.control_side(T, a["inst"], "m15_t0.003"))
        # a long at the ask, sold at the bid, pays a positive settled rate
        b = of.entries(self.rates, self.books, T, 0.003)[1]
        tb = of.settle_trade(b, (10.5, 10.6), -0.0061, T, "m5_t0.003")
        self.assertAlmostEqual(tb["net"], (10.5 / 10.1 - 1) - 0.001 + 0.0061)

    def test_control_is_deterministic_and_balanced(self):
        sides = [of.control_side(T + k * of.DAY8, f"I{k}-USDT-SWAP", "m1_t0.005") for k in range(400)]
        self.assertEqual(sides, [of.control_side(T + k * of.DAY8, f"I{k}-USDT-SWAP", "m1_t0.005") for k in range(400)])
        self.assertTrue(150 < sum(1 for s in sides if s > 0) < 250)

    def trades(self, model, ctrl, n=3):
        return [{"net": model, "ctrl_net": ctrl, "net_2x": model - 0.002} for _ in range(n)]

    def test_ledger_edge_needs_everything(self):
        led = of.Ledger()
        for _ in range(400):
            led.add_unit("m15_t0.003", self.trades(0.02, -0.02))
        v = led.verdicts()["m15_t0.003"]
        self.assertEqual(v["verdict"], "edge")
        self.assertGreaterEqual(v["e_value_edge"], 120)
        self.assertEqual(v["trades"], 1200)
        led2 = of.Ledger()
        for _ in range(400):
            led2.add_unit("m15_t0.003", self.trades(0.02, -0.02))
            led2.stats["m15_t0.003"]["net_2x"] -= 0.1                                  # cost check fails
        self.assertNotEqual(led2.verdicts()["m15_t0.003"]["verdict"], "edge")
        few = of.Ledger()
        for _ in range(10):
            few.add_unit("m5_t0.005", self.trades(0.05, -0.05))
        self.assertEqual(few.verdicts()["m5_t0.005"]["verdict"], "continue")

    def test_ledger_no_edge_and_noise(self):
        led = of.Ledger()
        for _ in range(400):
            led.add_unit("m1_t0.003", self.trades(-0.02, 0.02))
        self.assertEqual(led.verdicts()["m1_t0.003"]["verdict"], "no edge")
        noise = of.Ledger()
        for k in range(200):
            noise.add_unit("m1_t0.005", self.trades(0.01 if k % 2 else -0.01, 0.0))
        self.assertEqual(noise.verdicts()["m1_t0.005"]["verdict"], "continue")

    def test_ledger_roundtrip_and_clipping(self):
        led = of.Ledger()
        led.add_unit("m15_t0.003", self.trades(0.3, 0.0))                              # clipped at 5% for the e-process, counted
        led.add_unit("m15_t0.003", [])
        again = of.Ledger(json.loads(json.dumps(led.dump())))
        self.assertEqual(again.eps["m15_t0.003"].n, 1)
        self.assertEqual(again.stats["m15_t0.003"]["clipped"], 3)
        self.assertAlmostEqual(again.eps["m15_t0.003"].sum, 0.5)                       # clip(0.3) - clip(0) = 0.05 over lo + hi = 0.1

    def test_tracking(self):
        rows = [{"minutes": 15, "pred": 0.004 + 0.0001, "settled": 0.004}, {"minutes": 15, "pred": 0.006 + 0.0001, "settled": 0.006},
                {"minutes": 15, "pred": 0.002 + 0.0001, "settled": 0.002}, {"minutes": 5, "pred": 1.0, "settled": None}]
        tr = of.tracking(rows)
        self.assertEqual(tr["15"]["n"], 3)
        self.assertAlmostEqual(tr["15"]["bias"], 0.0001)
        self.assertAlmostEqual(tr["15"]["corr"], 1.0)
        self.assertEqual(tr["5"], {"n": 0})


class Runner(unittest.TestCase):
    def test_finish_writes_state_trades_and_summary(self):
        from research.studies import fundwin_okx_forward as run
        with tempfile.TemporaryDirectory() as td:
            led = of.Ledger()
            tr = [{"T": T, "cohort": "m15_t0.003", "inst": "A", "net": 0.01, "ctrl_net": 0.0, "net_2x": 0.008}]
            led.add_unit("m15_t0.003", tr)
            state = {"meta": {"settlements": 1, "missed": 0, "late_cohorts": 0, "no_rates": 0, "done": [T]}}
            s = run.finish(Path(td), state, led, tr, [{"T": T, "inst": "A", "minutes": 15, "pred": 0.004, "settled": 0.004}])
            self.assertEqual(s["cohorts"]["m15_t0.003"]["trades"], 1)
            self.assertEqual(len((Path(td) / "trades.jsonl").read_text().splitlines()), 1)
            self.assertEqual(json.loads((Path(td) / "state.json").read_text())["meta"]["settlements"], 1)
            run.finish(Path(td), json.loads((Path(td) / "state.json").read_text()), of.Ledger(json.loads((Path(td) / "state.json").read_text())["cohorts"]), [], [])
            self.assertEqual(len((Path(td) / "preds.jsonl").read_text().splitlines()), 1)      # append-only, nothing duplicated


class KeeperAndWorkflow(unittest.TestCase):
    def test_keeper_dispatches_the_ledger(self):
        k = (ROOT / ".github" / "workflows" / "keeper.yml").read_text()
        self.assertIn("fundwin_okx.yml", k)
        self.assertIn("23:30|07:30|15:30", k)
        w = (ROOT / ".github" / "workflows" / "fundwin_okx.yml").read_text()
        self.assertIn("data/okx-fwd", w)
        self.assertNotIn("\t", w)


if __name__ == "__main__":
    unittest.main()
