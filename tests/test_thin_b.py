import json
import random
import unittest
from unittest import mock

from core import thin_b as tb

D, H = 86400, 3600
E = 1_800_000_000          # a scheduled endDate


def tr(t, idx=0, price=0.9, side="BUY", size=100.0, tx=None):
    return {"t": t, "side": side, "idx": idx, "price": price, "size": size, "tx": tx or f"0x{t}{idx}{price}{side}"}


class Trades(unittest.TestCase):
    def test_parse_trades_dedupes_and_sorts(self):
        raw = [{"transaction_hash": "0xa", "token_id": "T", "price": 0.5, "size": 10, "timestamp": 200, "side": "buy", "outcome_index": 0},
               {"transaction_hash": "0xa", "token_id": "T", "price": 0.5, "size": 10, "timestamp": 200, "side": "buy", "outcome_index": 0},
               {"transaction_hash": "0xb", "token_id": "T", "price": 0.6, "size": 5, "timestamp": 100, "side": "SELL", "outcome_index": 1},
               {"price": "bad"}]
        out = tb.parse_trades(raw)
        self.assertEqual([x["t"] for x in out], [100, 200])
        self.assertEqual(out[1]["side"], "BUY")

    def test_yes_equivalent_of_a_no_trade(self):
        self.assertAlmostEqual(tb.yes_equiv(tr(1, idx=1, price=0.92)), 0.08)

    def test_first_buy_needs_side_token_size_and_latency_window(self):
        trades = [tr(100, price=0.9, side="SELL"), tr(200, price=0.9, size=5.0), tr(300, idx=1), tr(400, price=0.91)]
        self.assertEqual(tb.first_buy(trades, 0, 100, 1000)["t"], 400)      # SELL, too small and the wrong token are skipped
        self.assertIsNone(tb.first_buy(trades, 0, 100, 399))

    def test_bin_net_with_haircut_and_double_cost(self):
        self.assertAlmostEqual(tb.bin_net(1.0, 0.94), 1 / 0.945 - 1)
        self.assertAlmostEqual(tb.bin_net(1.0, 0.94, 2.0), 1 / 0.95 - 1 - 0.01)
        self.assertAlmostEqual(tb.bin_net(0.0, 0.94), -1.0)


class SingleMarkets(unittest.TestCase):
    def market(self, won=True, closed=E + D):
        return {"id": "7", "end": E, "closed": closed, "yes_won": won}

    def test_b1_known_numbers_and_missing_horizons(self):
        t0 = E - 3 * D
        trades = [tr(t0 - 100, price=0.93), tr(t0 + 400, price=0.94)]
        row = tb.b1_row(self.market(), trades)
        self.assertEqual(list(row["ret"]), ["3d"])           # no price known 7 d out, no BUY in the 1 d window
        self.assertAlmostEqual(row["ret"]["3d"]["net"], 1 / 0.945 - 1)
        self.assertAlmostEqual(row["ret"]["3d"]["gross"], 1 / 0.94 - 1)
        self.assertEqual(row["ts"], E + D)                    # the split follows closedTime
        lost = tb.b1_row(self.market(won=False), trades)
        self.assertAlmostEqual(lost["ret"]["3d"]["net"], -1.0)

    def test_b1_buys_the_no_token_when_no_is_the_favourite(self):
        t0 = E - 3 * D
        trades = [tr(t0 - 100, idx=1, price=0.92), tr(t0 + 400, idx=1, price=0.93)]
        row = tb.b1_row(self.market(won=False), trades)       # Yes lost, so the No favourite wins
        self.assertAlmostEqual(row["ret"]["3d"]["net"], 1 / 0.935 - 1)

    def test_b1_skips_out_of_band_and_already_closed_markets(self):
        t0 = E - 3 * D
        self.assertIsNone(tb.b1_row(self.market(), [tr(t0 - 100, price=0.98), tr(t0 + 400, price=0.98)]))
        self.assertIsNone(tb.b1_row(self.market(), [tr(t0 - 100, price=0.60), tr(t0 + 400, price=0.60)]))
        self.assertIsNone(tb.b1_row(self.market(closed=t0 + 100), [tr(t0 - 100, price=0.93), tr(t0 + 400, price=0.94)]))

    def test_b2_follows_a_jump_to_the_leading_token(self):
        T = E - 5 * D
        trades = [tr(T, price=0.40), tr(T + H, price=0.85), tr(T + H + 400, price=0.87)]
        row = tb.b2_row(self.market(), trades)
        self.assertAlmostEqual(row["ret"]["hold"]["net"], 1 / 0.875 - 1)
        self.assertIsNone(tb.b2_row(self.market(), [tr(T, price=0.70), tr(T + H, price=0.85), tr(T + H + 400, price=0.87)]))   # no 6 h move from <= 0.50

    def test_b5_needs_an_edge_and_a_fill(self):
        t0 = E - 3 * D
        trades = [tr(t0 - 100, price=0.50), tr(t0 + 400, price=0.52)]
        row = tb.b5_row(self.market(), trades, 0.90)
        self.assertEqual(row["ret"]["hold"]["gross"], 1 / 0.52 - 1)
        self.assertIsNone(tb.b5_row(self.market(), trades, 0.60))          # edge 0.10 < 0.15
        self.assertIsNone(tb.b5_row(self.market(), trades, None))


