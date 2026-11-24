import unittest

from core import entities


class CommonWordNames(unittest.TestCase):
    def test_ordinary_word_uses_do_not_link(self):
        self.assertNotIn("TGT", entities.link("Zscaler receives multiple target hikes ahead of proposed acquisition"))
        self.assertNotIn("TGT", entities.link("Analyst lifts price Target on Nvidia"))
        self.assertNotIn("TGT", entities.link("Fed sticks to its inflation Target"))
        self.assertNotIn("V", entities.link("New visa rules hit tech hiring"))
        self.assertNotIn("AAPL", entities.link("apple orchard sales rise"))

    def test_company_uses_still_link(self):
        self.assertEqual(entities.link("Target beats holiday estimates"), ["TGT"])
        self.assertEqual(entities.link("Apple and Microsoft slide as Amazon jumps"), ["AAPL", "MSFT", "AMZN"])
        self.assertIn("V", entities.link("Visa and Mastercard settle fee case"))


if __name__ == "__main__":
    unittest.main()
