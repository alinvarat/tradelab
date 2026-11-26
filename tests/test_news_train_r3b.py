"""Offline tests for round 3 Track B2 (Korean/Chinese crypto headlines). Synthetic data only."""
import hashlib
import unittest
from pathlib import Path

from research.news_train import logic as L
from research.news_train import run_b as B

ROOT = Path(__file__).resolve().parents[1] / "research" / "news_train"


class Lock(unittest.TestCase):
    def test_addendum_b_hash(self):
        a = ROOT / "protocol_r3_addendum_b_20261126.md"
        self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(), a.with_suffix(".sha256").read_text().strip())
        self.assertIn(hashlib.sha256((ROOT / "params_r3b.json").read_bytes()).hexdigest(), a.read_text())
        self.assertEqual(B.PB["model"], "claude-haiku-5-5")


class Corpus(unittest.TestCase):
    def test_coin_map(self):
        self.assertEqual(B.coin_of_cjk("비트코인 근 한달 만에 최고"), "BTC")
        self.assertEqual(B.coin_of_cjk("比特币突破7万美元"), "BTC")
        self.assertEqual(B.coin_of_cjk("비트코인캐시 급등"), "BCH")              # not read as bitcoin
        self.assertIsNone(B.coin_of_cjk("비트코인과 이더리움 동반 상승"))          # two coins
        self.assertIsNone(B.coin_of_cjk("금값 추락"))
        self.assertEqual(B.coin_of_cjk("Solana 네트워크 장애"), "SOL")

    def test_redact_and_dedupe(self):
        self.assertNotIn("비트코인", B.redact("비트코인 7만1000달러 돌파", "BTC"))
        rows = [{"t": 1000, "coin": "BTC", "title": "비트코인 7만 달러 돌파 소식"}, {"t": 2000, "coin": "BTC", "title": "비트코인 7만 달러 돌파 소식!"},
                {"t": 3000, "coin": "ETH", "title": "이더리움 업그레이드 완료 발표"}]
        self.assertEqual(len(B.dedupe(rows)), 2)

    def test_split_and_refuse(self):
        self.assertIsNone(B.split_b(L.day_ts("2025-11-30")))
        self.assertEqual(B.split_b(L.day_ts("2026-03-31")), "train")
        self.assertEqual(B.split_b(L.day_ts("2026-06-30")), "validation")
        self.assertEqual(B.split_b(L.day_ts("2026-07-01")), "sealed")
        with self.assertRaises(L.SealError):
            B.split_b(L.day_ts("2026-11-27"))


if __name__ == "__main__":
    unittest.main()