class Baskets(unittest.TestCase):
    def legs(self, price, idx, winners, n=3):
        return [{"trades": [tr(1000, idx=idx, price=0.5, side="SELL"), tr(3700, idx=idx, price=price)], "won": k < winners} for k in range(n)]

    def test_b3_long_basket_pays_one_winner(self):
        r = tb.basket_row("e1", self.legs(0.30, 0, 1), 100000, "B3")
        self.assertAlmostEqual(r["ret"]["hold"]["net"], 1 / (3 * 0.305) - 1)
        self.assertEqual((r["legs"], r["winners"]), (3, 1))

    def test_b3_nothing_won_is_a_total_loss_not_dropped(self):
        r = tb.basket_row("e1", self.legs(0.30, 0, 0), 100000, "B3")
        self.assertAlmostEqual(r["ret"]["hold"]["net"], -1.0)

    def test_b3_expensive_basket_does_not_enter(self):
        self.assertIsNone(tb.basket_row("e1", self.legs(0.34, 0, 1), 100000, "B3"))

    def test_b3_needs_every_leg_to_trade_in_the_window(self):
        legs = self.legs(0.30, 0, 1)
        legs[2]["trades"] = [tr(1000, price=0.30)]            # BUY at 1000 is before the first grid time
        self.assertIsNone(tb.basket_row("e1", legs, 100000, "B3"))

    def test_b4_buys_every_no(self):
        r = tb.basket_row("e1", self.legs(0.60, 1, 1), 100000, "B4")
        self.assertAlmostEqual(r["ret"]["hold"]["net"], 2 / (3 * 0.605) - 1)

    def test_kalshi_long_basket_uses_asks_and_fee(self):
        legs = [{"candles": {3600: (0.28, 0.30)}, "won": k == 0} for k in range(3)]
        r = tb.kalshi_basket_row("k1", legs, 100000, "B6")
        cost = 3 * (0.30 + 0.07 * 0.3 * 0.7 + 0.005)
        self.assertAlmostEqual(r["ret"]["hold"]["net"], 1 / cost - 1)
        self.assertIsNone(tb.kalshi_basket_row("k1", legs, 100000, "B7"))   # NO side costs 3 x 0.74 > 0.97 x 2

    def test_kalshi_missing_quote_blocks_the_hour(self):
        legs = [{"candles": {3600: (0.28, 1.0)}, "won": k == 0} for k in range(3)]
        self.assertIsNone(tb.kalshi_basket_row("k1", legs, 100000, "B6"))


def synth(rule, n, mean, spread=0.2):
    rng = random.Random(5)
    rows = []
    for sp, (a, z) in tb.BOUNDS.items():
        for k in range(n):
            net = rng.gauss(mean, spread)
            rows.append({"symbol": f"pm:{sp}{k}", "venue": "polymarket", "rule": rule, "kind": rule, "ts": a + (z - a) * k / n,
                         "ret": {"hold": {"net": net, "net2": net - 0.02, "gross": net}}})
    return rows


class Verdict(unittest.TestCase):
    def test_pass_kill_and_frequency(self):
        self.assertEqual(tb.verdict(synth("B2", 400, 0.10), ["hold"])["verdict"], "pass")
        self.assertEqual(tb.verdict(synth("B2", 400, -0.05), ["hold"])["verdict"], "killed")
        self.assertNotEqual(tb.verdict(synth("B2", 40, 0.30, 0.1), ["hold"])["verdict"], "pass")     # about 1 a week

    def test_duplicates_invalidate(self):
        rows = synth("B2", 100, 0.1)
        self.assertTrue(tb.verdict(rows + rows[:20], ["hold"])["verdict"].startswith("invalid data"))

    def test_summarize_all_rules_and_b5_bounds(self):
        s = tb.summarize(synth("B2", 100, 0.1) + synth("B5", 30, 0.0))
        self.assertEqual(set(s["per_rule"]), set(tb.RULE_HORIZONS))
        self.assertEqual(s["per_rule"]["B1"]["verdict"], "no data")
        self.assertIn("audit_top", s["per_rule"]["B5"])


class Fetchers(unittest.TestCase):
    def test_norm_market(self):
        from research.studies import thin_b as io
        m = {"id": 5, "conditionId": "0xc", "outcomePrices": json.dumps(["0", "1"]), "clobTokenIds": json.dumps(["a", "b"]),
             "closedTime": "2025-07-04 00:49:16+00", "endDate": "2026-06-30T12:00:00Z", "volumeNum": 12000, "events": [{"id": "9"}], "feesEnabled": False}
        out = io.norm_market(m)
        self.assertFalse(out["yes_won"])
        self.assertLess(out["closed"], out["end"])            # endDate and closedTime really differ; the split uses closedTime
        self.assertIsNone(io.norm_market({**m, "feesEnabled": True}))
        self.assertIsNone(io.norm_market({**m, "outcomePrices": json.dumps(["0.4", "0.6"])}))

    def test_fetch_trades_pages_and_truncation(self):
        from research.studies import thin_b as io
        row = lambda i: {"transaction_hash": f"0x{i}", "token_id": "T", "price": 0.5, "size": 10, "timestamp": 100 + i, "side": "BUY", "outcome_index": 0}
        pages = [{"data": [row(1), row(2)], "pagination": {"has_more": True, "next_cursor": "c1"}},
                 {"data": [row(2), row(3)], "pagination": {"has_more": False, "next_cursor": None}}]
        with mock.patch.object(io, "_get", side_effect=pages):
            trades, trunc = io.fetch_trades("0xc")
        self.assertEqual((len(trades), trunc), (3, False))          # row 2 repeated across pages is de-duplicated
        endless = {"data": [row(1)], "pagination": {"has_more": True, "next_cursor": "c"}}
        with mock.patch.object(io, "_get", return_value=endless):
            self.assertTrue(io.fetch_trades("0xc", max_pages=2)[1])


if __name__ == "__main__":
    unittest.main()
