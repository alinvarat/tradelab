"""Liveness: dead background threads are restarted; /healthz reports stale components."""
import threading
import time
import unittest

import server


class Supervisor(unittest.TestCase):
    def test_dead_thread_is_restarted(self):
        ran = []

        def once():
            ran.append(time.time())
        server.THREADS.clear()
        server.start("probe", once)
        server.THREADS["probe"][2].join()
        self.assertFalse(server.THREADS["probe"][2].is_alive())
        # emulate one supervisor pass without the 60 s sleep
        for name, (target, args, t) in list(server.THREADS.items()):
            if not t.is_alive():
                server.RESTARTS[name] = server.RESTARTS.get(name, 0) + 1
                server.start(name, target, *args)
        server.THREADS["probe"][2].join()
        self.assertEqual(len(ran), 2)
        self.assertEqual(server.RESTARTS["probe"], 1)
        server.THREADS.clear()
        server.RESTARTS.clear()


class Accounts(unittest.TestCase):
    def test_summary_is_safe_before_the_bots_start_and_uses_one_unit(self):
        from unittest import mock
        with mock.patch("server.data.fx_to_usd", return_value=0.03), mock.patch.object(server, "auto", None), \
                mock.patch.object(server, "hunt", None), mock.patch.object(server, "evt", None), mock.patch.object(server, "llm", None):
            out = server.accounts_summary()
        self.assertEqual([r["key"] for r in out["rows"]], ["manual"])
        row = out["rows"][0]
        self.assertAlmostEqual(row["equity_thb"], row["equity_usd"] / 0.03)
        self.assertAlmostEqual(out["thb_per_usd"], 1 / 0.03)
        self.assertEqual(row["return_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
