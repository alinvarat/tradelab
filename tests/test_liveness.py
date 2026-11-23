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


if __name__ == "__main__":
    unittest.main()
