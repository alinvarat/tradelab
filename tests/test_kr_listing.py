"""Offline tests for core/kr_listing.py (no network, no prices)."""
import unittest

from core import kr_listing as kl


def bars(step, n, f):
    return {1000 * 60 + i * step: (f(i), f(i) * 1.001, f(i) * 0.999, f(i)) for i in range(n)}


class Parsers(unittest.TestCase):
    def test_listing_titles(self):
        for t in ("[거래] 아비트럼(ARB) KRW, BTC 마켓 디지털 자산 추가", "[마켓 추가] 오르빗 체인(ORC) 원화 마켓 추가",
                  "[거래] 웜홀(W) 신규 거래지원 안내 (KRW, USDT 마켓)"):
            self.assertTrue(kl.listing_title(t), t)
        for t in ("[거래] 아비트럼(ARB) BTC, USDT 마켓 디지털 자산 추가", "[마켓 추가] 오르빗 체인(ORC) 원화 마켓 추가 이벤트",
                  "[거래] 아비트럼(ARB) KRW 마켓 거래지원 종료", "투자유의 종목 지정 안내 - 싸이식(CYS)", "[거래] ARB KRW 마켓 추가 일정 연기",
                  "[거래] ARB KRW 마켓 추가 취소"):
            self.assertFalse(kl.listing_title(t), t)
        self.assertEqual(kl.listing_symbols("[마켓 추가] 오르빗 체인(ORC) 원화 마켓 추가"), ["ORC"])

    def test_edited_suffix_notes(self):
        for t in ("레이어제로(ZRO) 신규 거래지원 안내 (KRW, BTC, USDT 마켓) (거래지원 개시 시점 연기 안내)",
                  "Market Support for Jupiter(JUP) (KRW, BTC, USDT Market) (Delay in start of Market Support)",
                  "마켓 추가 NEW 버추얼 프로토콜(VIRTUAL) 원화 마켓 추가 (입금 오픈 시간 변경)",
                  "[마켓 추가] 스타크넷(STRK) 원화 마켓 추가 및 재단 에어드랍 안내 (거래 오픈 오후 10:40)"):
            self.assertTrue(kl.listing_title(t), t)
        self.assertFalse(kl.listing_title("[거래] 아비트럼(ARB) KRW 마켓 추가 (취소 안내)"))
        self.assertFalse(kl.listing_title("KRW 마켓 호가 단위 변경 안내"))
        self.assertFalse(kl.listing_title("업비트 NFT 신규 거래지원 컬렉션 안내 (Sappy Seals 컬렉션)"))
        self.assertEqual(kl.listing_symbols("Market Support for Ondo Finance(ONDO) (KRW, BTC, USDT Market)"), ["ONDO"])

    def test_dedupe_first_across_venues(self):
        ev = [{"sym": "A", "ts": 100 + kl.DEDUPE_S + 5, "src": "u"}, {"sym": "A", "ts": 200, "src": "b"}, {"sym": "A", "ts": 100, "src": "u"}]
        out = kl.dedupe(ev)
        self.assertEqual([e["ts"] for e in out], [100, 100 + kl.DEDUPE_S + 5])

    def test_rules(self):
        self.assertEqual(len(kl.family_rules()), 9)
        self.assertEqual(kl.rule_id(900, 60), "kr_listing|h15m|d1m")


class Trade(unittest.TestCase):
    def test_long_gain_and_net(self):
        b = bars(60, 400, lambda i: 100 + i * 0.1)
        ts = 1000 * 60 - 120
        s = kl.long_trade(b, 60, ts, 60, 900)
        self.assertGreater(s["gross"], 0)
        t = kl.make_trade("A", ts, s, 900)
        self.assertAlmostEqual(t["net"], s["gross"] - kl.COST - kl.FUND[900])
        self.assertEqual(t["side"], 1)

    def test_entry_not_before_delay(self):
        b = bars(60, 400, lambda i: 100.0)
        ts = 1000 * 60 + 30
        s = kl.long_trade(b, 60, ts, 300, 900)
        self.assertGreaterEqual(s["te"], ts + 300)

    def test_stop(self):
        b = bars(60, 100, lambda i: 100.0 if i < 5 else 60.0)
        b = {t: (o, h, min(l, o), c) for t, (o, h, l, c) in b.items()}
        s = kl.long_trade(b, 60, 1000 * 60 - 60, 60, 3600)
        self.assertEqual(s["reason"], "stop")
        self.assertAlmostEqual(s["gross"], -(kl.STOP + kl.STOP_SLIP))

    def test_missing_exit_bar(self):
        b = bars(60, 5, lambda i: 100.0)
        self.assertIsNone(kl.long_trade(b, 60, 1000 * 60 - 60, 60, 3600))

    def test_control_needs_three(self):
        b = bars(300, 100, lambda i: 100 + i * 0.01)
        self.assertIsNone(kl.control_gross({"A": b, "B": b}, ["A", "B", "C"], 300, 1000 * 60 - 300, 60, 900))
        self.assertIsNotNone(kl.control_gross({"A": b, "B": b, "C": b}, ["A", "B", "C"], 300, 1000 * 60 - 300, 60, 900))


if __name__ == "__main__":
    unittest.main()


class Lock(unittest.TestCase):
    def test_protocol_unchanged_and_matches_code(self):
        import hashlib
        from pathlib import Path
        p = Path(__file__).resolve().parents[1] / "research" / "studies" / "protocol_kr_listing_20261126.md"
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), p.with_suffix(".sha256").read_text().strip(),
                         "protocol is locked; write a dated addendum instead")
        text = p.read_text()
        self.assertEqual(kl.DELAYS, (60, 300, 900))
        self.assertEqual(kl.HOLDS, (900, 3600, 14400))
        self.assertEqual(kl.COST, 0.006)
        self.assertIn("kr_listing|h240m|d1m", text)
        self.assertIn("20261126", text)
